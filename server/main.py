"""Muse Alarm Clock — backend API server.

Run:
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000

The API is fully usable without the dashboard UI: the AI agent drives
sequences, executions, and devices directly through these endpoints.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import Store
from driver import MockClockDriver
from engine import SequenceEngine
from models import (
    DeviceCreate,
    DeviceResponse,
    ExecuteRequest,
    ExecuteResponse,
    ExecutionStatusResponse,
    SequenceCreate,
    SequenceResponse,
    SequenceUpdate,
    StatusResponse,
    TestRunResponse,
)

BASE_DIR = Path(__file__).resolve().parent
import os as _os

DB_PATH = Path(_os.environ.get("DB_PATH", BASE_DIR / "data" / "alarm.db"))

store: Store
engine: SequenceEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, engine
    store = Store(DB_PATH)
    engine = SequenceEngine(store)
    engine.start()
    yield
    engine.stop()
    store.close()


app = FastAPI(title="Muse Alarm Clock", version="0.1.0", lifespan=lifespan)

# The dashboard (and any local tooling) talks to this API cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _seq_to_response(data: dict) -> SequenceResponse:
    return SequenceResponse(**data)


# ---------------------------------------------------------------- sequences

@app.get("/api/sequences", response_model=list[SequenceResponse])
def list_sequences():
    return [_seq_to_response(s) for s in store.list_sequences()]


@app.post("/api/sequences", response_model=SequenceResponse, status_code=201)
def create_sequence(body: SequenceCreate):
    # author defaults to "user"; the AI agent passes "author": "ryker".
    seq_id = f"seq_{uuid.uuid4().hex[:12]}"
    data = store.create_sequence(seq_id, body.model_dump(by_alias=True))
    return _seq_to_response(data)


@app.get("/api/sequences/{seq_id}", response_model=SequenceResponse)
def get_sequence(seq_id: str):
    data = store.get_sequence(seq_id)
    if not data:
        raise HTTPException(404, f"no such sequence: {seq_id}")
    return _seq_to_response(data)


@app.put("/api/sequences/{seq_id}", response_model=SequenceResponse)
def update_sequence(seq_id: str, body: SequenceUpdate):
    patch = {k: v for k, v in body.model_dump(by_alias=True).items() if v is not None}
    data = store.update_sequence(seq_id, patch)
    if not data:
        raise HTTPException(404, f"no such sequence: {seq_id}")
    return _seq_to_response(data)


@app.delete("/api/sequences/{seq_id}", status_code=204)
def delete_sequence(seq_id: str):
    if not store.delete_sequence(seq_id):
        raise HTTPException(404, f"no such sequence: {seq_id}")
    return None


@app.post("/api/sequences/{seq_id}/test", response_model=TestRunResponse)
def test_sequence(seq_id: str):
    """Dry run: log every step the sequence would take, touch nothing."""
    try:
        return engine.dry_run(seq_id)
    except KeyError:
        raise HTTPException(404, f"no such sequence: {seq_id}")


@app.post("/api/sequences/{seq_id}/execute", response_model=ExecuteResponse, status_code=202)
def execute_sequence(seq_id: str, body: ExecuteRequest | None = None):
    """Run the sequence NOW against a real device. Returns an execution ID
    the caller can poll with GET /api/executions/{id}."""
    body = body or ExecuteRequest()
    try:
        rec = engine.execute_now(seq_id, device_id=body.device_id, context=body.context)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ExecuteResponse(execution_id=rec["id"], sequence_id=seq_id, status=rec["status"])


# ---------------------------------------------------------------- executions

@app.get("/api/executions/{exec_id}", response_model=ExecutionStatusResponse)
def get_execution(exec_id: str):
    rec = engine.get_execution(exec_id)
    if not rec:
        raise HTTPException(404, f"no such execution: {exec_id}")
    return ExecutionStatusResponse(
        id=rec["id"],
        sequence_id=rec["sequence_id"],
        sequence_name=rec["sequence_name"],
        status=rec["status"],
        current_block_id=rec["current_block_id"],
        current_block_type=rec["current_block_type"],
        started_at=rec["started_at"],
        updated_at=rec["updated_at"],
        log=rec["log"],
    )


@app.post("/api/executions/{exec_id}/cancel")
def cancel_execution(exec_id: str):
    if not engine.get_execution(exec_id):
        raise HTTPException(404, f"no such execution: {exec_id}")
    if not engine.cancel_execution(exec_id):
        raise HTTPException(409, "execution is not running and cannot be cancelled")
    return {"ok": True, "execution_id": exec_id}


# ------------------------------------------------------------------ devices

@app.get("/api/devices", response_model=list[DeviceResponse])
def list_devices():
    return [DeviceResponse(**d) for d in store.list_devices()]


@app.post("/api/devices", response_model=DeviceResponse, status_code=201)
def create_device(body: DeviceCreate):
    dev_id = f"dev_{uuid.uuid4().hex[:12]}"
    data = store.create_device(dev_id, body.model_dump())
    return DeviceResponse(**data)


@app.delete("/api/devices/{dev_id}", status_code=204)
def delete_device(dev_id: str):
    if not store.delete_device(dev_id):
        raise HTTPException(404, f"no such device: {dev_id}")
    MockClockDriver.unregister(dev_id)
    return None


@app.post("/api/devices/{dev_id}/simulate-button")
def simulate_button(dev_id: str, body: dict):
    """Mock-driver test hook: pretend a physical button was pressed.

    Body: {"button": "middle"}. Only meaningful while an execution is
    waiting in wait_for_button; ignored otherwise.
    """
    button = (body or {}).get("button", "middle")
    driver = MockClockDriver.get(dev_id)
    if not driver:
        raise HTTPException(404, f"no live mock driver for device: {dev_id}")
    driver.simulate_press(button)
    return {"ok": True, "device_id": dev_id, "button": button}


# ------------------------------------------------------------------- status

@app.get("/api/status", response_model=StatusResponse)
def get_status():
    return engine.status()


@app.get("/api")
def api_index():
    return {"name": "Muse Alarm Clock", "version": "0.1.0", "docs": "/docs"}


# ------------------------------------------------------------------- frontend
# Serve the built dashboard (app/dist) as a single-page app. In Docker the
# dist/ tree is copied to /app/frontend; in dev it lives at ../app/dist.
def _mount_frontend():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    candidates = [
        Path("/app/frontend"),  # Docker
        Path(__file__).parent.parent / "app" / "dist",  # repo dev layout
    ]
    dist = next((p for p in candidates if (p / "index.html").exists()), None)
    if not dist:
        return  # UI not built; API-only mode

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_root():
        return FileResponse(dist / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str):
        # Don't swallow API routes or docs.
        if path.startswith("api/") or path in ("docs", "openapi.json", "redoc"):
            raise HTTPException(404)
        candidate = dist / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


_mount_frontend()
