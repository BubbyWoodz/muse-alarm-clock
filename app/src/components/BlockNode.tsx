import { memo } from 'react'
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { blockDef } from '../blockDefs'
import { BLOCK_ICONS } from '../icons'
import type { BlockType } from '../types'

// ---------------------------------------------------------------------------
// Custom react-flow node for an alarm-sequence block.
// Shows the block icon, label, and a one-line config summary.
// ---------------------------------------------------------------------------

export type BlockNodeData = {
  blockType: BlockType
  config: Record<string, any>
  running: boolean
  [key: string]: unknown
}

export type BlockNodeType = Node<BlockNodeData, 'block'>

function summarize(type: BlockType, config: Record<string, any>): string {
  switch (type) {
    case 'time_trigger':
      return config.mode === 'computed' || config.computed
        ? 'Computed alarm time'
        : `At ${config.time ?? '07:00'}`
    case 'button_trigger': {
      const mins = Math.round((config.timeoutSec ?? 600) / 60)
      return `On ${(config.button ?? 'middle')}-button press\n${mins}m timeout → escalation`
    }
    case 'alarm':
      return `${config.sound ?? 'sound.mp3'}\nVol ${config.volume ?? 70} — ${config.text ?? ''}`
    case 'page': {
      const lines: string[] = config.lines ?? []
      const cond = config.condition === 'work_day' ? '\nOnly on work days' : ''
      return `${lines.slice(0, 2).join('\n')}${lines.length > 2 ? '\n…' : ''}\n${config.durationSec ?? 10}s${cond}`
    }
    case 'audio':
      return `${config.file ?? 'audio.mp3'}\nVol ${config.volume ?? 50}`
    case 'wait':
      return `${config.seconds ?? 10} seconds`
    default:
      return ''
  }
}

function BlockNodeComponent({ data, selected }: NodeProps<BlockNodeType>) {
  const def = blockDef(data.blockType)
  const Icon = BLOCK_ICONS[data.blockType]
  return (
    <div
      className={`block-node${selected ? ' selected' : ''}${data.running ? ' running' : ''}`}
      style={{ ['--accent' as string]: def.accent }}
    >
      <Handle type="target" position={Position.Left} />
      <div className="head">
        <span className="chip">
          <Icon />
        </span>
        {def.label}
      </div>
      <div className="summary">{summarize(data.blockType, data.config)}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

export const BlockNode = memo(BlockNodeComponent)
