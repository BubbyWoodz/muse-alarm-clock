# TC002 driver

Python driver for the Ulanzi TC002 (Pixbar Smart Pixel Clock II) running the
community firmware (`tc002-customisation` v0.3.1). This is the hardware layer
the Muse Alarm Clock backend talks to.

## Install

```bash
pip install -r requirements.txt
```

## Configure

The driver needs the clock's LAN IP and an API bearer token. Tokens live on
the clock at `/data/tc002/state/credentials/tokens` (pull via ADB); use the
`control` token for actions or the `admin` token for everything.

```bash
export TC002_IP=192.168.8.232
export TC002_TOKEN=<control-or-admin-token>
```

Token scopes: the `control` token covers actions (text, sound, brightness,
button inject, events). Config writes (`set_config`, `show_clock`,
timezone/NTP) need the `admin` token — the device answers `403 forbidden`
otherwise.

No IP or token is hardcoded — both are constructor args or env vars.

## Usage

```python
from driver import TC002Driver

drv = TC002Driver("192.168.8.232", token="...")  # or TC002_TOKEN env var

# Status: revision bumps on every state change, base is clock/canvas/art
status = drv.get_status()
print(status["revision"], status["base"], status["time"]["state"])

# Show scrolling text for 10 seconds
drv.show_text("Good morning Rhy", duration_s=10)

# Multiple lines become one scrolling line
drv.show_text(["Wake up", "Work at 9:00"], duration_s=15, colour="ffaa00")

# Play a sound stored on the clock (see list_sounds), loop until stopped
drv.play_sound("alarm.mp3", volume=80, loop=True)
drv.stop_sound()

# Brightness 1..100
drv.set_brightness(60)

# Back to the clock face (e.g. after a button cycled the display mode)
drv.show_clock()

# Inject a button event (for testing the dismiss flow without touching hardware)
drv.press_button("middle", "click")

# THE important one: block until the user physically presses a button.
# Uses the /events SSE stream; falls back to polling the revision counter.
if drv.wait_for_button("middle", timeout_s=30):
    print("dismissed!")
else:
    print("timed out - escalate")
```

## Physical button detection

`wait_for_button()` is the primitive the whole alarm-dismiss flow is built
on. Verified live 2026-10-07: a physical middle-button press moved the
status `revision` 4 -> 5 and flipped `base` from `clock` to `canvas`.

Two mechanisms, in order:

1. **SSE stream** (`GET /api/v1/events`) — real-time push of every applied
   statement; `: ping` keepalives are ignored. Any data event is treated as
   device activity and confirmed against the revision counter.
2. **Polling fallback** — `GET /api/v1/status` every 0.5 s, watching for a
   `revision` increment. A physical press always applies a statement, which
   always bumps the revision.

The `button` argument (`"left"` / `"middle"` / `"right"`) is best-effort
filtering for now: any physical press counts, with preference for events
that name the requested button.

## Self-test

```bash
TC002_IP=192.168.8.232 TC002_TOKEN=... python3 test_driver.py
```

Runs status, brightness, text, an injected button press, then waits 10 s
for you to physically press the middle button. Exits 0 when everything
passes.

## API reference

| Method | Endpoint | Notes |
|---|---|---|
| `get_status()` | `GET /api/v1/status` | revision, base, brightness, time, network |
| `get_config()` / `set_config(patch)` | `GET`/`PATCH /api/v1/config` | e.g. `{"base": "clock"}`, `{"timezone": "America/Los_Angeles"}`, `{"ntp_server": "1.2.3.4"}` (dotted IPv4, no DNS on a fresh runtime) |
| `set_brightness(level)` | `POST /api/v1/action` | `{"action": "brightness", "brightness": 1..100}` |
| `show_text(lines, duration_s, colour)` | `POST /api/v1/notify` | 1-128 printable ASCII chars, 1-300 s |
| `play_sound(name, volume, loop)` / `stop_sound()` | `POST /api/v1/sound` | volume 0-100 |
| `list_sounds()` | `GET /api/v1/sounds` | |
| `press_button(button, event)` | `POST /api/v1/input` | `{"control": "middle", "event": "click"}` |
| `wait_for_button(button, timeout_s)` | `GET /api/v1/events` SSE, fallback `GET /api/v1/status` poll | |
| `show_clock()` | `PATCH /api/v1/config` | `{"base": "clock"}` |

Full schema (no auth needed): `GET http://<ip>/api/openapi.json`.
