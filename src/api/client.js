async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = null
    try {
      detail = (await res.json()).detail
    } catch {
      // non-JSON error body
    }
    const err = new Error(detail || `Request failed (${res.status})`)
    err.status = res.status
    throw err
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  daily: () => request('/daily'),
  freeGame: (difficulty) =>
    request('/free-game', { method: 'POST', body: JSON.stringify({ difficulty }) }),
  search: (q, limit = 8) =>
    request(`/players/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  validate: (fromId, toId) =>
    request('/validate', {
      method: 'POST',
      body: JSON.stringify({ from_id: fromId, to_id: toId }),
    }),
  solution: (startId, targetId) =>
    request(
      `/solution?start_id=${encodeURIComponent(startId)}&target_id=${encodeURIComponent(targetId)}`,
    ),
}
