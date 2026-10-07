// ---------------------------------------------------------------------------
// Domain types for the Muse Alarm Clock sequence builder.
//
// These shapes are the contract the backend API will adopt later. The
// frontend persists them to localStorage for now; when the server lands,
// `storage.ts` gets swapped for fetch calls without changing components.
// ---------------------------------------------------------------------------

export type BlockType =
  | 'time_trigger'
  | 'button_trigger'
  | 'alarm'
  | 'page'
  | 'audio'
  | 'wait'

export interface Block {
  id: string
  type: BlockType
  /** Per-type configuration (see BLOCK_DEFS in blockDefs.ts for each schema). */
  config: Record<string, any>
  /** Canvas coordinates (react-flow units). */
  position: { x: number; y: number }
}

export interface Edge {
  id: string
  from: string
  to: string
}

export interface Sequence {
  id: string
  name: string
  enabled: boolean
  /** Who authored the sequence: the user, or Ryker (built-in templates). */
  author: 'user' | 'ryker'
  blocks: Block[]
  edges: Edge[]
  /** Unix ms of the last time this sequence was saved. */
  updatedAt: number
}

/** Human metadata for each block type (label, icon name, accent color, defaults). */
export interface BlockDef {
  type: BlockType
  label: string
  description: string
  /** Accent color used on the node border / icon chip. */
  accent: string
  defaultConfig: Record<string, any>
}
