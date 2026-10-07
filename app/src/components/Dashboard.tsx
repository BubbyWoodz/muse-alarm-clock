import { useState } from 'react'
import { IconClock, IconPencil, IconPerson, IconPlus, IconSpark, IconTrash } from '../icons'
import { newId } from '../storage'
import type { Sequence } from '../types'

// ---------------------------------------------------------------------------
// Dashboard: grid of sequence cards + "New Sequence".
// Cards show name, enabled toggle, next-run hint, author badge, edit/delete.
// ---------------------------------------------------------------------------

interface Props {
  sequences: Sequence[]
  onToggle: (id: string) => void
  onDelete: (id: string) => void
  onEdit: (id: string) => void
  onCreate: (seq: Sequence) => void
}

function nextRunLabel(seq: Sequence): string {
  if (!seq.enabled) return 'Paused'
  const trigger = seq.blocks.find((b) => b.type === 'time_trigger')
  if (!trigger) return 'No trigger'
  if (trigger.config.mode === 'computed' || trigger.config.computed) return 'Computed nightly'
  const t = trigger.config.time ?? '07:00'
  const [h, m] = t.split(':').map(Number)
  const now = new Date()
  const next = new Date(now)
  next.setHours(h, m, 0, 0)
  const label = next <= now ? 'Tomorrow' : 'Today'
  return `${label} ${t}`
}

function AuthorBadge({ author }: { author: 'user' | 'ryker' }) {
  const isRyker = author === 'ryker'
  return (
    <span className={`author-badge${isRyker ? ' ryker' : ''}`} title={isRyker ? 'Built by Ryker' : 'Created by you'}>
      {isRyker ? <IconSpark /> : <IconPerson />}
      {isRyker ? 'Ryker' : 'You'}
    </span>
  )
}

export function Dashboard({ sequences, onToggle, onDelete, onEdit, onCreate }: Props) {
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const createNew = () => {
    const seq: Sequence = {
      id: newId('seq'),
      name: 'Untitled Sequence',
      enabled: true,
      author: 'user',
      blocks: [],
      edges: [],
      updatedAt: Date.now(),
    }
    onCreate(seq)
  }

  return (
    <div className="dashboard">
      <h1>Sequences</h1>
      <p className="sub">Alarm flows for your clock. Toggle them on, or open one to edit the timeline.</p>

      <div className="seq-grid">
        {sequences.map((seq) => (
          <div key={seq.id} className={`seq-card${seq.enabled ? '' : ' disabled'}`}>
            <div className="row">
              <p className="name">{seq.name}</p>
              <button
                className="toggle"
                role="switch"
                aria-checked={seq.enabled}
                aria-label={`Enable ${seq.name}`}
                onClick={() => onToggle(seq.id)}
              />
            </div>
            <div className="row">
              <span className="meta">
                <IconClock /> {nextRunLabel(seq)}
              </span>
              <AuthorBadge author={seq.author ?? 'user'} />
            </div>
            <div className="meta">{seq.blocks.length} blocks</div>
            <div className="actions">
              <button className="btn" onClick={() => onEdit(seq.id)} style={{ flex: 1, justifyContent: 'center' }}>
                <IconPencil /> Edit
              </button>
              {confirmDelete === seq.id ? (
                <button
                  className="btn danger"
                  onClick={() => {
                    onDelete(seq.id)
                    setConfirmDelete(null)
                  }}
                >
                  Confirm
                </button>
              ) : (
                <button className="btn icon-only danger" onClick={() => setConfirmDelete(seq.id)} title="Delete">
                  <IconTrash />
                </button>
              )}
            </div>
          </div>
        ))}

        <button className="new-card" onClick={createNew}>
          <IconPlus />
          New Sequence
        </button>
      </div>
    </div>
  )
}
