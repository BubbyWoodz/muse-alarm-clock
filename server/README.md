# Muse Alarm Clock — Server

REST API + sequence execution engine. Stores alarm sequences, fires them on
schedule, and talks to clock devices through a driver interface.

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Interactive docs: http://localhost:8000/docs

Storage is a single SQLite file at `server/data/alarm.db` (created on first
run). On a fresh database the engine seeds the default **Wake Up Sequence**
(author `ryker`).

The driver is currently a mock (`driver.py: MockClockDriver`) — it logs every
action instead of touching hardware. The real TC002 driver (`device/tc002/`)
plugs into `make_driver()` when it's built.

## API

Fully usable without the dashboard UI — the AI agent drives everything here.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/sequences` | List all sequences (includes `author`) |
| POST | `/api/sequences` | Create. Body: `{name, blocks, edges, timezone?, manual_time?, enabled?, author?}`. `author` defaults to `"user"`; the agent passes `"author": "ryker"` |
| GET | `/api/sequences/{id}` | Get one |
| PUT | `/api/sequences/{id}` | Update (partial) |
| DELETE | `/api/sequences/{id}` | Delete |
| POST | `/api/sequences/{id}/test` | Dry run — logs each step, touches nothing |
| POST | `/api/sequences/{id}/execute` | Run NOW against a device. Body (optional): `{device_id?, context?}`. Returns `{execution_id}` |
| GET | `/api/executions/{id}` | Execution status: `running`, `waiting_button`, `completed`, `cancelled`, `failed`, `escalated`, plus current block and step log |
| POST | `/api/executions/{id}/cancel` | Stop a running execution |
| GET | `/api/devices` | List configured clocks |
| POST | `/api/devices` | Add clock. Body: `{name, ip, token, type?}` (`type` defaults to `tc002`) |
| DELETE | `/api/devices/{id}` | Remove a clock |
| POST | `/api/devices/{id}/simulate-button` | Mock-only test hook: `{"button": "middle"}` pretends a physical press |
| GET | `/api/status` | Engine health: uptime, counts, next fire times, recent events |

### Blocks

A sequence is `blocks` + `edges` (`{from, to}` arrows). Block types:

- `time_trigger` `{time: "HH:MM"}` — fires the sequence
- `button_trigger` `{button: "middle", timeout_s: 600}` — pauses for a physical press; timeout → escalation
- `alarm` `{sound, volume, lines, duration_s}` — play sound + show text
- `page` `{lines, duration_s, advance_button}` — show text; a button press advances early
- `audio` `{file, volume}` — play an MP3
- `wait` `{seconds}` — pause

Page lines support templates filled at execution time: `{date}`, `{time}`,
`{weather}`, `{wake_reason}`, `{work_detail}`. Pass values via the `context`
object on `/execute` (date/time are automatic).

### Wake Up Sequence (locked order)

1. **Alarm** — plays sound, shows `WAKE UP`, then waits for the middle button (10 min timeout)
2. **Dismiss** (button press) → pages, 10 s each, button advances early:
   - `Good Morning Rhy` + `:-)`
   - date / time / weather
   - wake reason
   - work shift details
   - `Your 1440 waits for you`
3. **No press in 10 min** → escalation: loudest alarm at max volume + logged event

## Scheduling (reliability core)

- **12:00 AM** — compute every enabled sequence's fire time for the day.
- **3:00 AM** — fail-safe recompute for anything still missing.
- A sequence with `manual_time` set skips computation and fires at that time.
- A background thread checks every 30 s. Fire times more than 5 minutes past
  are marked missed, never fired late (no surprise alarms after a restart).
- Each firing runs in its own thread; button waits are sliced so `/cancel`
  stays responsive.

## Files

- `main.py` — FastAPI app and routes
- `models.py` — Pydantic request/response models
- `db.py` — SQLite store (sequences, devices)
- `driver.py` — `ClockDriver` ABC + `MockClockDriver`
- `engine.py` — scheduler, executor, dry-run, Wake Up template
