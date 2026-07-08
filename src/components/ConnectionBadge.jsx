import { useState } from 'react'

/**
 * The label riding on an elastic link: shared club crest + name + seasons.
 * Renders the first shared stint and hints at extras ("+1 more").
 */
export default function ConnectionBadge({ links, compact = false }) {
  const [crestFailed, setCrestFailed] = useState(false)
  if (!links || links.length === 0) return null
  const first = links[0]
  const extra = links.length - 1

  return (
    <div
      className={`pointer-events-none flex items-center gap-1.5 rounded-full border border-pitch-500/40 bg-pitch-900/90 shadow-soft backdrop-blur-sm ${
        compact ? 'px-2 py-0.5' : 'px-2.5 py-1'
      }`}
    >
      {!crestFailed && (
        <img
          src={first.crest}
          alt=""
          onError={() => setCrestFailed(true)}
          className={compact ? 'h-3.5 w-3.5 object-contain' : 'h-4 w-4 object-contain'}
        />
      )}
      <span
        className={`whitespace-nowrap font-medium text-pitch-100 ${
          compact ? 'text-[10px]' : 'text-[11px]'
        }`}
      >
        {first.club_name}
        <span className="ml-1 text-pitch-300">{first.seasons.join(', ')}</span>
        {extra > 0 && <span className="ml-1 text-pitch-400">+{extra} more</span>}
      </span>
    </div>
  )
}
