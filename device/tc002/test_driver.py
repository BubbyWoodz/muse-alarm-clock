#!/usr/bin/env python3
"""Self-test for the TC002 driver against a real clock.

Usage:
    TC002_IP=192.168.8.232 TC002_TOKEN=<token> python3 test_driver.py

The test exercises status, brightness, text display, and then waits up to
10 seconds for you to physically press the middle button on the clock.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from driver import TC002Driver, TC002Error


def main() -> int:
    ip = os.environ.get("TC002_IP")
    token = os.environ.get("TC002_TOKEN")
    if not ip or not token:
        print("set TC002_IP and TC002_TOKEN env vars first")
        return 2

    drv = TC002Driver(ip, token)
    failures = 0

    def check(name, fn):
        nonlocal failures
        try:
            result = fn()
            print(f"[ok] {name}")
            return result
        except TC002Error as exc:
            failures += 1
            print(f"[FAIL] {name}: {exc}")
            return None

    print(f"--- TC002 self-test @ {ip} ---")

    status = check("get_status", drv.get_status)
    if status:
        print(
            f"     revision={status.get('revision')} base={status.get('base')} "
            f"time={status.get('time', {}).get('state')} "
            f"ip={status.get('network', {}).get('ip')}"
        )

    check("set_brightness(50)", lambda: drv.set_brightness(50))
    check("set_brightness(100)", lambda: drv.set_brightness(100))

    check(
        "show_text",
        lambda: drv.show_text("driver self-test", duration_s=8),
    )

    check("press_button (injected)", lambda: drv.press_button("middle", "click"))

    print()
    print(">>> Press the MIDDLE button on the clock within 10 seconds... <<<")
    pressed = False
    try:
        pressed = drv.wait_for_button("middle", timeout_s=10)
    except TC002Error as exc:
        failures += 1
        print(f"[FAIL] wait_for_button: {exc}")
    if pressed:
        print("[ok] wait_for_button: physical press detected")
    else:
        failures += 1
        print("[FAIL] wait_for_button: no press seen in 10s")

    # Leave the clock face tidy.
    try:
        drv.show_clock()
    except TC002Error:
        pass

    print()
    if failures:
        print(f"RESULT: {failures} check(s) failed")
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
