import { useEffect, useState } from 'react'
import { Dashboard } from './components/Dashboard'
import { Editor } from './components/Editor'
import { IconMoon, IconSun } from './icons'
import { loadSequences, saveSequences } from './storage'
import type { Sequence } from './types'

// ---------------------------------------------------------------------------
// App shell: dashboard <-> editor routing, theme toggle, sequence store.
// The store lives here; storage.ts persists to localStorage (API later).
// ---------------------------------------------------------------------------

type View = { name: 'dashboard' } | { name: 'editor'; seqId: string }

function themeInit(): 'dark' | 'light' {
  const saved = localStorage.getItem('muse-alarm-theme')
  return saved === 'light' ? 'light' : 'dark'
}

export function App() {
  const [sequences, setSequences] = useState<Sequence[]>(() => loadSequences())
  const [view, setView] = useState<View>({ name: 'dashboard' })
  const [theme, setTheme] = useState<'dark' | 'light'>(themeInit)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('muse-alarm-theme', theme)
  }, [theme])

  const persist = (next: Sequence[]) => {
    setSequences(next)
    saveSequences(next)
  }

  const activeSeq =
    view.name === 'editor' ? sequences.find((s) => s.id === view.seqId) ?? null : null

  return (
    <div className="app-shell">
      {view.name === 'dashboard' && (
        <>
          <header className="topbar">
            <span className="brand">
              <span className="logo">
                <IconMoon />
              </span>
              Muse Alarm Clock
            </span>
            <span className="spacer" />
            <button
              className="icon-btn"
              onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {theme === 'dark' ? <IconSun /> : <IconMoon />}
            </button>
          </header>
          <Dashboard
            sequences={sequences}
            onToggle={(id) =>
              persist(sequences.map((s) => (s.id === id ? { ...s, enabled: !s.enabled, updatedAt: Date.now() } : s)))
            }
            onDelete={(id) => persist(sequences.filter((s) => s.id !== id))}
            onEdit={(id) => setView({ name: 'editor', seqId: id })}
            onCreate={(seq) => {
              persist([...sequences, seq])
              setView({ name: 'editor', seqId: seq.id })
            }}
          />
        </>
      )}

      {view.name === 'editor' && activeSeq && (
        <Editor
          sequence={activeSeq}
          onSave={(seq) => persist(sequences.map((s) => (s.id === seq.id ? seq : s)))}
          onBack={() => setView({ name: 'dashboard' })}
        />
      )}
    </div>
  )
}
