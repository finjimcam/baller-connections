import { useEffect, useState } from 'react'
import ConnectionBadge from './ConnectionBadge'
import PlayerBubble from './PlayerBubble'

function RouteList({ title, route, connections, highlight = false }) {
  return (
    <div
      className={`rounded-2xl border p-4 ${
        highlight
          ? 'border-pitch-400/60 bg-pitch-800/60'
          : 'border-pitch-600/40 bg-pitch-900/60'
      }`}
    >
      <h3 className="mb-3 font-display text-lg font-semibold tracking-[-0.02em] text-pitch-100">
        {title}
      </h3>
      <ol className="space-y-1.5">
        {route.map((player, i) => (
          <li key={player.id}>
            <div className="flex items-center gap-3">
              <PlayerBubble player={player} size={40} showLabel={false} />
              <span className="text-sm font-semibold text-pitch-50">{player.name}</span>
            </div>
            {i < route.length - 1 && (
              <div className="ml-[13px] flex items-center gap-2 border-l-2 border-dotted border-pitch-600/70 py-1.5 pl-6">
                <ConnectionBadge links={connections[i]} compact />
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}

function nextDailyCountdown() {
  const now = new Date()
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1))
  const ms = next - now
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  return `${h}h ${m}m`
}

/**
 * Post-game panel: your route vs the shortest route, par comparison, and
 * play-again / next-daily actions.
 */
export default function WinScreen({ state, solution, onPlayAgain }) {
  const { status, mode, puzzle, chain, wrongCount } = state
  const [countdown, setCountdown] = useState(nextDailyCountdown())

  useEffect(() => {
    const timer = setInterval(() => setCountdown(nextDailyCountdown()), 30_000)
    return () => clearInterval(timer)
  }, [])

  const revealed = status === 'revealed'
  const yourSteps = chain.length - 1
  const par = solution?.length ?? puzzle.par
  const yourRoute = chain.map((entry) => entry.player)
  const yourConnections = chain.slice(1).map((entry) => entry.links)

  let verdict = null
  if (!revealed) {
    if (yourSteps <= par) verdict = 'Perfect — you matched the shortest route!'
    else verdict = `+${yourSteps - par} over the shortest route`
  }

  return (
    <div className="animate-rise mx-auto w-full max-w-3xl rounded-3xl border border-pitch-500/40 bg-pitch-900/90 p-6 shadow-lifted backdrop-blur-md sm:p-8">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-pitch-400">
        {revealed ? 'Route revealed' : 'Connection made'}
      </p>
      <h2 className="mt-1 font-display text-3xl font-semibold tracking-[-0.03em] text-pitch-50">
        {revealed
          ? `${puzzle.start.name} → ${puzzle.target.name}`
          : `${puzzle.start.name} → ${puzzle.target.name} in ${yourSteps} ${
              yourSteps === 1 ? 'step' : 'steps'
            }`}
      </h2>
      {verdict && <p className="mt-1.5 text-sm leading-relaxed text-pitch-300">{verdict}</p>}
      {!revealed && wrongCount > 0 && (
        <p className="mt-0.5 text-xs text-pitch-400">
          {wrongCount} wrong {wrongCount === 1 ? 'guess' : 'guesses'} along the way
        </p>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {!revealed && (
          <RouteList
            title={`Your route · ${yourSteps} ${yourSteps === 1 ? 'step' : 'steps'}`}
            route={yourRoute}
            connections={yourConnections}
          />
        )}
        {solution ? (
          <RouteList
            title={`Shortest route · ${solution.length} ${solution.length === 1 ? 'step' : 'steps'}`}
            route={solution.route}
            connections={solution.connections}
            highlight
          />
        ) : (
          <div className="flex items-center justify-center rounded-2xl border border-pitch-600/40 bg-pitch-900/60 p-8">
            <span
              className="h-6 w-6 animate-spin rounded-full border-2 border-pitch-600 border-t-pitch-300"
              aria-label="Loading shortest route"
            />
          </div>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        {mode === 'free' ? (
          <button
            onClick={onPlayAgain}
            className="rounded-full bg-pitch-500 px-5 py-2 text-sm font-semibold text-white shadow-soft transition-[transform,box-shadow] hover:shadow-lifted focus:outline-none focus-visible:ring-2 focus-visible:ring-pitch-300 active:scale-[0.97]"
          >
            Play again
          </button>
        ) : (
          <p className="text-sm text-pitch-300">
            Next daily puzzle in <span className="font-semibold text-pitch-100">{countdown}</span>
          </p>
        )}
      </div>
    </div>
  )
}
