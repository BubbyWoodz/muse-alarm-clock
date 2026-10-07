import { BLOCK_DEFS } from '../blockDefs'
import { BLOCK_ICONS, IconGrip } from '../icons'

// ---------------------------------------------------------------------------
// Left palette: draggable block types. Drag onto the canvas (or click to add
// at the viewport center). Uses native HTML5 drag-and-drop with a
// `application/x-block-type` payload that the canvas drop handler reads.
// ---------------------------------------------------------------------------

export function Palette({ onAdd }: { onAdd: (type: string) => void }) {
  return (
    <aside className="palette">
      <h3>Blocks</h3>
      <p className="hint">Drag onto the canvas, or click to add.</p>
      {BLOCK_DEFS.map((def) => {
        const Icon = BLOCK_ICONS[def.type]
        return (
          <button
            key={def.type}
            className="palette-item"
            style={{ ['--accent' as string]: def.accent }}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData('application/x-block-type', def.type)
              e.dataTransfer.effectAllowed = 'copy'
            }}
            onClick={() => onAdd(def.type)}
            title={def.description}
          >
            <span className="chip">
              <Icon />
            </span>
            <span>
              <div className="lbl">{def.label}</div>
              <div className="desc">{def.description}</div>
            </span>
            <span style={{ marginLeft: 'auto', color: 'var(--text-faint)' }}>
              <IconGrip />
            </span>
          </button>
        )
      })}
    </aside>
  )
}
