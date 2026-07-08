import { useState } from 'react'

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

/**
 * Circular player face bubble. Falls back to initials when the image proxy
 * has no portrait (204) or the file fails to load.
 */
export default function PlayerBubble({
  player,
  role = 'guess', // start | guess | target
  size = 92,
  showLabel = true,
  popIn = false,
  shake = false,
  className = '',
}) {
  const [imgFailed, setImgFailed] = useState(false)

  const ring =
    role === 'start'
      ? 'ring-[3px] ring-pitch-400'
      : role === 'target'
        ? 'ring-[3px] ring-pitch-300/80 ring-dashed'
        : 'ring-2 ring-pitch-200/40'

  return (
    <div
      className={`flex flex-col items-center select-none ${popIn ? 'animate-pop' : ''} ${
        shake ? 'animate-shake' : ''
      } ${className}`}
    >
      <div
        className={`relative overflow-hidden rounded-full bg-pitch-100 shadow-lifted ${ring}`}
        style={{ width: size, height: size, borderStyle: role === 'target' ? 'dashed' : undefined }}
      >
        {/* initials underneath double as the loading state and the fallback */}
        <div className="flex h-full w-full items-center justify-center bg-pitch-800 font-display text-2xl font-semibold text-pitch-200">
          {initials(player.name)}
        </div>
        {!imgFailed && player.image && (
          <>
            <img
              src={player.image}
              alt=""
              draggable={false}
              onError={() => setImgFailed(true)}
              className="absolute inset-0 h-full w-full object-cover object-top"
            />
            {/* colour treatment + depth per the design guardrails */}
            <div className="pointer-events-none absolute inset-0 bg-pitch-500/15 mix-blend-multiply" />
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-pitch-950/35 via-transparent to-transparent" />
          </>
        )}
      </div>
      {showLabel && (
        <div className="mt-1.5 max-w-[130px] text-center">
          <p className="truncate text-[13px] font-semibold leading-tight text-pitch-50 [text-shadow:0_1px_6px_rgba(10,36,25,0.9)]">
            {player.name}
          </p>
          {role !== 'guess' && (
            <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-pitch-300">
              {role === 'start' ? 'Start' : 'Target'}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
