const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  // Analyst
  accuracy:           () => get('/api/accuracy'),
  predictionsHistory: () => get('/api/predictions/history'),

  // Bettor
  predictionsToday:   () => get('/api/predictions/today'),
  schedule:           () => get('/api/schedule'),
  signal:             () => get('/api/signal/current'),
  odds:               () => get('/api/odds/today'),

  // Roster
  roster:    (team)   => get(`/api/roster/${team}`),
  player:    (name)   => get(`/api/player/${name}`),
  download:  (team)   => `${BASE}/api/download/${team}`,
}
