import type { Block, Sequence } from './types'

// ---------------------------------------------------------------------------
// Persistence layer. localStorage for now; swap for API calls later without
// touching components. All functions are synchronous on purpose.
// ---------------------------------------------------------------------------

const KEY = 'muse-alarm-sequences-v1'

function uid(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

export const newId = (prefix: string) => uid(prefix)

function seedSequences(): Sequence[] {
  const now = Date.now()

  // The default "Wake Up Sequence" template — Christian's exact morning flow.
  // 1. computed time trigger → 2. alarm → 3. middle-button dismiss →
  // 4-8. the post-dismiss page chain.
  const t1 = newId('blk') // time trigger (computed)
  const a1 = newId('blk') // alarm (sound + WAKE UP)
  const bt = newId('blk') // button trigger (middle = "I'm up")
  const p1 = newId('blk') // good morning page
  const p2 = newId('blk') // date/time + weather page
  const p3 = newId('blk') // wake reason page
  const p4 = newId('blk') // work shift page (work days only)
  const p5 = newId('blk') // handoff page

  const wake: Sequence = {
    id: newId('seq'),
    name: 'Wake Up Sequence',
    enabled: true,
    author: 'ryker',
    updatedAt: now,
    blocks: [
      { id: t1, type: 'time_trigger', config: { mode: 'computed', computed: true }, position: { x: 60, y: 180 } },
      { id: a1, type: 'alarm', config: { sound: 'morning-chime.mp3', volume: 70, text: 'WAKE UP' }, position: { x: 320, y: 180 } },
      { id: bt, type: 'button_trigger', config: { button: 'middle', timeoutSec: 600 }, position: { x: 580, y: 180 } },
      { id: p1, type: 'page', config: { lines: ['Good Morning Rhy', ':)'], durationSec: 10, fontSize: 16 }, position: { x: 840, y: 60 } },
      { id: p2, type: 'page', config: { lines: ['Tue Oct 7', '10:38 AM', '72F Sunny'], durationSec: 10, fontSize: 14 }, position: { x: 840, y: 300 } },
      { id: p3, type: 'page', config: { lines: ['Wake reason', 'Work — 2:00 PM shift'], durationSec: 10, fontSize: 14 }, position: { x: 1100, y: 60 } },
      { id: p4, type: 'page', config: { lines: ['Work 2:00 PM – 11:00 PM', 'Tustin — Merch Sales'], durationSec: 10, fontSize: 14, condition: 'work_day' }, position: { x: 1100, y: 300 } },
      { id: p5, type: 'page', config: { lines: ['Your 1440 waits for you'], durationSec: 10, fontSize: 14 }, position: { x: 1360, y: 180 } },
    ],
    edges: [
      { id: newId('edg'), from: t1, to: a1 },
      { id: newId('edg'), from: a1, to: bt },
      { id: newId('edg'), from: bt, to: p1 },
      { id: newId('edg'), from: bt, to: p2 },
      { id: newId('edg'), from: p1, to: p3 },
      { id: newId('edg'), from: p2, to: p4 },
      { id: newId('edg'), from: p3, to: p5 },
      { id: newId('edg'), from: p4, to: p5 },
    ],
  }

  const wind: Sequence = {
    id: newId('seq'),
    name: 'Wind Down',
    enabled: false,
    author: 'ryker',
    updatedAt: now,
    blocks: [
      { id: newId('blk'), type: 'time_trigger', config: { mode: 'computed', computed: true }, position: { x: 60, y: 180 } },
      { id: newId('blk'), type: 'audio', config: { file: 'lofi-01.mp3', volume: 40 }, position: { x: 320, y: 180 } },
      { id: newId('blk'), type: 'page', config: { lines: ['Wind down', 'See you at 7:00'], durationSec: 10, fontSize: 14 }, position: { x: 580, y: 180 } },
    ] as Block[],
    edges: [],
  }
  // wire the wind-down chain
  wind.edges = [
    { id: newId('edg'), from: wind.blocks[0].id, to: wind.blocks[1].id },
    { id: newId('edg'), from: wind.blocks[1].id, to: wind.blocks[2].id },
  ]

  return [wake, wind]
}

export function loadSequences(): Sequence[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) {
      const seeded = seedSequences()
      saveSequences(seeded)
      return seeded
    }
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) throw new Error('bad shape')
    // Backfill: sequences persisted before the author field existed.
    return (parsed as Sequence[]).map((s) => ({
      ...s,
      author: s.author ?? 'ryker',
    }))
  } catch {
    const seeded = seedSequences()
    saveSequences(seeded)
    return seeded
  }
}

export function saveSequences(seqs: Sequence[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(seqs))
  } catch {
    // storage full / private mode — the app keeps working in-memory
  }
}
