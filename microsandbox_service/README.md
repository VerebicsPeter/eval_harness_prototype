# microsandbox_service

A light FastAPI wrapper around the [microsandbox](https://microsandbox.dev) Python SDK. It exposes microsandbox's stateful microVM lifecycle (create, exec, file I/O, destroy) over HTTP so networked training loops can drive sandboxes remotely.

This is intentionally thin. It does **not** reimplement the microsandbox runtime or the old `msb serve` RPC portal; it relies on the SDK (which bundles the runtime) and only adds:

- an in-process registry of live `Sandbox` handles (stateful sessions by id),
- HTTP endpoints for lifecycle / exec / file I/O,
- optional bearer-token auth,
- idle-TTL cleanup of forgotten sandboxes.

## Install

From the repo root:

```bash
uv pip install -e microsandbox_service
# or
pip install -e microsandbox_service
```

## Run

```bash
microsandbox-service
# or
python -m microsandbox_service
```

Interactive API docs (OpenAPI/Swagger) are served at `http://<host>:<port>/docs`.

### Single-worker constraint

The sandbox registry lives **in the server process**, so the service must run as a
single worker (the entrypoint pins `workers=1`). Do not put it behind a
multi-worker/multi-replica setup that would split requests across processes,
since a sandbox created in one process is invisible to the others. Concurrency is
handled via async, not extra workers. (If horizontal scaling is ever needed, the
path would be microsandbox detached sandboxes + `Sandbox.get()` reconnect.)

## Configuration

All settings come from environment variables prefixed with `MSB_SERVICE_`:

| Variable | Default | Description |
| --- | --- | --- |
| `MSB_SERVICE_HOST` | `127.0.0.1` | Bind address |
| `MSB_SERVICE_PORT` | `8000` | Bind port |
| `MSB_SERVICE_API_KEY` | (unset) | If set, all endpoints except `/health` require `Authorization: Bearer <key>`. If unset, the service is unauthenticated (a warning is logged). |
| `MSB_SERVICE_DEFAULT_IMAGE` | `python` | Image used when a create request omits `image` |
| `MSB_SERVICE_DEFAULT_CPUS` | `1` | Default vCPUs |
| `MSB_SERVICE_DEFAULT_MEMORY` | `512` | Default memory (MiB) |
| `MSB_SERVICE_IDLE_TTL_SECONDS` | `600` | Idle time after which a sandbox is reaped |
| `MSB_SERVICE_MAX_SANDBOXES` | `50` | Cap on concurrent sandboxes (create returns 503 beyond this) |
| `MSB_SERVICE_REAPER_INTERVAL_SECONDS` | `60` | How often the idle reaper runs |

## API

- `GET /health` -> `{ "status": "ok", "sandbox_count": N }` (no auth)
- `POST /sandboxes` -> create a sandbox, returns `SandboxInfo` with an `id`
- `GET /sandboxes` -> list active sandboxes
- `GET /sandboxes/{id}` -> one sandbox's info
- `DELETE /sandboxes/{id}` -> stop and remove a sandbox (204)
- `POST /sandboxes/{id}/exec` -> run a command
- `POST /sandboxes/{id}/files/write` -> write a file
- `POST /sandboxes/{id}/files/read` -> read a file

File contents are transferred as `encoding: "utf-8"` (plain string) or
`encoding: "base64"` (for binary), so file I/O is binary-safe.

### Example

Create a VM using:

```json
POST /sandboxes
{
  "image": "python",
  "cpus": 1,
  "memory": 256,
  "name": "bar"
}
```

Run a script in the VM using:

```json
POST /sandboxes/{sandbox_id}/exec
{
  "cmd": ["python", "-c", "print('Hi from microVM!')"],
  "timeout": 30
}
```

## Tests

Unit tests use a fake sandbox (no real microVM):

```bash
pip install -e "microsandbox_service[test]"
pytest microsandbox_service/tests/test_service.py
```

An optional end-to-end smoke test boots a real microVM (downloads the `python`
image on first run):

```bash
MSB_SERVICE_RUN_INTEGRATION=1 pytest microsandbox_service/tests/test_integration.py
```
