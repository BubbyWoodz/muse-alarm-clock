"""Clock device driver interface.

`ClockDriver` is the abstraction every supported clock implements. The
sequence engine only talks to this interface, so adding a new clock model
means writing one driver class — the engine, API, and dashboard stay the
same.

`MockClockDriver` logs every action instead of touching hardware. It is the
default driver until the real TC002 driver (device/tc002/) is wired in.
"""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ClockDriver(ABC):
    """Abstract interface a clock device must implement."""

    def __init__(self, device: dict):
        self.device = device
        self.name = device.get("name", "unknown")
        self.ip = device.get("ip", "")

    @abstractmethod
    def show_text(self, lines: list[str], duration_s: int) -> None:
        """Show lines of text on the display for duration_s seconds."""
        ...

    @abstractmethod
    def play_sound(self, file: str, volume: int) -> None:
        """Play an audio file at 0-100 volume."""
        ...

    @abstractmethod
    def wait_for_button(self, button: str, timeout_s: int) -> bool:
        """Block until `button` is pressed. True = pressed, False = timed out."""
        ...

    @abstractmethod
    def set_brightness(self, level: int) -> None:
        """Set display brightness 0-100."""
        ...


class MockClockDriver(ClockDriver):
    """Logs actions instead of calling hardware.

    Button presses can be simulated (for tests and the dry-run UI) via
    `simulate_press(button)` or the POST /api/devices/{id}/simulate-button
    endpoint. A class-level registry maps device id -> driver instance so the
    API layer can reach the right driver's event.
    """

    _registry: dict[str, "MockClockDriver"] = {}
    _registry_lock = threading.Lock()

    def __init__(self, device: dict):
        super().__init__(device)
        self.log: list[dict] = []
        self._press_events: dict[str, threading.Event] = {}
        self._log_lock = threading.Lock()
        with MockClockDriver._registry_lock:
            MockClockDriver._registry[device["id"]] = self

    @classmethod
    def get(cls, device_id: str) -> "MockClockDriver | None":
        with cls._registry_lock:
            return cls._registry.get(device_id)

    @classmethod
    def unregister(cls, device_id: str) -> None:
        with cls._registry_lock:
            cls._registry.pop(device_id, None)

    # -- internal -----------------------------------------------------
    def _record(self, action: str, detail: str = "") -> None:
        entry = {"ts": _ts(), "device": self.name, "action": action, "detail": detail}
        with self._log_lock:
            self.log.append(entry)
        print(f"[mock:{self.name}] {action} {detail}".rstrip())

    def _event_for(self, button: str) -> threading.Event:
        with self._log_lock:
            ev = self._press_events.get(button)
            if ev is None:
                ev = threading.Event()
                self._press_events[button] = ev
            return ev

    # -- ClockDriver API ----------------------------------------------
    def show_text(self, lines: list[str], duration_s: int) -> None:
        self._record("show_text", f"lines={lines} duration_s={duration_s}")

    def play_sound(self, file: str, volume: int) -> None:
        self._record("play_sound", f"file={file} volume={volume}")

    def wait_for_button(self, button: str, timeout_s: int) -> bool:
        self._record("wait_for_button", f"button={button} timeout_s={timeout_s}")
        ev = self._event_for(button)
        ev.clear()
        pressed = ev.wait(timeout=timeout_s)
        self._record("button_result", f"button={button} pressed={pressed}")
        return pressed

    def set_brightness(self, level: int) -> None:
        self._record("set_brightness", f"level={level}")

    # -- test hook ----------------------------------------------------
    def simulate_press(self, button: str) -> bool:
        """Pretend the physical button was pressed. Returns False if nobody
        is currently waiting (the press is then ignored, like real hardware
        would when nothing is listening)."""
        ev = self._event_for(button)
        # Only count it if someone is actually waiting on it.
        self._record("simulate_press", f"button={button}")
        ev.set()
        return True


class TC002ClockDriver(ClockDriver):
    """Adapter: wraps device/tc002/driver.py's TC002Driver in the
    ClockDriver interface the engine expects.

    The TC002 driver is imported lazily so the server still runs without
    the device/ tree (e.g. in CI or for UI-only development).
    """

    def __init__(self, device: dict):
        super().__init__(device)
        try:
            import sys
            import os
            # device/tc002 lives at ../../device/tc002 relative to server/
            here = os.path.dirname(os.path.abspath(__file__))
            dev_path = os.path.normpath(os.path.join(here, "..", "device"))
            if dev_path not in sys.path:
                sys.path.insert(0, dev_path)
            from tc002.driver import TC002Driver
        except ImportError as exc:
            raise RuntimeError(
                f"TC002 driver not available: {exc}. "
                "Is device/tc002/driver.py present with its requirements installed?"
            ) from exc
        token = device.get("token") or os.environ.get("TC002_TOKEN", "")
        self._drv = TC002Driver(ip=self.ip, token=token)

    def show_text(self, lines: list[str], duration_s: int) -> None:
        self._drv.show_text(lines, duration_s=duration_s)

    def play_sound(self, file: str, volume: int) -> None:
        # `file` is the sound name as known to the clock (see GET /sounds).
        self._drv.play_sound(file, volume=volume)

    def wait_for_button(self, button: str, timeout_s: int) -> bool:
        return self._drv.wait_for_button(button=button, timeout_s=timeout_s)

    def set_brightness(self, level: int) -> None:
        self._drv.set_brightness(level)


def make_driver(device: dict) -> ClockDriver:
    """Driver factory. TC002 devices get the real hardware driver;
    anything else falls back to the mock (logs actions, no hardware)."""
    if device.get("type") == "tc002":
        return TC002ClockDriver(device)
    return MockClockDriver(device)
