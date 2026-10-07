import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge as FlowEdge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { blockDef } from '../blockDefs'
import { IconBack, IconCheck, IconPlay, IconSave } from '../icons'
import { newId } from '../storage'
import type { Block, BlockType, Edge, Sequence } from '../types'
import { BlockNode, type BlockNodeType } from './BlockNode'
import { ConfigPanel } from './ConfigPanel'
import { Palette } from './Palette'

// ---------------------------------------------------------------------------
// Sequence editor: drag-drop canvas (react-flow) + palette + config panel.
// ---------------------------------------------------------------------------

const nodeTypes = { block: BlockNode }

interface Props {
  sequence: Sequence
  onSave: (seq: Sequence) => void
  onBack: () => void
}

function toNodes(blocks: Block[]): BlockNodeType[] {
  return blocks.map((b) => ({
    id: b.id,
    type: 'block',
    position: b.position,
    data: { blockType: b.type, config: b.config, running: false },
  }))
}

function toFlowEdges(edges: Edge[]): FlowEdge[] {
  return edges.map((e) => ({ id: e.id, source: e.from, target: e.to }))
}

function EditorInner({ sequence, onSave, onBack }: Props) {
  const [name, setName] = useState(sequence.name)
  const [blocks, setBlocks] = useState<Block[]>(sequence.blocks)
  const [nodes, setNodes, onNodesChange] = useNodesState<BlockNodeType>(toNodes(sequence.blocks))
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>(toFlowEdges(sequence.edges))
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [testState, setTestState] = useState<{ label: string } | null>(null)
  const { screenToFlowPosition } = useReactFlow()
  const timers = useRef<number[]>([])

  const selectedBlock = useMemo(
    () => blocks.find((b) => b.id === selectedId) ?? null,
    [blocks, selectedId],
  )

  const showToast = (msg: string) => {
    setToast(msg)
    window.setTimeout(() => setToast(null), 2600)
  }

  // Keep node data (config summary) in sync when block configs change.
  useEffect(() => {
    setNodes((ns) =>
      ns.map((n) => {
        const b = blocks.find((x) => x.id === n.id)
        if (!b) return n
        return { ...n, data: { ...n.data, blockType: b.type, config: b.config } }
      }),
    )
  }, [blocks, setNodes])

  const markDirty = () => setDirty(true)

  const addBlock = useCallback(
    (type: BlockType, at?: { x: number; y: number }) => {
      const def = blockDef(type)
      const id = newId('blk')
      const position = at ?? { x: 120 + Math.random() * 200, y: 120 + Math.random() * 200 }
      const block: Block = {
        id,
        type,
        config: JSON.parse(JSON.stringify(def.defaultConfig)),
        position,
      }
      setBlocks((bs) => [...bs, block])
      setNodes((ns) => [
        ...ns,
        { id, type: 'block', position, data: { blockType: type, config: block.config, running: false } },
      ])
      setSelectedId(id)
      markDirty()
    },
    [setNodes],
  )

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const type = e.dataTransfer.getData('application/x-block-type') as BlockType
      if (!type) return
      addBlock(type, screenToFlowPosition({ x: e.clientX, y: e.clientY }))
    },
    [addBlock, screenToFlowPosition],
  )

  const onConnect = useCallback(
    (conn: Connection) => {
      if (!conn.source || !conn.target || conn.source === conn.target) return
      setEdges((es) => {
        if (es.some((e) => e.source === conn.source && e.target === conn.target)) return es
        return addEdge({ ...conn, id: newId('edg') }, es)
      })
      markDirty()
    },
    [setEdges],
  )

  const patchBlock = useCallback((id: string, patch: Record<string, any>) => {
    setBlocks((bs) => bs.map((b) => (b.id === id ? { ...b, config: { ...b.config, ...patch } } : b)))
    markDirty()
  }, [])

  const deleteBlock = useCallback(
    (id: string) => {
      setBlocks((bs) => bs.filter((b) => b.id !== id))
      setNodes((ns) => ns.filter((n) => n.id !== id))
      setEdges((es) => es.filter((e) => e.source !== id && e.target !== id))
      setSelectedId(null)
      markDirty()
    },
    [setNodes, setEdges],
  )

  const handleSave = () => {
    // Sync drag positions from the canvas back into the blocks.
    setNodes((ns) => {
      const pos = new Map(ns.map((n) => [n.id, n.position]))
      setBlocks((bs) => bs.map((b) => ({ ...b, position: pos.get(b.id) ?? b.position })))
      return ns
    })
    // Read the latest blocks via a microtask to include position sync.
    window.setTimeout(() => {
      setBlocks((bs) => {
        const flowEdges: Edge[] = edges.map((e) => ({ id: e.id, from: e.source, to: e.target }))
        onSave({ ...sequence, name: name.trim() || 'Untitled', blocks: bs, edges: flowEdges, updatedAt: Date.now() })
        return bs
      })
      setDirty(false)
      showToast('Sequence saved')
    }, 0)
  }

  // --- test run: walk the flow from the trigger, highlighting each block ---
  const stopTest = () => {
    timers.current.forEach((t) => window.clearTimeout(t))
    timers.current = []
    setTestState(null)
    setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data, running: false } })))
  }

  const runTest = () => {
    stopTest()
    if (blocks.length === 0) {
      showToast('Add some blocks first')
      return
    }
    // Topological walk starting at trigger nodes (nodes with no incoming edges).
    const incoming = new Map<string, number>()
    const outgoing = new Map<string, string[]>()
    blocks.forEach((b) => {
      incoming.set(b.id, 0)
      outgoing.set(b.id, [])
    })
    edges.forEach((e) => {
      incoming.set(e.target, (incoming.get(e.target) ?? 0) + 1)
      outgoing.get(e.source)?.push(e.target)
    })
    const starts = blocks.filter((b) => (incoming.get(b.id) ?? 0) === 0)
    const order: Block[] = []
    const queue = [...(starts.length ? starts : [blocks[0]])]
    const seen = new Set<string>()
    while (queue.length) {
      const b = queue.shift()!
      if (seen.has(b.id)) continue
      seen.add(b.id)
      order.push(b)
      for (const next of outgoing.get(b.id) ?? []) {
        const nb = blocks.find((x) => x.id === next)
        if (nb && !seen.has(nb.id)) queue.push(nb)
      }
    }

    let t = 400
    order.forEach((b, i) => {
      const def = blockDef(b.type)
      timers.current.push(
        window.setTimeout(() => {
          setNodes((ns) =>
            ns.map((n) => ({ ...n, data: { ...n.data, running: n.id === b.id } })),
          )
          setTestState({ label: `${i + 1}/${order.length} — ${def.label}` })
        }, t),
      )
      t += 1400
    })
    timers.current.push(
      window.setTimeout(() => {
        stopTest()
        showToast('Test run complete')
      }, t),
    )
  }

  useEffect(() => () => stopTest(), []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="icon-btn" onClick={onBack} title="Back to dashboard">
          <IconBack />
        </button>
        <input
          className="seq-name-input"
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            markDirty()
          }}
          placeholder="Sequence name"
          aria-label="Sequence name"
        />
        {dirty && <span style={{ fontSize: 12, color: 'var(--text-faint)' }}>unsaved changes</span>}
        <span className="spacer" />
        <button className="btn" onClick={runTest} title="Simulate this sequence step by step">
          <IconPlay /> Test run
        </button>
        <button className="btn primary" onClick={handleSave}>
          <IconSave /> Save
        </button>
      </header>

      <div className="editor">
        <Palette onAdd={(t) => addBlock(t as BlockType)} />

        <div className="canvas-wrap">
          {testState && (
            <div className="test-banner">
              <IconCheck /> Test run: {testState.label}
            </div>
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={(c) => {
              onNodesChange(c)
              markDirty()
            }}
            onEdgesChange={(c) => {
              onEdgesChange(c)
              markDirty()
            }}
            onConnect={onConnect}
            onDrop={onDrop}
            onDragOver={(e) => {
              e.preventDefault()
              e.dataTransfer.dropEffect = 'copy'
            }}
            onNodeClick={(_, n) => setSelectedId(n.id)}
            onPaneClick={() => setSelectedId(null)}
            onEdgesDelete={() => markDirty()}
            fitView
            minZoom={0.4}
            deleteKeyCode={['Backspace', 'Delete']}
            onNodesDelete={(ns) => {
              const ids = new Set(ns.map((n) => n.id))
              setBlocks((bs) => bs.filter((b) => !ids.has(b.id)))
              setSelectedId(null)
              markDirty()
            }}
          >
            <Background gap={22} />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
        </div>

        <ConfigPanel block={selectedBlock} onChange={patchBlock} onDelete={deleteBlock} />
      </div>

      {toast && (
        <div className="toast">
          <IconCheck /> {toast}
        </div>
      )}
    </div>
  )
}

export function Editor(props: Props) {
  return (
    <ReactFlowProvider>
      <EditorInner {...props} />
    </ReactFlowProvider>
  )
}
