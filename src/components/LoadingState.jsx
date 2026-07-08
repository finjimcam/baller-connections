export default function LoadingState() {
  return (
    <div className="flex flex-col items-center gap-8 py-24" aria-label="Loading puzzle">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex flex-col items-center gap-2">
          <div
            className="h-[88px] w-[88px] animate-pulse rounded-full bg-pitch-800/80"
            style={{ animationDelay: `${i * 150}ms` }}
          />
          <div
            className="h-3 w-20 animate-pulse rounded-full bg-pitch-800/60"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        </div>
      ))}
    </div>
  )
}
