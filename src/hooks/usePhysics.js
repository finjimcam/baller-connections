import { useEffect, useMemo, useRef, useState } from 'react'
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from 'd3-force'

export const BUBBLE_R = 46

const EDGE_PAD_TOP = 70
// bottom needs headroom for the name + role label hanging under the bubble
const EDGE_PAD_BOTTOM = 120
const POINTER_RADIUS = 190
const POINTER_STRENGTH = 0.55

/**
 * Spring-physics layout for the bubble chain.
 *
 * nodes:  [{ id, anchor: 'top' | 'bottom' | null }] in chain order (target last)
 * links:  [{ source, target, goal: bool }] — `goal` is the dashed hint link
 *
 * Bubbles are guided into a gentle vertical zigzag by weak positional springs,
 * attracted elastically toward the cursor, and draggable; the springs always
 * pull everything back. With prefers-reduced-motion the layout is static.
 */
export default function usePhysics({ nodes, links, width, height, reducedMotion }) {
  const [positions, setPositions] = useState({})
  const simRef = useRef(null)
  const liveNodesRef = useRef([])
  const pointerRef = useRef(null)
  const dragIdRef = useRef(null)

  const nodeKey = useMemo(() => nodes.map((n) => `${n.id}:${n.anchor || ''}`).join('|'), [nodes])

  useEffect(() => {
    if (!width || !height || nodes.length === 0) return undefined

    const innerH = Math.max(height - EDGE_PAD_TOP - EDGE_PAD_BOTTOM, 1)
    const denom = Math.max(nodes.length - 1, 1)
    const zigzag = Math.min(width * 0.16, 110)

    const previous = new Map(liveNodesRef.current.map((n) => [n.id, n]))
    const liveNodes = nodes.map((spec, i) => {
      const tx =
        width / 2 + (spec.anchor || nodes.length < 3 ? 0 : (i % 2 === 1 ? -zigzag : zigzag))
      const ty = EDGE_PAD_TOP + (i / denom) * innerH
      const old = previous.get(spec.id)
      const seedFrom = i > 0 ? previous.get(nodes[i - 1].id) : null
      return {
        id: spec.id,
        anchor: spec.anchor,
        tx,
        ty,
        x: old?.x ?? (seedFrom ? seedFrom.x + 30 : tx) + (Math.random() - 0.5) * 20,
        y: old?.y ?? (seedFrom ? seedFrom.y + 60 : ty),
        vx: old?.vx ?? 0,
        vy: old?.vy ?? 0,
      }
    })
    liveNodesRef.current = liveNodes

    if (reducedMotion) {
      simRef.current = null
      setPositions(Object.fromEntries(liveNodes.map((n) => [n.id, { x: n.tx, y: n.ty }])))
      return undefined
    }

    const liveLinks = links.map((l) => ({ ...l }))
    const segment = Math.max(90, Math.min(200, innerH / denom))

    const pointerForce = () => {
      const p = pointerRef.current
      if (!p) return
      for (const node of liveNodes) {
        if (node.id === dragIdRef.current) continue
        const dx = p.x - node.x
        const dy = p.y - node.y
        const dist = Math.hypot(dx, dy)
        if (dist > POINTER_RADIUS || dist < 1) continue
        const falloff = 1 - dist / POINTER_RADIUS
        const pull = falloff * falloff * POINTER_STRENGTH
        node.vx += (dx / dist) * pull * Math.min(dist, 40)
        node.vy += (dy / dist) * pull * Math.min(dist, 40)
      }
    }

    const sim = forceSimulation(liveNodes)
      .force(
        'link',
        forceLink(liveLinks)
          .id((d) => d.id)
          .distance((l) => (l.goal ? segment * 1.25 : segment))
          .strength((l) => (l.goal ? 0.05 : 0.5)),
      )
      .force('charge', forceManyBody().strength(-340))
      .force('collide', forceCollide().radius(BUBBLE_R + 16).strength(0.9))
      .force('x', forceX((d) => d.tx).strength((d) => (d.anchor ? 0.32 : 0.06)))
      .force('y', forceY((d) => d.ty).strength((d) => (d.anchor ? 0.4 : 0.16)))
      .force('pointer', pointerForce)
      .velocityDecay(0.32)
      .on('tick', () => {
        for (const node of liveNodes) {
          node.x = Math.max(BUBBLE_R + 8, Math.min(width - BUBBLE_R - 8, node.x))
          node.y = Math.max(BUBBLE_R + 8, Math.min(height - BUBBLE_R - 54, node.y))
        }
        setPositions(Object.fromEntries(liveNodes.map((n) => [n.id, { x: n.x, y: n.y }])))
      })

    sim.alpha(0.9).restart()
    simRef.current = sim
    return () => sim.stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeKey, width, height, reducedMotion])

  const wake = (target = 0.25) => {
    const sim = simRef.current
    if (!sim) return
    sim.alphaTarget(target)
    if (sim.alpha() < 0.1) sim.restart()
  }

  const rest = () => {
    simRef.current?.alphaTarget(0)
  }

  return {
    positions,
    setPointer(x, y) {
      pointerRef.current = { x, y }
      wake()
    },
    clearPointer() {
      pointerRef.current = null
      rest()
    },
    beginDrag(id, x, y) {
      dragIdRef.current = id
      const node = liveNodesRef.current.find((n) => n.id === id)
      if (node) {
        node.fx = x
        node.fy = y
      }
      wake(0.4)
    },
    dragTo(x, y) {
      const node = liveNodesRef.current.find((n) => n.id === dragIdRef.current)
      if (node) {
        node.fx = x
        node.fy = y
      }
    },
    endDrag() {
      const node = liveNodesRef.current.find((n) => n.id === dragIdRef.current)
      if (node) {
        node.fx = null
        node.fy = null
      }
      dragIdRef.current = null
      rest()
    },
  }
}
