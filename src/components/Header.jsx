const MODES = [
  { id: 'daily', label: 'Daily' },
  { id: 'free', label: 'Free play' },
]

export default function Header({ mode, onModeChange, puzzle }) {
  return (
    <header className="flex flex-col items-center gap-4 pb-2 pt-8 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="font-display text-4xl font-semibold tracking-[-0.03em] text-pitch-50 sm:text-5xl">
          Baller Connections
        </h1>
        <p className="mt-1 text-sm leading-relaxed text-pitch-300">
          Link two footballers through the teammates they shared.
        </p>
      </div>
      <div className="flex items-center gap-3">
        {puzzle?.date && (
          <span className="hidden rounded-full border border-pitch-600/50 bg-pitch-900/60 px-3 py-1 text-xs font-medium text-pitch-300 sm:inline">
            {puzzle.date} · par {puzzle.par}
          </span>
        )}
        <div
          role="tablist"
          aria-label="Game mode"
          className="flex rounded-full border border-pitch-600/50 bg-pitch-900/70 p-1 shadow-soft"
        >
          {MODES.map((m) => (
            <button
              key={m.id}
              role="tab"
              aria-selected={mode === m.id}
              onClick={() => onModeChange(m.id)}
              className={`rounded-full px-4 py-1.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-pitch-300 active:scale-[0.97] ${
                mode === m.id
                  ? 'bg-pitch-500 text-white shadow-soft'
                  : 'text-pitch-300 hover:text-pitch-100'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
    </header>
  )
}
