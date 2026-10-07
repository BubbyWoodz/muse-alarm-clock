# Muse Alarm Clock

A visual alarm-sequence builder for the Ulanzi TC002 Pixbar Smart Pixel Clock II
(and any future supported clocks). Built for Christian, designed for everybody.

## The idea

A dashboard of sequence cards (e.g. "wake up"). Each sequence is a timeline of
steps with arrows: a time trigger fires the alarm (with per-step audio
choice), a button press acts as the next trigger, then pages flow — greeting,
date/time/weather, wake reason, work shift — each page user-arranged via
drag and drop. One app, works with anybody's clock.

## Layout

- `app/` — web dashboard: sequence cards, drag-and-drop timeline builder.
  UI rule: no emojis, theme-colored SVG icons only.
- `server/` — sequence engine: executes timelines, talks to clocks, serves the API.
- `device/` — hardware drivers. `tc002/` = Ulanzi TC002 (HTTP/MQTT) driver.
- `docker/` — Dockerfile + compose for self-hosted deployment.
- `brumble/` — Christian's Umbrel community app-store package.
- `TUTORIAL.txt` — plain-English, section-by-section explanation of every piece
  of code: what it does, why it's there, written as the build happens.

## Build order

1. Prove the hardware: TC002 on WiFi, verify a physical middle-button press is
   detectable over the network (the trigger everything depends on).
2. Device driver (`device/tc002/`): display pages, audio playback, button events.
3. Sequence engine (`server/`): timeline executor — triggers, steps, audio.
4. Dashboard (`app/`): cards, timeline builder, drag-and-drop.
5. Docker + Brumble packaging for one-click install on any Umbrel.

## Standing rules

- Public/generic install from day one. No Christian-only hardcoding.
- Ships via Brumble store: source in GitHub, GHCR image built on push to main,
  store package pins the image. No hand-editing the live Umbrel.
