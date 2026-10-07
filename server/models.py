"""Pydantic request/response models for the Muse Alarm Clock API.

A sequence is a visual flow: a list of blocks (steps) connected by edges
(arrows). The dashboard renders blocks as cards and edges as arrows; the
engine walks them in order when the sequence fires.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- blocks/edges

class Block(BaseModel):
    """One step in a sequence.

    type is one of:
      time_trigger   {time: "HH:MM"}            - fires the sequence
      button_trigger {button: "middle"|"left"|"right", timeout_s: 600}
      alarm          {sound, volume, lines, duration_s}
      page           {lines, duration_s}
      audio          {file, volume}
      wait           {seconds}
    """
    id: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    """An arrow from one block to the next. JSON uses from/to."""
    from_block: str = Field(alias="from")
    to_block: str = Field(alias="to")

    model_config = {"populate_by_name": True}


# ------------------------------------------------------------------ sequences

class SequenceCreate(BaseModel):
    name: str
    blocks: list[Block] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    timezone: str = "America/Los_Angeles"
    manual_time: Optional[str] = None  # "HH:MM" — when set, skips daily computation
    enabled: bool = True
    author: str = "user"  # "user" (dashboard) or "ryker" (AI agent via API)


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    blocks: Optional[list[Block]] = None
    edges: Optional[list[Edge]] = None
    timezone: Optional[str] = None
    manual_time: Optional[str] = None
    enabled: Optional[bool] = None
    author: Optional[str] = None


class SequenceResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    blocks: list[Block]
    edges: list[Edge]
    timezone: str
    manual_time: Optional[str] = None
    author: str = "user"
    created_at: str
    updated_at: str


# ------------------------------------------------------------------- devices

class DeviceCreate(BaseModel):
    name: str
    ip: str
    token: str
    type: str = "tc002"


class DeviceResponse(BaseModel):
    id: str
    name: str
    ip: str
    token: str
    type: str
    created_at: str


# --------------------------------------------------------------------- misc

class TestStep(BaseModel):
    step: int
    block_id: str
    block_type: str
    action: str
    detail: str = ""


class TestRunResponse(BaseModel):
    sequence_id: str
    sequence_name: str
    steps: list[TestStep]
    would_fire_at: Optional[str] = None


class StatusResponse(BaseModel):
    running: bool
    uptime_s: int
    sequences: int
    devices: int
    computed_today: int
    fired_today: list[str]
    next_fire: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]


# --------------------------------------------------------------- executions

class ExecuteRequest(BaseModel):
    device_id: Optional[str] = None  # default: first configured device
    context: dict[str, str] = Field(default_factory=dict)
    # context fills page templates: {date}, {time}, {weather},
    # {wake_reason}, {work_detail}


class ExecuteResponse(BaseModel):
    execution_id: str
    sequence_id: str
    status: str


class ExecutionStatusResponse(BaseModel):
    id: str
    sequence_id: str
    sequence_name: str
    status: str  # running | waiting_button | completed | cancelled | failed | escalated
    current_block_id: Optional[str] = None
    current_block_type: Optional[str] = None
    started_at: str
    updated_at: str
    log: list[dict[str, Any]]
