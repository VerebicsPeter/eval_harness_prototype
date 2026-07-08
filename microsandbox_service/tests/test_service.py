"""Unit tests for the microsandbox service using a fake sandbox (no real microVM).

Run with: ``pytest microsandbox_service/tests/test_service.py``
"""

from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from microsandbox_service.app import create_app
from microsandbox_service.config import Settings


# ---------------------------------------------------------------------------
# fake sandbox
# ---------------------------------------------------------------------------


class FakeFs:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def write(self, path: str, data: bytes) -> None:
        assert isinstance(data, (bytes, bytearray)), "fs.write must receive bytes"
        self.files[path] = bytes(data)

    async def read(self, path: str) -> bytes:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]


class FakeSandbox:
    def __init__(self, name: str) -> None:
        self.name = name
        self.fs = FakeFs()
        self.stopped = False

    async def exec(self, program, args=None, cwd=None, env=None, timeout=None):
        args = args or []
        # "boom" simulates a command that exits non-zero.
        if "boom" in args:
            return SimpleNamespace(exit_code=1, stdout_text="", stderr_text="boom failed")
        return SimpleNamespace(
            exit_code=0,
            stdout_text=" ".join([program, *args]),
            stderr_text="",
        )

    async def stop(self) -> None:
        self.stopped = True


async def fake_factory(name: str, image: str, cpus: int, memory: int) -> FakeSandbox:
    return FakeSandbox(name)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def build_client(**settings_overrides) -> TestClient:
    settings = Settings(**settings_overrides)
    app = create_app(settings=settings, sandbox_factory=fake_factory)
    return TestClient(app)


@pytest.fixture()
def client() -> TestClient:
    with build_client(api_key=None) as c:
        yield c


def _create(client: TestClient, **body) -> str:
    resp = client.post("/sandboxes", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["sandbox_count"] == 0


def test_create_list_get(client: TestClient) -> None:
    sandbox_id = _create(client, image="python", cpus=1, memory=256)

    resp = client.get("/sandboxes")
    assert resp.status_code == 200
    assert [s["id"] for s in resp.json()] == [sandbox_id]

    resp = client.get(f"/sandboxes/{sandbox_id}")
    assert resp.status_code == 200
    assert resp.json()["image"] == "python"

    assert client.get("/health").json()["sandbox_count"] == 1


def test_get_unknown_returns_404(client: TestClient) -> None:
    assert client.get("/sandboxes/does-not-exist").status_code == 404


def test_exec_success_and_failure(client: TestClient) -> None:
    sandbox_id = _create(client)

    resp = client.post(f"/sandboxes/{sandbox_id}/exec", json={"cmd": ["echo", "hi"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["returncode"] == 0
    assert body["stdout"] == "echo hi"

    resp = client.post(f"/sandboxes/{sandbox_id}/exec", json={"cmd": ["run", "boom"]})
    body = resp.json()
    assert body["success"] is False
    assert body["returncode"] == 1
    assert body["stderr"] == "boom failed"


def test_exec_unknown_sandbox_404(client: TestClient) -> None:
    resp = client.post("/sandboxes/nope/exec", json={"cmd": ["echo", "hi"]})
    assert resp.status_code == 404


def test_exec_requires_nonempty_cmd(client: TestClient) -> None:
    sandbox_id = _create(client)
    resp = client.post(f"/sandboxes/{sandbox_id}/exec", json={"cmd": []})
    assert resp.status_code == 422


def test_file_text_round_trip(client: TestClient) -> None:
    sandbox_id = _create(client)

    resp = client.post(
        f"/sandboxes/{sandbox_id}/files/write",
        json={"path": "/tmp/msg.txt", "content": "round trip works\n"},
    )
    assert resp.status_code == 200
    assert resp.json()["bytes_written"] == len("round trip works\n".encode())

    resp = client.post(
        f"/sandboxes/{sandbox_id}/files/read",
        json={"path": "/tmp/msg.txt"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "round trip works\n"


def test_file_base64_round_trip(client: TestClient) -> None:
    sandbox_id = _create(client)
    raw = bytes(range(256))
    encoded = base64.b64encode(raw).decode("ascii")

    resp = client.post(
        f"/sandboxes/{sandbox_id}/files/write",
        json={"path": "/tmp/blob.bin", "content": encoded, "encoding": "base64"},
    )
    assert resp.status_code == 200
    assert resp.json()["bytes_written"] == 256

    resp = client.post(
        f"/sandboxes/{sandbox_id}/files/read",
        json={"path": "/tmp/blob.bin", "encoding": "base64"},
    )
    assert resp.status_code == 200
    assert base64.b64decode(resp.json()["content"]) == raw


def test_read_binary_as_utf8_returns_400(client: TestClient) -> None:
    sandbox_id = _create(client)
    encoded = base64.b64encode(b"\xff\xfe\xfd").decode("ascii")
    client.post(
        f"/sandboxes/{sandbox_id}/files/write",
        json={"path": "/tmp/bad.bin", "content": encoded, "encoding": "base64"},
    )
    resp = client.post(
        f"/sandboxes/{sandbox_id}/files/read",
        json={"path": "/tmp/bad.bin", "encoding": "utf-8"},
    )
    assert resp.status_code == 400


def test_write_invalid_base64_returns_400(client: TestClient) -> None:
    sandbox_id = _create(client)
    resp = client.post(
        f"/sandboxes/{sandbox_id}/files/write",
        json={"path": "/tmp/x", "content": "not!base64!", "encoding": "base64"},
    )
    assert resp.status_code == 400


def test_delete_stops_and_removes(client: TestClient) -> None:
    sandbox_id = _create(client)
    registry = client.app.state.registry
    entry = registry.get(sandbox_id)

    resp = client.delete(f"/sandboxes/{sandbox_id}")
    assert resp.status_code == 204
    assert entry.sandbox.stopped is True
    assert client.get(f"/sandboxes/{sandbox_id}").status_code == 404
    assert client.delete(f"/sandboxes/{sandbox_id}").status_code == 404


def test_max_sandboxes_cap_returns_503() -> None:
    with build_client(api_key=None, max_sandboxes=1) as client:
        _create(client)
        resp = client.post("/sandboxes", json={})
        assert resp.status_code == 503


def test_auth_enforced_when_key_set() -> None:
    with build_client(api_key="s3cret") as client:
        # health is exempt
        assert client.get("/health").status_code == 200

        # missing / malformed / wrong tokens are rejected
        assert client.post("/sandboxes", json={}).status_code == 401
        assert client.post(
            "/sandboxes", json={}, headers={"Authorization": "Basic xyz"}
        ).status_code == 401
        assert client.post(
            "/sandboxes", json={}, headers={"Authorization": "Bearer wrong"}
        ).status_code == 401

        # correct token succeeds
        resp = client.post(
            "/sandboxes", json={}, headers={"Authorization": "Bearer s3cret"}
        )
        assert resp.status_code == 201
