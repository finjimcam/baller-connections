import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import useDebounce from '../hooks/useDebounce'

/**
 * ARIA combobox over /api/players/search: type a player, pick with mouse or
 * arrow keys, and the selection is validated against the end of the chain.
 */
export default function GuessInput({ lastPlayer, onGuess, disabled, validating }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [searching, setSearching] = useState(false)
  const debounced = useDebounce(query, 250)
  const inputRef = useRef(null)
  const rootRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    const q = debounced.trim()
    if (q.length < 2) {
      setResults([])
      setOpen(false)
      return undefined
    }
    setSearching(true)
    api
      .search(q)
      .then((rows) => {
        if (cancelled) return
        setResults(rows)
        setOpen(true)
        setActive(rows.length ? 0 : -1)
      })
      .catch(() => {
        if (!cancelled) setResults([])
      })
      .finally(() => {
        if (!cancelled) setSearching(false)
      })
    return () => {
      cancelled = true
    }
  }, [debounced])

  useEffect(() => {
    const onClickAway = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', onClickAway)
    return () => document.removeEventListener('pointerdown', onClickAway)
  }, [])

  const pick = (row) => {
    setQuery('')
    setResults([])
    setOpen(false)
    onGuess(row)
    inputRef.current?.focus()
  }

  const onKeyDown = (e) => {
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => (a + 1) % results.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => (a - 1 + results.length) % results.length)
    } else if (e.key === 'Enter' && active >= 0) {
      e.preventDefault()
      pick(results[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div ref={rootRef} className="relative w-full max-w-xl">
      <label htmlFor="guess-input" className="sr-only">
        Guess a teammate of {lastPlayer?.name}
      </label>
      <div className="flex items-center gap-2 rounded-2xl border border-pitch-600/50 bg-pitch-900/80 px-4 py-3 shadow-lifted backdrop-blur-sm transition-shadow focus-within:border-pitch-400 focus-within:shadow-[0_0_0_3px_rgba(79,177,127,0.25),0_8px_24px_rgba(10,36,25,0.4)]">
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4 shrink-0 text-pitch-400" aria-hidden="true">
          <path
            fillRule="evenodd"
            d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.45 4.4l3.07 3.08a.75.75 0 1 1-1.06 1.06l-3.07-3.07A7 7 0 0 1 2 9Z"
            clipRule="evenodd"
          />
        </svg>
        <input
          id="guess-input"
          ref={inputRef}
          role="combobox"
          aria-expanded={open}
          aria-controls="guess-listbox"
          aria-activedescendant={active >= 0 ? `guess-option-${active}` : undefined}
          aria-autocomplete="list"
          autoComplete="off"
          disabled={disabled}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={
            lastPlayer ? `Who played with ${lastPlayer.name}?` : 'Search for a player…'
          }
          className="w-full bg-transparent text-[15px] text-pitch-50 placeholder:text-pitch-400/80 focus:outline-none disabled:opacity-50"
        />
        {(searching || validating) && (
          <span
            className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-pitch-500 border-t-pitch-200"
            aria-hidden="true"
          />
        )}
      </div>

      {open && (
        <ul
          id="guess-listbox"
          role="listbox"
          className="absolute bottom-full left-0 z-40 mb-2 max-h-72 w-full overflow-auto rounded-2xl border border-pitch-600/50 bg-pitch-900/95 p-1.5 shadow-lifted backdrop-blur-md"
        >
          {results.length === 0 ? (
            <li className="px-3 py-2.5 text-sm text-pitch-300">No players found</li>
          ) : (
            results.map((row, i) => (
              <li
                key={row.id}
                id={`guess-option-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(row)}
                className={`cursor-pointer rounded-xl px-3 py-2.5 transition-colors ${
                  i === active ? 'bg-pitch-700/70' : ''
                }`}
              >
                <p className="text-sm font-semibold text-pitch-50">{row.name}</p>
                <p className="text-xs text-pitch-300">
                  {[row.position, row.birth_year && `b. ${row.birth_year}`, row.latest_club]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  )
}
