import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import BubbleBoard from './components/BubbleBoard'
import DifficultyPicker from './components/DifficultyPicker'
import ErrorState from './components/ErrorState'
import GuessInput from './components/GuessInput'
import Header from './components/Header'
import LoadingState from './components/LoadingState'
import WinScreen from './components/WinScreen'
import useGame from './hooks/useGame'

export default function App() {
  const { state, dispatch, loadDaily, loadFree, guess, undo, reveal } = useGame()
  const [solution, setSolution] = useState(null)
  const [emptyDatabase, setEmptyDatabase] = useState(false)

  const startGame = useCallback(
    (mode, difficulty) => {
      setSolution(null)
      if (mode === 'daily') loadDaily()
      else loadFree(difficulty)
    },
    [loadDaily, loadFree],
  )

  useEffect(() => {
    startGame(state.mode, state.difficulty)
    // deliberately re-run on mode changes only; difficulty changes start a
    // new game through their own handler
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.mode])

  // Fetch the shortest route once the game ends (win or reveal).
  useEffect(() => {
    if (!['won', 'revealed'].includes(state.status) || !state.puzzle) return undefined
    let cancelled = false
    api
      .solution(state.puzzle.start.id, state.puzzle.target.id)
      .then((data) => {
        if (!cancelled) setSolution(data)
      })
      .catch(() => {
        if (!cancelled) setSolution(null)
      })
    return () => {
      cancelled = true
    }
  }, [state.status, state.puzzle])

  // Distinguish "backend broken" from "database not seeded yet".
  useEffect(() => {
    if (state.status !== 'error') {
      setEmptyDatabase(false)
      return
    }
    api
      .health()
      .then((h) => setEmptyDatabase(h.players === 0))
      .catch(() => setEmptyDatabase(false))
  }, [state.status])

  const lastPlayer = state.chain.length
    ? state.chain[state.chain.length - 1].player
    : null
  const playing = state.status === 'playing'
  const finished = ['won', 'revealed'].includes(state.status)

  return (
    <div className="stadium-backdrop grain-overlay min-h-screen">
      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-4xl flex-col px-4 sm:px-6">
        <Header
          mode={state.mode}
          onModeChange={(mode) => dispatch({ type: 'SET_MODE', mode })}
          puzzle={state.mode === 'daily' ? state.puzzle : null}
        />

        {state.mode === 'free' && state.status !== 'loading' && (
          <div className="pb-1 pt-2">
            <DifficultyPicker
              value={state.difficulty}
              onChange={(difficulty) => {
                dispatch({ type: 'SET_DIFFICULTY', difficulty })
                startGame('free', difficulty)
              }}
              onNewGame={() => startGame('free', state.difficulty)}
            />
          </div>
        )}

        <main className="flex flex-1 flex-col">
          {state.status === 'loading' && <LoadingState />}

          {state.status === 'error' && (
            <div className="py-16">
              <ErrorState
                message={state.error}
                emptyDatabase={emptyDatabase}
                onRetry={() => startGame(state.mode, state.difficulty)}
              />
            </div>
          )}

          {(playing || finished) && state.puzzle && (
            <>
              <BubbleBoard
                chain={state.chain}
                target={state.puzzle.target}
                status={state.status}
                wrongGuess={state.wrongGuess}
              />

              {playing && (
                <div className="sticky bottom-0 z-30 mt-2 flex flex-col items-center gap-2.5 pb-5 pt-3">
                  <GuessInput
                    lastPlayer={lastPlayer}
                    onGuess={guess}
                    disabled={!playing}
                    validating={state.validating}
                  />
                  <div className="flex items-center gap-4 text-xs text-pitch-400">
                    <span>
                      {state.chain.length - 1} {state.chain.length === 2 ? 'step' : 'steps'} · par{' '}
                      {state.puzzle.par}
                    </span>
                    {state.chain.length > 1 && (
                      <button
                        onClick={undo}
                        className="rounded-full px-2 py-0.5 font-semibold text-pitch-300 transition-colors hover:text-pitch-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-pitch-300 active:scale-[0.97]"
                      >
                        Undo last
                      </button>
                    )}
                    <button
                      onClick={reveal}
                      className="rounded-full px-2 py-0.5 font-semibold text-pitch-300 transition-colors hover:text-pitch-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-pitch-300 active:scale-[0.97]"
                    >
                      Give up · show route
                    </button>
                  </div>
                </div>
              )}

              {finished && (
                <div className="pb-10 pt-4">
                  <WinScreen
                    state={state}
                    solution={solution}
                    onPlayAgain={() => startGame('free', state.difficulty)}
                  />
                </div>
              )}
            </>
          )}
        </main>

        <footer className="pb-6 pt-2 text-center text-[11px] text-pitch-500">
          Squad data via a self-hosted transfermarkt-api · bubbles are draggable
        </footer>
      </div>
    </div>
  )
}
