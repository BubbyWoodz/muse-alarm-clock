import type { BlockType } from './types'
import type { BlockDef } from './types'

// ---------------------------------------------------------------------------
// Block catalog: the palette entries and their default configs.
// The accent colors are theme-agnostic (work on dark and light).
// ---------------------------------------------------------------------------

export const BLOCK_DEFS: BlockDef[] = [
  {
    type: 'time_trigger',
    label: 'Time Trigger',
    description: 'Start the flow at a fixed time or a computed alarm time',
    accent: '#7c6cf0',
    defaultConfig: { mode: 'fixed', time: '07:00', computed: false },
  },
  {
    type: 'button_trigger',
    label: 'Button Trigger',
    description: 'Continue on a physical clock button press — 10 min timeout triggers escalation',
    accent: '#3fa7ff',
    defaultConfig: { button: 'middle', timeoutSec: 600 },
  },
  {
    type: 'alarm',
    label: 'Alarm',
    description: 'Play a sound and show text until dismissed',
    accent: '#ff5d5d',
    defaultConfig: { sound: 'morning-chime.mp3', volume: 70, text: 'Good morning!' },
  },
  {
    type: 'page',
    label: 'Page',
    description: 'Show text lines on the clock display',
    accent: '#38c172',
    defaultConfig: { lines: ['Good Morning Rhy'], durationSec: 10, fontSize: 16 },
  },
  {
    type: 'audio',
    label: 'Audio',
    description: 'Play an MP3 file on the clock speaker',
    accent: '#f0a13c',
    defaultConfig: { file: 'lofi-01.mp3', volume: 50 },
  },
  {
    type: 'wait',
    label: 'Wait',
    description: 'Pause the flow for a number of seconds',
    accent: '#9aa3b2',
    defaultConfig: { seconds: 10 },
  },
]

export function blockDef(type: BlockType): BlockDef {
  const def = BLOCK_DEFS.find((d) => d.type === type)
  if (!def) throw new Error(`unknown block type: ${type}`)
  return def
}

export const BUTTON_OPTIONS = ['left', 'middle', 'right'] as const

/** Mock sound library — replaced by the device file listing later. */
export const SOUND_LIBRARY = [
  'morning-chime.mp3',
  'gentle-wake.mp3',
  'lofi-01.mp3',
  'lofi-02.mp3',
  'iphone-alarm-max.mp3',
  'wind-down.mp3',
]
