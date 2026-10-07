import { BLOCK_DEFS, BUTTON_OPTIONS, SOUND_LIBRARY, blockDef } from '../blockDefs'
import { BLOCK_ICONS, IconTrash } from '../icons'
import type { Block, BlockType } from '../types'

// ---------------------------------------------------------------------------
// Right panel: edit the selected block's config. Field editors are driven by
// block type; changes propagate up via onChange (patch semantics).
// ---------------------------------------------------------------------------

interface Props {
  block: Block | null
  onChange: (id: string, patch: Record<string, any>) => void
  onDelete: (id: string) => void
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  )
}

export function ConfigPanel({ block, onChange, onDelete }: Props) {
  if (!block) {
    return (
      <aside className="config-panel">
        <div className="empty-panel">
          Select a block on the canvas
          <br />
          to edit its settings.
        </div>
      </aside>
    )
  }

  const def = blockDef(block.type)
  const Icon = BLOCK_ICONS[block.type]
  const cfg = block.config
  const set = (patch: Record<string, any>) => onChange(block.id, patch)

  return (
    <aside className="config-panel">
      <h3>
        <span
          style={{
            display: 'inline-flex',
            color: def.accent,
            width: 22,
            height: 22,
          }}
        >
          <Icon />
        </span>
        {def.label}
      </h3>
      <div className="type-lbl">{def.description}</div>

      {block.type === 'time_trigger' && (
        <>
          <Field label="Trigger mode">
            <select
              value={cfg.mode === 'computed' || cfg.computed ? 'computed' : 'fixed'}
              onChange={(e) => {
                const computed = e.target.value === 'computed'
                set({ mode: e.target.value, computed })
              }}
            >
              <option value="fixed">Fixed time</option>
              <option value="computed">Computed (dynamic alarm)</option>
            </select>
          </Field>
          {!(cfg.mode === 'computed' || cfg.computed) && (
            <Field label="Time">
              <input
                type="time"
                value={cfg.time ?? '07:00'}
                onChange={(e) => set({ time: e.target.value })}
              />
            </Field>
          )}
        </>
      )}

      {block.type === 'button_trigger' && (
        <>
          <Field label="Button">
            <select value={cfg.button ?? 'middle'} onChange={(e) => set({ button: e.target.value })}>
              {BUTTON_OPTIONS.map((b) => (
                <option key={b} value={b}>
                  {b[0].toUpperCase() + b.slice(1)} button
                </option>
              ))}
            </select>
          </Field>
          <Field label="Timeout (seconds) — then escalate">
            <input
              type="number"
              min={0}
              max={3600}
              value={cfg.timeoutSec ?? 600}
              onChange={(e) => set({ timeoutSec: Number(e.target.value) })}
            />
          </Field>
        </>
      )}

      {block.type === 'alarm' && (
        <>
          <Field label="Sound file">
            <select value={cfg.sound ?? ''} onChange={(e) => set({ sound: e.target.value })}>
              {SOUND_LIBRARY.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label={`Volume (${cfg.volume ?? 70}%)`}>
            <input
              type="range"
              min={0}
              max={100}
              value={cfg.volume ?? 70}
              onChange={(e) => set({ volume: Number(e.target.value) })}
            />
          </Field>
          <Field label="Display text">
            <input
              value={cfg.text ?? ''}
              onChange={(e) => set({ text: e.target.value })}
              placeholder="Good morning!"
            />
          </Field>
        </>
      )}

      {block.type === 'page' && (
        <>
          <Field label="Text lines (one per line)">
            <textarea
              value={(cfg.lines ?? []).join('\n')}
              onChange={(e) => set({ lines: e.target.value.split('\n') })}
            />
          </Field>
          <div className="row" style={{ display: 'flex', gap: 8 }}>
            <Field label="Duration (s)">
              <input
                type="number"
                min={1}
                max={120}
                value={cfg.durationSec ?? 10}
                onChange={(e) => set({ durationSec: Number(e.target.value) })}
              />
            </Field>
            <Field label="Font size">
              <input
                type="number"
                min={8}
                max={32}
                value={cfg.fontSize ?? 16}
                onChange={(e) => set({ fontSize: Number(e.target.value) })}
              />
            </Field>
          </div>
        </>
      )}

      {block.type === 'audio' && (
        <>
          <Field label="MP3 file">
            <select value={cfg.file ?? ''} onChange={(e) => set({ file: e.target.value })}>
              {SOUND_LIBRARY.filter((s) => s.endsWith('.mp3')).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label={`Volume (${cfg.volume ?? 50}%)`}>
            <input
              type="range"
              min={0}
              max={100}
              value={cfg.volume ?? 50}
              onChange={(e) => set({ volume: Number(e.target.value) })}
            />
          </Field>
        </>
      )}

      {block.type === 'wait' && (
        <Field label="Seconds">
          <input
            type="number"
            min={1}
            max={3600}
            value={cfg.seconds ?? 10}
            onChange={(e) => set({ seconds: Number(e.target.value) })}
          />
        </Field>
      )}

      <div style={{ marginTop: 20 }}>
        <button className="btn danger" onClick={() => onDelete(block.id)} style={{ width: '100%', justifyContent: 'center' }}>
          <IconTrash /> Delete block
        </button>
      </div>

      <div style={{ marginTop: 16, fontSize: 11.5, color: 'var(--text-faint)' }}>
        Block id: <code>{block.id}</code>
        <br />
        Type: <code>{block.type satisfies BlockType}</code>
        <br />
        Available types: {BLOCK_DEFS.map((d) => d.type).join(', ')}
      </div>
    </aside>
  )
}
