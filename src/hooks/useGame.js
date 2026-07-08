import { useCallback, useEffect, useReducer } from 'react'
import { api } from '../api/client'

// chain entry: { player: PlayerCard, links: StintLink[] | null } — links join
// this player to the previous entry; the first entry (start player) has none.

const initialState = {
  status: 'loading', // loading | playing | won | revealed | error
  mode: 'daily',
  difficulty: 'medium',
  puzzle: null, // { mode, date, par, start, target }
  chain: [],
  wrongCount: 0,
  wrongGuess: null, // { message, nonce } — nonce retriggers the shake animation
  error: null,
  validating: false,
}

function storageKey(date) {
  return `bc:daily:${date}`
}

function reducer(state, action) {
  switch (action.type) {
    case 'LOADING':
      return { ...initialState, mode: state.mode, difficulty: state.difficulty }
    case 'ERROR':
      return { ...state, status: 'error', error: action.message }
    case 'START':
      return {
        ...initialState,
        mode: state.mode,
        difficulty: state.difficulty,
        status: action.saved?.status || 'playing',
        puzzle: action.puzzle,
        chain: action.saved?.chain || [{ player: action.puzzle.start, links: null }],
        wrongCount: action.saved?.wrongCount || 0,
      }
    case 'VALIDATING':
      return { ...state, validating: true }
    case 'GUESS_OK': {
      const chain = [...state.chain, { player: action.player, links: action.links }]
      const won = action.player.id === state.puzzle.target.id
      return { ...state, chain, status: won ? 'won' : 'playing', wrongGuess: null, validating: false }
    }
    case 'GUESS_FAIL':
      return {
        ...state,
        wrongCount: state.wrongCount + 1,
        wrongGuess: { message: action.message, nonce: Date.now() },
        validating: false,
      }
    case 'UNDO':
      if (state.chain.length <= 1 || state.status !== 'playing') return state
      return { ...state, chain: state.chain.slice(0, -1), wrongGuess: null }
    case 'REVEAL':
      return { ...state, status: 'revealed' }
    case 'SET_MODE':
      return { ...state, mode: action.mode }
    case 'SET_DIFFICULTY':
      return { ...state, difficulty: action.difficulty }
    default:
      return state
  }
}

export default function useGame() {
  const [state, dispatch] = useReducer(reducer, initialState)

  const loadDaily = useCallback(async () => {
    dispatch({ type: 'LOADING' })
    try {
      const puzzle = await api.daily()
      let saved = null
      try {
        const raw = localStorage.getItem(storageKey(puzzle.date))
        if (raw) saved = JSON.parse(raw)
      } catch {
        // corrupted save — start fresh
      }
      dispatch({ type: 'START', puzzle, saved })
    } catch (err) {
      dispatch({ type: 'ERROR', message: err.message })
    }
  }, [])

  const loadFree = useCallback(async (difficulty) => {
    dispatch({ type: 'LOADING' })
    try {
      const puzzle = await api.freeGame(difficulty)
      dispatch({ type: 'START', puzzle })
    } catch (err) {
      dispatch({ type: 'ERROR', message: err.message })
    }
  }, [])

  // Persist daily progress so a refresh doesn't lose the chain.
  useEffect(() => {
    if (state.mode !== 'daily' || !state.puzzle?.date) return
    if (!['playing', 'won', 'revealed'].includes(state.status)) return
    try {
      localStorage.setItem(
        storageKey(state.puzzle.date),
        JSON.stringify({ chain: state.chain, status: state.status, wrongCount: state.wrongCount }),
      )
    } catch {
      // storage full/blocked — the game still works, it just won't survive refresh
    }
  }, [state.mode, state.puzzle, state.chain, state.status, state.wrongCount])

  const guess = useCallback(
    async (candidate) => {
      if (state.status !== 'playing' || state.validating) return
      if (state.chain.some((entry) => entry.player.id === candidate.id)) {
        dispatch({ type: 'GUESS_FAIL', message: `${candidate.name} is already in your chain` })
        return
      }
      const last = state.chain[state.chain.length - 1].player
      dispatch({ type: 'VALIDATING' })
      try {
        const result = await api.validate(last.id, candidate.id)
        if (result.connected) {
          dispatch({ type: 'GUESS_OK', player: result.player, links: result.links })
        } else if (result.reason === 'player-unknown') {
          dispatch({
            type: 'GUESS_FAIL',
            message: `Couldn't find ${candidate.name} right now — try another player`,
          })
        } else {
          dispatch({
            type: 'GUESS_FAIL',
            message: `${candidate.name} never shared a squad with ${last.name}`,
          })
        }
      } catch (err) {
        dispatch({ type: 'GUESS_FAIL', message: err.message })
      }
    },
    [state.status, state.validating, state.chain],
  )

  return {
    state,
    dispatch,
    loadDaily,
    loadFree,
    guess,
    undo: () => dispatch({ type: 'UNDO' }),
    reveal: () => dispatch({ type: 'REVEAL' }),
  }
}
