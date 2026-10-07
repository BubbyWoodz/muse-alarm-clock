"""TC002 device driver for the Muse Alarm Clock.

Controls a Ulanzi TC002 (Pixbar Smart Pixel Clock II) running the community
firmware (tc002-customisation v0.3.1) over its local HTTP API.

The critical capability this driver provides is *physical button press
detection*: the whole alarm-dismiss flow depends on knowing, over the
network, that the user physically pressed a button on the clock.

API summary (verified live 2026-10-07 against v0.3.1):
    Base: http://<ip>/api/v1
    Auth: Authorization: Bearer <token>  (admin token for config writes,
            control token for actions)
"""

from __future__ import annotations

import os
import re
import time

import requests
from sseclient import SSEClient


class TC002Error(Exception):
    """Raised for any transport, auth, or API-level failure."""


# Buttons the firmware knows about (see InputBody in /api/openapi.json).
BUTTONS = ("left", "middle", "right")
BUTTON_EVENTS = ("press", "release", "click", "long")

class TC002Driver:
    """HTTP driver for one TC002 running the community firmware."""

    def __init__(self, ip: str, token: str | None = None, timeout: int = 10):
        """Create a driver.

        Args:
            ip: Clock's LAN address, e.g. "192.168.8.232".
            token: API bearer token. Falls back to the TC002_TOKEN
                environment variable when omitted.
            timeout: Seconds for ordinary HTTP calls.
        """
        token = token or os.environ.get("TC002_TOKEN")
        if not token:
            raise TC002Error(
                "no API token: pass token= or set the TC002_TOKEN env var"
            )
        self.ip = ip
        self.timeout = timeout
        self.base_url = f"http://{ip}/api/v1"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._last_revision: int | None = None

    # ------------------------------------------------------------------ #
    # low-level                                                           #
    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Call the API and return the decoded JSON body."""
        url = self.base_url + path
        kwargs.setdefault("timeout", self.timeout)
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}))
        try:
            resp = requests.request(method, url, headers=headers, **kwargs)
        except requests.RequestException as exc:
            raise TC002Error(f"{method} {path}: connection failed: {exc}") from exc
        if resp.status_code == 401:
            raise TC002Error(f"{method} {path}: unauthorized (bad token?)")
        try:
            body = resp.json()
        except ValueError:
            raise TC002Error(
                f"{method} {path}: non-JSON reply (HTTP {resp.status_code})"
            ) from None
        if isinstance(body, dict) and body.get("error"):
            raise TC002Error(
                f"{method} {path}: {body.get('error')}: {body.get('message')}"
            )
        if resp.status_code >= 400:
            raise TC002Error(f"{method} {path}: HTTP {resp.status_code}: {body}")
        return body

    # ------------------------------------------------------------------ #
    # status / config                                                     #
    # ------------------------------------------------------------------ #
    def get_status(self) -> dict:
        """Return the live status object (revision, base, brightness, time...)."""
        return self._request("GET", "/status")

    def get_config(self) -> dict:
        """Return the persisted configuration."""
        return self._request("GET", "/config")

    def set_config(self, patch: dict) -> dict:
        """PATCH selected config fields, e.g. {"base": "clock"}.

        Known flat fields: base, brightness, timezone, ntp_server, ...
        Returns the updated config.
        """
        return self._request("PATCH", "/config", json=patch)

    def set_brightness(self, level: int) -> dict:
        """Set display brightness, 1..100."""
        level = max(1, min(100, int(level)))
        return self._request(
            "POST", "/action", json={"action": "brightness", "brightness": level}
        )

    def show_clock(self) -> dict:
        """Switch the display base back to the clock face."""
        return self.set_config({"base": "clock"})

    # ------------------------------------------------------------------ #
    # display                                                             #
    # ------------------------------------------------------------------ #
    def show_text(
        self,
        lines: list[str] | str,
        duration_s: int = 10,
        colour: str = "ffffff",
    ) -> dict:
        """Show scrolling text on the display.

        Args:
            lines: One string or a list of strings; joined into a single
                scrolling line (the panel is 52x16, long text scrolls).
            duration_s: How long to show it, 1..300.
            colour: 6-digit hex colour, e.g. "ff0000".

        Only printable ASCII is accepted by the firmware; anything else is
        stripped and the text is truncated to 128 chars.
        """
        if isinstance(lines, str):
            lines = [lines]
        text = "  ".join(lines)
        text = "".join(ch for ch in text if 32 <= ord(ch) <= 126)
        text = re.sub(r"\s+", " ", text).strip()[:128]
        if not text:
            raise TC002Error("show_text: nothing printable to display")
        duration_s = max(1, min(300, int(duration_s)))
        return self._request(
            "POST",
            "/notify",
            json={"text": text, "duration_s": duration_s, "colour": colour},
        )

    # ------------------------------------------------------------------ #
    # sound                                                               #
    # ------------------------------------------------------------------ #
    def play_sound(
        self, name: str, volume: int = 80, loop: bool = False
    ) -> dict:
        """Play a sound file stored on the clock.

        Args:
            name: Sound name as known to the device (see GET /sounds).
            volume: 0..100.
            loop: Repeat until stop_sound() is called.
        """
        volume = max(0, min(100, int(volume)))
        return self._request(
            "POST",
            "/sound",
            json={"name": name, "volume": volume, "loop": loop},
        )

    def stop_sound(self) -> dict:
        """Stop any currently playing sound."""
        return self._request("POST", "/sound", json={"stop": True})

    def list_sounds(self) -> dict:
        """List sounds stored on the clock."""
        return self._request("GET", "/sounds")

    # ------------------------------------------------------------------ #
    # input injection (testing)                                           #
    # ------------------------------------------------------------------ #
    def press_button(self, button: str = "middle", event: str = "click") -> dict:
        """Inject a button event as if pressed on the device.

        Useful for testing the dismiss flow without touching the clock.
        """
        if button not in BUTTONS:
            raise TC002Error(f"unknown button {button!r}; expected {BUTTONS}")
        if event not in BUTTON_EVENTS:
            raise TC002Error(
                f"unknown event {event!r}; expected {BUTTON_EVENTS}"
            )
        return self._request(
            "POST", "/input", json={"control": button, "event": event}
        )

    # ------------------------------------------------------------------ #
    # physical button detection (the whole point)                         #
    # ------------------------------------------------------------------ #
    def wait_for_button(
        self, button: str = "middle", timeout_s: int = 30, poll_interval: float = 0.5
    ) -> bool:
        """Block until a physical button is pressed on the clock.

        Primary method: the /events SSE stream, which pushes every applied
        statement in real time. Falls back to polling /status and watching
        the ``revision`` counter when the stream cannot be opened.

        Args:
            button: Which button to wait for ("left"/"middle"/"right").
                Filtering is best-effort: any physical press counts, and a
                press of the named button is preferred when the event data
                identifies it.
            timeout_s: Give up after this many seconds.
            poll_interval: Seconds between status polls in fallback mode.

        Returns:
            True if a button press was detected, False on timeout.
        """
        if button not in BUTTONS:
            raise TC002Error(f"unknown button {button!r}; expected {BUTTONS}")
        try:
            return self._wait_for_button_sse(button, timeout_s)
        except TC002Error:
            # SSE unavailable (stream busy, network hiccup): poll instead.
            return self._wait_for_button_poll(button, timeout_s, poll_interval)

    def _wait_for_button_sse(self, button: str, timeout_s: int) -> bool:
        """SSE-based detection. Raises TC002Error when the stream fails."""
        url = self.base_url + "/events"
        try:
            self._last_revision = self.get_status().get("revision")
        except TC002Error:
            self._last_revision = None
        try:
            client = SSEClient(
                url,
                headers={"Authorization": self.headers["Authorization"]},
                timeout=max(timeout_s, 5),
            )
        except Exception as exc:
            raise TC002Error(f"SSE connect failed: {exc}") from exc

        deadline = time.monotonic() + timeout_s
        try:
            for event in client:
                if time.monotonic() >= deadline:
                    return False
                data = (event.data or "").strip()
                if not data:
                    continue  # keepalive comment (": ping")
                # Any applied statement means *something* happened on the
                # device. Prefer events that name the button we want.
                if button in data:
                    return True
                if '"revision"' in data or '"control"' in data or '"input"' in data:
                    # State changed but we can't attribute it; confirm via
                    # the revision counter before claiming a press.
                    if self._revision_changed():
                        return True
            return False
        except Exception as exc:
            raise TC002Error(f"SSE read failed: {exc}") from exc

    def _revision_changed(self) -> bool:
        """True if the status revision moved since this call's snapshot."""
        before = self._last_revision
        try:
            after = self.get_status().get("revision")
        except TC002Error:
            return False
        self._last_revision = after
        return after is not None and before is not None and after != before

    def _wait_for_button_poll(
        self, button: str, timeout_s: int, poll_interval: float
    ) -> bool:
        """Fallback detection: poll /status and watch the revision counter.

        A physical press always applies a statement, which always bumps
        ``revision``. Verified live: a middle-button press moved revision
        4 -> 5 and flipped base clock -> canvas.
        """
        try:
            start = self.get_status().get("revision")
        except TC002Error:
            return False
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            try:
                current = self.get_status().get("revision")
            except TC002Error:
                continue
            if current != start:
                return True
        return False

    def wait_for_button_polling(
        self, button: str = "middle", timeout_s: int = 30, poll_interval: float = 0.5
    ) -> bool:
        """wait_for_button() using only the polling fallback (for tests)."""
        if button not in BUTTONS:
            raise TC002Error(f"unknown button {button!r}; expected {BUTTONS}")
        return self._wait_for_button_poll(button, timeout_s, poll_interval)
