/**
 * Friendly failure panel. When the backend is fine but the database is empty
 * (fresh checkout, no backfill yet) it explains the setup step instead of
 * showing a generic error.
 */
export default function ErrorState({ message, emptyDatabase, onRetry }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 rounded-3xl border border-pitch-600/40 bg-pitch-900/70 px-8 py-12 text-center shadow-soft">
      <span className="text-3xl" aria-hidden="true">
        {emptyDatabase ? '🌱' : '⚠️'}
      </span>
      {emptyDatabase ? (
        <>
          <h2 className="font-display text-xl font-semibold tracking-[-0.02em] text-pitch-100">
            No player data yet
          </h2>
          <p className="text-sm leading-relaxed text-pitch-300">
            The database is empty. Seed it by running the ingest backfill:
          </p>
          <code className="rounded-lg bg-pitch-950/80 px-3 py-2 text-xs text-pitch-200">
            docker compose exec -d backend uv run python -m app.ingest backfill
          </code>
        </>
      ) : (
        <>
          <h2 className="font-display text-xl font-semibold tracking-[-0.02em] text-pitch-100">
            Something went wrong
          </h2>
          <p className="text-sm leading-relaxed text-pitch-300">{message}</p>
        </>
      )}
      <button
        onClick={onRetry}
        className="mt-2 rounded-full bg-pitch-500 px-5 py-2 text-sm font-semibold text-white shadow-soft transition-[transform,box-shadow] hover:shadow-lifted focus:outline-none focus-visible:ring-2 focus-visible:ring-pitch-300 active:scale-[0.97]"
      >
        Try again
      </button>
    </div>
  )
}
