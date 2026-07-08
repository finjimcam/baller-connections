import { useEffect, useMemo, useRef, useState } from 'react'
import usePhysics, { BUBBLE_R } from '../hooks/usePhysics'
import ConnectionBadge from './ConnectionBadge'
import PlayerBubble from './PlayerBubble'

function useReducedMotion() {
  const [reduced, setReduced] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = (e) => setReduced(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

function linkPath(a, b, index) {
  // Slightly bowed quadratic so the "rope" reads as elastic, not rigid.
  const mx = (a.x + b.x) / 2
  const my = (a.y + b.y) / 2
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  const bow = Math.min(len * 0.12, 26) * (index % 2 === 0 ? 1 : -1)
  const cx = mx + (-dy / len) * bow
  const cy = my + (dx / len) * bow
  // badge anchor: point on the curve biased toward the newer (lower) bubble so
  // it clears the previous bubble's name label
  const t = 0.62
  const badge = {
    x: (1 - t) ** 2 * a.x + 2 * (1 - t) * t * cx + t ** 2 * b.x,
    y: (1 - t) ** 2 * a.y + 2 * (1 - t) * t * cy + t ** 2 * b.y,
  }
  return { d: `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`, mid: { x: cx, y: cy }, badge }
}

/**
 * The physics board: player bubbles joined by elastic links, guided into a
 * vertical chain, attracted by the cursor, and draggable.
 */
export default function BubbleBoard({ chain, target, status, wrongGuess }) {
  const containerRef = useRef(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const reducedMotion = useReducedMotion()

  const targetReached = chain.some((entry) => entry.player.id === target.id)
  const showGoalNode = !targetReached

  const boardHeight = Math.max(540, (chain.length + (showGoalNode ? 1 : 0)) * 160)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return undefined
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0].contentRect
      setSize({ width: rect.width, height: rect.height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const nodes = useMemo(() => {
    const list = chain.map((entry, i) => ({
      id: entry.player.id,
      anchor: i === 0 ? 'top' : entry.player.id === target.id ? 'bottom' : null,
    }))
    if (showGoalNode) list.push({ id: target.id, anchor: 'bottom' })
    return list
  }, [chain, target.id, showGoalNode])

  const links = useMemo(() => {
    const list = chain.slice(1).map((entry, i) => ({
      source: chain[i].player.id,
      target: entry.player.id,
      goal: false,
    }))
    if (showGoalNode) {
      list.push({ source: chain[chain.length - 1].player.id, target: target.id, goal: true })
    }
    return list
  }, [chain, target.id, showGoalNode])

  const physics = usePhysics({
    nodes,
    links,
    width: size.width,
    height: size.height,
    reducedMotion,
  })
  const { positions } = physics

  const toLocal = (e) => {
    const rect = containerRef.current.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  const draggingRef = useRef(false)

  const playersById = useMemo(() => {
    const map = new Map(chain.map((entry) => [entry.player.id, entry.player]))
    map.set(target.id, target)
    return map
  }, [chain, target])

  const ready = size.width > 0 && Object.keys(positions).length > 0

  return (
    <div
      ref={containerRef}
      className="relative w-full touch-none overflow-hidden"
      style={{ height: boardHeight }}
      onPointerMove={(e) => {
        const p = toLocal(e)
        if (draggingRef.current) physics.dragTo(p.x, p.y)
        else physics.setPointer(p.x, p.y)
      }}
      onPointerLeave={() => {
        physics.clearPointer()
        if (draggingRef.current) {
          physics.endDrag()
          draggingRef.current = false
        }
      }}
      onPointerUp={() => {
        if (draggingRef.current) {
          physics.endDrag()
          draggingRef.current = false
        }
      }}
    >
      {ready && (
        <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
          {links.map((link, i) => {
            const a = positions[link.source]
            const b = positions[link.target]
            if (!a || !b) return null
            const { d } = linkPath(a, b, i)
            return link.goal ? (
              <path
                key="goal"
                d={d}
                fill="none"
                stroke="#4fb17f"
                strokeOpacity="0.35"
                strokeWidth="2"
                strokeDasharray="3 9"
                strokeLinecap="round"
              />
            ) : (
              <path
                key={`${link.source}-${link.target}`}
                d={d}
                fill="none"
                stroke="#2d9463"
                strokeOpacity="0.75"
                strokeWidth="3"
                strokeLinecap="round"
              />
            )
          })}
        </svg>
      )}

      {/* connection badges ride each solved link's midpoint */}
      {ready &&
        chain.slice(1).map((entry, i) => {
          const a = positions[chain[i].player.id]
          const b = positions[entry.player.id]
          if (!a || !b || !entry.links) return null
          const { badge } = linkPath(a, b, i)
          return (
            <div
              key={`badge-${entry.player.id}`}
              className="absolute left-0 top-0 z-10"
              style={{
                transform: `translate3d(${badge.x}px, ${badge.y}px, 0) translate(-50%, -50%)`,
              }}
            >
              <ConnectionBadge links={entry.links} />
            </div>
          )
        })}

      {/* goal hint on the dashed link */}
      {ready && showGoalNode && (
        (() => {
          const a = positions[chain[chain.length - 1].player.id]
          const b = positions[target.id]
          if (!a || !b) return null
          return (
            <div
              className="absolute left-0 top-0"
              style={{
                transform: `translate3d(${(a.x + b.x) / 2}px, ${(a.y + b.y) / 2}px, 0) translate(-50%, -50%)`,
              }}
            >
              <span className="rounded-full border border-pitch-500/30 bg-pitch-900/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-pitch-400">
                find the link
              </span>
            </div>
          )
        })()
      )}

      {ready &&
        nodes.map((node, i) => {
          const pos = positions[node.id]
          if (!pos) return null
          const player = playersById.get(node.id)
          if (!player) return null
          const isTargetNode = node.id === target.id
          const role = i === 0 ? 'start' : isTargetNode ? 'target' : 'guess'
          const isLastGuess = !isTargetNode && i === chain.length - 1 && i > 0
          const shakeKey = isLastGuess && wrongGuess ? wrongGuess.nonce : 'still'
          return (
            <div
              key={node.id}
              className="absolute left-0 top-0 z-20 cursor-grab will-change-transform active:cursor-grabbing"
              style={{
                transform: `translate3d(${pos.x}px, ${pos.y}px, 0) translate(-50%, -${BUBBLE_R}px)`,
              }}
              onPointerDown={(e) => {
                e.currentTarget.setPointerCapture?.(e.pointerId)
                const p = toLocal(e)
                physics.beginDrag(node.id, p.x, p.y)
                draggingRef.current = true
              }}
            >
              <div key={shakeKey} className={isLastGuess && wrongGuess ? 'animate-shake' : ''}>
                <PlayerBubble
                  player={player}
                  role={role}
                  size={BUBBLE_R * 2}
                  popIn={role === 'guess'}
                />
              </div>
            </div>
          )
        })}

      {status === 'playing' && wrongGuess && (
        <div className="pointer-events-none absolute bottom-3 left-1/2 z-30 -translate-x-1/2">
          <p
            key={wrongGuess.nonce}
            className="animate-rise whitespace-nowrap rounded-full border border-red-400/30 bg-red-950/80 px-4 py-1.5 text-sm font-medium text-red-200 shadow-soft"
          >
            {wrongGuess.message}
          </p>
        </div>
      )}
    </div>
  )
}
