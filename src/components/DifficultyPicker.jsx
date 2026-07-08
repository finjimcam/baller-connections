const LEVELS = [
  { id: 'easy', label: 'Easy' },
  { id: 'medium', label: 'Medium' },
  { id: 'hard', label: 'Hard' },
]

export default function DifficultyPicker({ value, onChange, onNewGame }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
      <div role="radiogroup" aria-label="Difficulty" className="flex gap-1.5">
        {LEVELS.map((level) => (
          <button
            key={level.id}
            role="radio"
            aria-checked={value === level.id}
            onClick={() => onChange(level.id)}
            className={`rounded-full border px-3.5 py-1 text-xs font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-pitch-300 active:scale-[0.97] ${
              value === level.id
                ? 'border-pitch-400 bg-pitch-700/80 text-pitch-50'
                : 'border-pitch-600/50 bg-pitch-900/60 text-pitch-300 hover:border-pitch-500 hover:text-pitch-100'
            }`}
          >
            {level.label}
          </button>
        ))}
      </div>
      <button
        onClick={onNewGame}
        className="rounded-full bg-pitch-500 px-4 py-1.5 text-xs font-semibold text-white shadow-soft transition-[transform,box-shadow] hover:shadow-lifted focus:outline-none focus-visible:ring-2 focus-visible:ring-pitch-300 active:scale-[0.97]"
      >
        New game
      </button>
    </div>
  )
}
