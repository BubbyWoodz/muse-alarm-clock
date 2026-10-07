"""Sequence execution engine.

Two jobs:
  1. Scheduler: a background thread wakes every 30 s, computes each enabled
     sequence's fire time (midnight compute, 3 AM fail-safe recompute,
     manual_time overrides skip computation), and fires due sequences.
  2. Executor: walks a sequence's blocks in edge order, calling the device
     driver. Button triggers pause for a physical press (10 min default
     timeout -> escalation). Page blocks show 10 s and advance early on
     button press. Everything runs in its own thread so one sequence never
     blocks the scheduler; executions are tracked and cancellable via API.

Time handling: all fire times are computed in the sequence's timezone
(default America/Los_Angeles) using zoneinfo from the stdlib.
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from db import Store
from driver import ClockDriver, make_driver

# How often the scheduler wakes up.
TICK_S = 30
# Midnight compute window / 3 AM fail-safe window (minutes past the hour).
COMPUTE_WINDOW_MIN = 5
# If a computed fire time is more than this far in the past, treat it as
# missed rather than firing immediately (avoids a surprise alarm hours late
# after a restart).
MISSED_GRACE_S = 5 * 60
# Cap a single wait_for_button slice so cancel stays responsive.
WAIT_SLICE_S = 5

ESCALATION_SOUND = "alarm_max.mp3"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _utcnow().isoformat(timespec="seconds")


def _parse_hhmm(value: str) -> tuple[int, int]:
    h, m = value.strip().split(":")
    return int(h), int(m)


def _ordered_blocks(blocks: list[dict], edges: list[dict]) -> list[dict]:
    """Walk blocks in edge order starting from the trigger.

    Finds the block with no incoming edge (preferring a time_trigger), then
    follows outgoing edges. Blocks unreachable from the start are appended
    in their original order so nothing is silently dropped.
    """
    by_id = {b["id"]: b for b in blocks}
    incoming = {b["id"]: 0 for b in blocks}
    outgoing: dict[str, str] = {}
    for e in edges:
        src = e.get("from", e.get("from_block"))
        dst = e.get("to", e.get("to_block"))
        if src in by_id and dst in by_id:
            incoming[dst] = incoming.get(dst, 0) + 1
            if src not in outgoing:  # first edge wins; chains are linear
                outgoing[src] = dst
    starts = [b for b in blocks if incoming.get(b["id"], 0) == 0]
    start = next((b for b in starts if b.get("type") == "time_trigger"), None)
    if start is None:
        start = starts[0] if starts else (blocks[0] if blocks else None)
    ordered: list[dict] = []
    seen: set[str] = set()
    cur = start
    while cur is not None and cur["id"] not in seen:
        ordered.append(cur)
        seen.add(cur["id"])
        nxt = outgoing.get(cur["id"])
        cur = by_id.get(nxt) if nxt else None
    for b in blocks:
        if b["id"] not in seen:
            ordered.append(b)
    return ordered


def _fill_templates(lines: list[str], context: dict[str, str]) -> list[str]:
    """Replace {date}, {time}, {weather}, {wake_reason}, {work_detail}."""
    out = []
    for line in lines:
        try:
            out.append(line.format(**context))
        except (KeyError, IndexError, ValueError):
            out.append(line)
    return out


def _default_context(seq_tz: str, extra: dict[str, str] | None) -> dict[str, str]:
    now = datetime.now(ZoneInfo(seq_tz))
    ctx = {
        "date": now.strftime("%a %b %d"),
        "time": now.strftime("%-I:%M %p"),
        "weather": "--",
        "wake_reason": "--",
        "work_detail": "--",
    }
    ctx.update(extra or {})
    return ctx


# ---------------------------------------------------------------------------
# Wake Up Sequence template (locked order, author "ryker")
# ---------------------------------------------------------------------------

def wake_up_template() -> dict:
    """The default Wake Up Sequence. Author is ryker (specified via API)."""
    blocks = [
        {
            "id": "b_alarm",
            "type": "alarm",
            "config": {
                "sound": "wake.mp3",
                "volume": 70,
                "lines": ["WAKE UP"],
                "duration_s": 30,
            },
        },
        {
            "id": "b_dismiss",
            "type": "button_trigger",
            "config": {"button": "middle", "timeout_s": 600},
        },
        {
            "id": "b_hello",
            "type": "page",
            "config": {
                "lines": ["Good Morning Rhy", ":-)"],
                "duration_s": 10,
                "advance_button": "middle",
            },
        },
        {
            "id": "b_datetime",
            "type": "page",
            "config": {
                "lines": ["{date}", "{time}", "{weather}"],
                "duration_s": 10,
                "advance_button": "middle",
            },
        },
        {
            "id": "b_reason",
            "type": "page",
            "config": {
                "lines": ["{wake_reason}"],
                "duration_s": 10,
                "advance_button": "middle",
            },
        },
        {
            "id": "b_work",
            "type": "page",
            "config": {
                "lines": ["{work_detail}"],
                "duration_s": 10,
                "advance_button": "middle",
            },
        },
        {
            "id": "b_handoff",
            "type": "page",
            "config": {
                "lines": ["Your 1440 waits for you"],
                "duration_s": 10,
                "advance_button": "middle",
            },
        },
    ]
    edges = [
        {"from": "b_alarm", "to": "b_dismiss"},
        {"from": "b_dismiss", "to": "b_hello"},
        {"from": "b_hello", "to": "b_datetime"},
        {"from": "b_datetime", "to": "b_reason"},
        {"from": "b_reason", "to": "b_work"},
        {"from": "b_work", "to": "b_handoff"},
    ]
    return {
        "name": "Wake Up Sequence",
        "blocks": blocks,
        "edges": edges,
        "timezone": "America/Los_Angeles",
        "manual_time": None,
        "enabled": True,
        "author": "ryker",
    }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SequenceEngine:
    def __init__(self, store: Store):
        self.store = store
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self.started_at = _utcnow()

        # Scheduling state (in-memory; recomputed daily / on restart).
        self._computed: dict[str, str] = {}        # seq_id -> "YYYY-MM-DD" computed for
        self._fired: dict[str, str] = {}          # seq_id -> "YYYY-MM-DD" fired on
        self._fire_times: dict[str, datetime] = {}  # seq_id -> aware fire datetime

        # Execution tracking.
        self.executions: dict[str, dict] = {}     # exec_id -> execution record

        # Recent events ring buffer (for /api/status).
        self.events: list[dict] = []

    # -- lifecycle ----------------------------------------------------
    def start(self) -> None:
        self._seed_templates()
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="seq-scheduler")
        self._thread.start()
        self._event("engine", "scheduler started")

    def stop(self) -> None:
        with self._lock:
            self._running = False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def _seed_templates(self) -> None:
        """Create the default Wake Up Sequence on a fresh database."""
        if not self.store.list_sequences():
            data = wake_up_template()
            seq_id = f"seq_{uuid.uuid4().hex[:12]}"
            self.store.create_sequence(seq_id, data)
            self._event("seed", f"created default Wake Up Sequence ({seq_id})")

    # -- events -------------------------------------------------------
    def _event(self, kind: str, message: str, **extra) -> None:
        entry = {"ts": _ts(), "kind": kind, "message": message, **extra}
        with self._lock:
            self.events.append(entry)
            self.events = self.events[-200:]
        print(f"[engine] {kind}: {message}")

    # -- scheduling ---------------------------------------------------
    def _today_str(self, tz: str) -> str:
        return datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")

    def _resolve_fire_time(self, seq: dict, day: datetime) -> datetime | None:
        """Resolve a sequence's fire time for the given date (in seq tz).

        manual_time wins; otherwise the time_trigger block's HH:MM.
        """
        hhmm = seq.get("manual_time")
        if not hhmm:
            for b in seq.get("blocks", []):
                if b.get("type") == "time_trigger":
                    hhmm = b.get("config", {}).get("time")
                    break
        if not hhmm:
            return None
        try:
            h, m = _parse_hhmm(hhmm)
            tz = ZoneInfo(seq.get("timezone") or "America/Los_Angeles")
            return day.replace(hour=h, minute=m, second=0, microsecond=0, tzinfo=tz)
        except (ValueError, AttributeError):
            return None

    def _compute_sequence(self, seq: dict) -> None:
        tz = seq.get("timezone") or "America/Los_Angeles"
        today = self._today_str(tz)
        now_local = datetime.now(ZoneInfo(tz))
        fire = self._resolve_fire_time(seq, now_local)
        with self._lock:
            self._computed[seq["id"]] = today
            if fire:
                self._fire_times[seq["id"]] = fire
            else:
                self._fire_times.pop(seq["id"], None)
        if fire:
            self._event("compute", f"{seq['name']} fires at {fire.isoformat()}")

    def _scheduler_loop(self) -> None:
        while self.running:
            try:
                self._tick()
            except Exception as e:  # never let the scheduler die
                self._event("error", f"scheduler tick failed: {e}")
            time.sleep(TICK_S)

    def _tick(self) -> None:
        sequences = self.store.list_sequences()
        # Midnight compute: 00:00-00:05 local (use first seq tz; per-seq below).
        for seq in sequences:
            if not seq.get("enabled"):
                continue
            tz = seq.get("timezone") or "America/Los_Angeles"
            now_local = datetime.now(ZoneInfo(tz))
            today = now_local.strftime("%Y-%m-%d")
            with self._lock:
                computed = self._computed.get(seq["id"])
            # Lazy compute (covers restarts) + midnight window.
            if computed != today:
                self._compute_sequence(seq)
            # 3 AM fail-safe: recompute anything still missing.
            if now_local.hour == 3 and now_local.minute < COMPUTE_WINDOW_MIN:
                with self._lock:
                    still_missing = self._computed.get(seq["id"]) != today
                if still_missing:
                    self._event("failsafe", f"3AM recompute for {seq['name']}")
                    self._compute_sequence(seq)

        # Due check.
        for seq in sequences:
            if not seq.get("enabled"):
                continue
            tz = seq.get("timezone") or "America/Los_Angeles"
            now_local = datetime.now(ZoneInfo(tz))
            today = now_local.strftime("%Y-%m-%d")
            with self._lock:
                fire = self._fire_times.get(seq["id"])
                fired = self._fired.get(seq["id"])
            if fire is None or fired == today:
                continue
            late_by = (now_local - fire).total_seconds()
            if now_local >= fire:
                if late_by > MISSED_GRACE_S:
                    # Missed its window (e.g. server was down); don't fire late.
                    with self._lock:
                        self._fired[seq["id"]] = today
                    self._event("missed", f"{seq['name']} missed its {fire.isoformat()} window")
                else:
                    with self._lock:
                        self._fired[seq["id"]] = today
                    self._event("fire", f"firing {seq['name']}")
                    self.execute_now(seq["id"])

    # -- executions ---------------------------------------------------
    def _new_execution(self, seq: dict, device: dict, context: dict) -> dict:
        exec_id = f"exec_{uuid.uuid4().hex[:12]}"
        rec = {
            "id": exec_id,
            "sequence_id": seq["id"],
            "sequence_name": seq["name"],
            "device_id": device["id"],
            "device_name": device.get("name", "?"),
            "status": "running",
            "current_block_id": None,
            "current_block_type": None,
            "cancel_requested": False,
            "context": context,
            "started_at": _ts(),
            "updated_at": _ts(),
            "log": [],
        }
        with self._lock:
            self.executions[exec_id] = rec
        return rec

    def get_execution(self, exec_id: str) -> dict | None:
        with self._lock:
            rec = self.executions.get(exec_id)
            return dict(rec) if rec else None

    def cancel_execution(self, exec_id: str) -> bool:
        with self._lock:
            rec = self.executions.get(exec_id)
            if not rec or rec["status"] not in ("running", "waiting_button"):
                return False
            rec["cancel_requested"] = True
            rec["updated_at"] = _ts()
            return True

    def execute_now(self, seq_id: str, device_id: str | None = None,
                    context: dict[str, str] | None = None) -> dict:
        """Start a real execution right now. Returns the execution record."""
        seq = self.store.get_sequence(seq_id)
        if not seq:
            raise KeyError(f"no such sequence: {seq_id}")
        if device_id:
            device = self.store.get_device(device_id)
            if not device:
                raise KeyError(f"no such device: {device_id}")
        else:
            devices = self.store.list_devices()
            if not devices:
                raise ValueError("no devices configured — add one via POST /api/devices first")
            device = devices[0]
        ctx = _default_context(seq.get("timezone") or "America/Los_Angeles", context)
        rec = self._new_execution(seq, device, ctx)
        t = threading.Thread(target=self._run_execution,
                             args=(rec["id"],), daemon=True,
                             name=f"exec-{rec['id']}")
        t.start()
        self._event("execute", f"started {rec['id']} for {seq['name']} on {device.get('name')}")
        return rec

    # -- execution internals ------------------------------------------
    def _log_step(self, rec: dict, action: str, detail: str = "") -> None:
        entry = {"ts": _ts(), "action": action, "detail": detail}
        with self._lock:
            rec["log"].append(entry)
            rec["updated_at"] = _ts()

    def _set_status(self, rec: dict, status: str,
                    block_id: str | None = None, block_type: str | None = None) -> None:
        with self._lock:
            rec["status"] = status
            rec["current_block_id"] = block_id
            rec["current_block_type"] = block_type
            rec["updated_at"] = _ts()

    def _cancelled(self, rec: dict) -> bool:
        with self._lock:
            return rec["cancel_requested"]

    def _sleep_chunked(self, rec: dict, seconds: float) -> bool:
        """Sleep, checking for cancel. Returns False if cancelled."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._cancelled(rec):
                return False
            time.sleep(min(1.0, end - time.monotonic()))
        return True

    def _wait_button_chunked(self, rec: dict, driver: ClockDriver,
                             button: str, timeout_s: float) -> bool | None:
        """Wait for a button in slices so cancel stays responsive.

        Returns True (pressed), False (timeout), None (cancelled).
        """
        self._set_status(rec, "waiting_button", rec["current_block_id"], rec["current_block_type"])
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._cancelled(rec):
                return None
            remaining = deadline - time.monotonic()
            if driver.wait_for_button(button, min(WAIT_SLICE_S, remaining)):
                return True
        return False

    def _escalate(self, rec: dict, driver: ClockDriver, reason: str) -> None:
        self._set_status(rec, "escalated", rec["current_block_id"], rec["current_block_type"])
        self._log_step(rec, "escalate", reason)
        self._event("escalation", f"{rec['sequence_name']}: {reason}",
                    execution_id=rec["id"])
        try:
            driver.play_sound(ESCALATION_SOUND, 100)
            driver.show_text(["NOT DISMISSED", "WAKE UP NOW"], 30)
        except Exception as e:
            self._log_step(rec, "escalate_error", str(e))

    def _run_execution(self, exec_id: str) -> None:
        with self._lock:
            rec = self.executions.get(exec_id)
        if not rec:
            return
        seq = self.store.get_sequence(rec["sequence_id"])
        if not seq:
            self._set_status(rec, "failed")
            self._log_step(rec, "error", "sequence no longer exists")
            return
        device = self.store.get_device(rec["device_id"])
        if not device:
            # Fall back to an ephemeral mock so the run is still observable.
            device = {"id": rec["device_id"], "name": rec["device_name"],
                      "ip": "", "token": "", "type": "mock"}
        driver = make_driver(device)
        try:
            self._walk(rec, seq, driver)
            if self._cancelled(rec):
                self._set_status(rec, "cancelled")
                self._log_step(rec, "cancelled", "execution cancelled")
            elif rec["status"] not in ("escalated", "failed"):
                self._set_status(rec, "completed")
                self._log_step(rec, "completed", "sequence finished")
            self._event("done", f"{rec['id']} ended as {rec['status']}")
        except Exception as e:
            self._set_status(rec, "failed")
            self._log_step(rec, "error", str(e))
            self._event("error", f"{rec['id']} failed: {e}")

    def _walk(self, rec: dict, seq: dict, driver: ClockDriver) -> None:
        blocks = _ordered_blocks(seq.get("blocks", []), seq.get("edges", []))
        ctx = rec["context"]
        for block in blocks:
            if self._cancelled(rec):
                return
            btype = block.get("type", "")
            cfg = block.get("config", {}) or {}
            self._set_status(rec, "running", block.get("id"), btype)
            self._log_step(rec, "block", f"{btype} ({block.get('id')})")

            if btype == "time_trigger":
                continue  # entry point; nothing to do at runtime

            elif btype == "button_trigger":
                button = cfg.get("button", "middle")
                timeout = float(cfg.get("timeout_s", 600))
                result = self._wait_button_chunked(rec, driver, button, timeout)
                if result is None:
                    return  # cancelled
                if result:
                    self._log_step(rec, "button_pressed", f"button={button}")
                else:
                    self._escalate(rec, driver,
                                   f"no {button} press within {int(timeout)}s")
                    return

            elif btype == "alarm":
                lines = _fill_templates(cfg.get("lines", ["WAKE UP"]), ctx)
                driver.play_sound(cfg.get("sound", "wake.mp3"),
                                  int(cfg.get("volume", 70)))
                driver.show_text(lines, int(cfg.get("duration_s", 30)))
                self._log_step(rec, "alarm",
                               f"sound={cfg.get('sound')} lines={lines}")

            elif btype == "page":
                lines = _fill_templates(cfg.get("lines", []), ctx)
                duration = float(cfg.get("duration_s", 10))
                advance_button = cfg.get("advance_button", "middle")
                driver.show_text(lines, int(duration))
                self._log_step(rec, "page", f"lines={lines} duration_s={duration}")
                # Button press advances early; timeout just moves on.
                result = self._wait_button_chunked(rec, driver, advance_button, duration)
                if result is None:
                    return  # cancelled
                if result:
                    self._log_step(rec, "page_advanced_early", f"button={advance_button}")

            elif btype == "audio":
                driver.play_sound(cfg.get("file", ""), int(cfg.get("volume", 70)))
                self._log_step(rec, "audio", f"file={cfg.get('file')}")

            elif btype == "wait":
                secs = float(cfg.get("seconds", 5))
                self._log_step(rec, "wait", f"seconds={secs}")
                if not self._sleep_chunked(rec, secs):
                    return  # cancelled

            else:
                self._log_step(rec, "unknown_block", f"type={btype} skipped")

    # -- dry run ------------------------------------------------------
    def dry_run(self, seq_id: str) -> dict:
        seq = self.store.get_sequence(seq_id)
        if not seq:
            raise KeyError(f"no such sequence: {seq_id}")
        blocks = _ordered_blocks(seq.get("blocks", []), seq.get("edges", []))
        ctx = _default_context(seq.get("timezone") or "America/Los_Angeles", None)
        steps: list[dict] = []
        tz = seq.get("timezone") or "America/Los_Angeles"
        now_local = datetime.now(ZoneInfo(tz))
        fire = self._resolve_fire_time(seq, now_local)
        for i, block in enumerate(blocks, 1):
            btype = block.get("type", "")
            cfg = block.get("config", {}) or {}
            if btype == "time_trigger":
                action = f"fires at {cfg.get('time', '?')} ({tz})"
            elif btype == "button_trigger":
                action = (f"wait up to {cfg.get('timeout_s', 600)}s for "
                          f"{cfg.get('button', 'middle')} press, else escalate")
            elif btype == "alarm":
                lines = _fill_templates(cfg.get("lines", []), ctx)
                action = f"play {cfg.get('sound')} @vol {cfg.get('volume')} + show {lines}"
            elif btype == "page":
                lines = _fill_templates(cfg.get("lines", []), ctx)
                action = f"show {lines} for {cfg.get('duration_s', 10)}s (button advances early)"
            elif btype == "audio":
                action = f"play {cfg.get('file')} @vol {cfg.get('volume', 70)}"
            elif btype == "wait":
                action = f"sleep {cfg.get('seconds', 5)}s"
            else:
                action = f"unknown block type '{btype}' — skipped"
            steps.append({"step": i, "block_id": block.get("id"),
                          "block_type": btype, "action": action, "detail": ""})
        return {
            "sequence_id": seq_id,
            "sequence_name": seq["name"],
            "steps": steps,
            "would_fire_at": fire.isoformat() if fire else None,
        }

    # -- status -------------------------------------------------------
    def status(self) -> dict:
        with self._lock:
            today = _utcnow().strftime("%Y-%m-%d")
            computed_today = sum(1 for d in self._computed.values() if d == today)
            fired_today = [sid for sid, d in self._fired.items() if d == today]
            next_fire = [
                {"sequence_id": sid, "fire_at": dt.isoformat()}
                for sid, dt in sorted(self._fire_times.items(), key=lambda kv: kv[1])
                if dt > _utcnow() and self._fired.get(sid) != today
            ]
            recent = list(self.events[-20:])
        uptime = int((_utcnow() - self.started_at).total_seconds())
        return {
            "running": self.running,
            "uptime_s": uptime,
            "sequences": len(self.store.list_sequences()),
            "devices": len(self.store.list_devices()),
            "computed_today": computed_today,
            "fired_today": fired_today,
            "next_fire": next_fire,
            "recent_events": recent,
        }
