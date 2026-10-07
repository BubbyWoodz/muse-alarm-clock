# Muse Alarm Clock — Sequence Builder (frontend)

Visual drag-and-drop workflow editor for alarm sequences. Users build
"Sequence" cards (e.g. **Wake Up Sequence**), each a flowchart of blocks
connected by arrows. The app ships with the Wake Up Sequence template
pre-built so the workflow is visible on first load.

**Stack:** React 19 + Vite 6 + TypeScript, [@xyflow/react](https://reactflow.dev)
for the canvas. No backend — state persists to `localStorage` for now; the
TypeScript interfaces in `src/types.ts` are the contract the server API will
adopt later.

## Run it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # typecheck + production build
```

## Structure

```
src/
  main.tsx            entry point (imports styles + App)
  App.tsx             shell: dashboard <-> editor routing, theme toggle, store
  types.ts            Sequence / Block / Edge interfaces (API contract)
  blockDefs.ts        block catalog: labels, accent colors, default configs
  storage.ts          localStorage persistence + default templates
  icons.tsx           inline SVG icon set (theme-aware via currentColor)
  styles.css          dark-first theme tokens + all component styles
  components/
    Dashboard.tsx     sequence card grid (toggle, next-run, author, edit/delete)
    Editor.tsx        react-flow canvas: drop/connect/configure/test-run
    Palette.tsx       draggable block-type palette
    ConfigPanel.tsx   per-type config editors for the selected block
    BlockNode.tsx     custom flow node (icon, label, config summary)
```

## Block types

| Type | Purpose |
|---|---|
| Time Trigger | Start at a fixed `HH:MM` or a nightly-computed alarm time |
| Button Trigger | Continue on a physical clock button press (10 min timeout → escalation) |
| Alarm | Play a sound + show text until dismissed |
| Page | Show text lines on the display for N seconds |
| Audio | Play an MP3 file on the clock speaker |
| Wait | Pause the flow for N seconds |

## Notes

- No emojis anywhere in the UI; all icons are inline SVG that adapt to the
  theme through CSS variables.
- The author badge on each card shows **You** (person icon) for sequences you
  create and **Ryker** (spark icon) for built-in templates.
- `storage.ts` is the seam for the backend: swap its functions for `fetch`
  calls without touching components.
