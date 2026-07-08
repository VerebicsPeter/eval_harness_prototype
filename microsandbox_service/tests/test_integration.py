"""Optional end-to-end smoke test that boots a real microsandbox microVM.

Skipped unless ``MSB_SERVICE_RUN_INTEGRATION=1`` is set, since it requires the
microsandbox runtime and downloads the ``python`` image on first run.

Run with: ``MSB_SERVICE_RUN_INTEGRATION=1 pytest microsandbox_service/tests/test_integration.py``
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from microsandbox_service.app import create_app
from microsandbox_service.config import Settings

pytestmark = pytest.mark.skipif(
    os.environ.get("MSB_SERVICE_RUN_INTEGRATION") != "1",
    reason="set MSB_SERVICE_RUN_INTEGRATION=1 to run the real-microVM smoke test",
)


def test_real_microvm_round_trip() -> None:
    # Uses the default (real) sandbox factory.
    settings = Settings(api_key=None, default_image="python")
    app = create_app(settings=settings)
    with TestClient(app) as client:
        sandbox_id = client.post("/sandboxes", json={"image": "python"}).json()["id"]
        try:
            resp = client.post(
                f"/sandboxes/{sandbox_id}/exec",
                json={"cmd": ["python3", "-c", "print('hello from microvm')"]},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["success"] is True
            assert "hello from microvm" in body["stdout"]

            client.post(
                f"/sandboxes/{sandbox_id}/files/write",
                json={"path": "/tmp/msg.txt", "content": "round trip works\n"},
            )
            read = client.post(
                f"/sandboxes/{sandbox_id}/files/read",
                json={"path": "/tmp/msg.txt"},
            )
            assert read.json()["content"].strip() == "round trip works"
        finally:
            client.delete(f"/sandboxes/{sandbox_id}")
