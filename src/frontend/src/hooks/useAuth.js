import { useState, useCallback, useEffect } from 'react'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'epoch_token'
const USER_KEY  = 'epoch_user'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || `API error ${res.status}`)
  return data
}

export function useAuth() {
  const [user, setUser]       = useState(() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY)) } catch { return null }
  })
  const [token, setToken]     = useState(() => localStorage.getItem(TOKEN_KEY))
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  // Persist token + user
  useEffect(() => {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  }, [token])

  useEffect(() => {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_KEY)
  }, [user])

  const authHeaders = useCallback(() => ({
    Authorization: token ? `Bearer ${token}` : '',
  }), [token])

  const login = useCallback(async (email, password) => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      setToken(data.token)
      setUser({ user_id: data.user_id, email: data.email, tier: data.tier, subscription: data.subscription })
      return data
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const register = useCallback(async (email, password, tier = 'ROSTRA') => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password, tier }),
      })
      setToken(data.token)
      setUser({ user_id: data.user_id, email: data.email, tier: data.tier, subscription: data.subscription })
      return data
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const refreshToken = useCallback(async () => {
    if (!token) return
    try {
      const data = await apiFetch('/api/auth/refresh', {
        method: 'POST',
        headers: authHeaders(),
      })
      setToken(data.token)
    } catch {
      logout()
    }
  }, [token, authHeaders, logout])

  // Tier checks
  const canAccess = useCallback((requiredTier) => {
    const levels = { ROSTRA: 1, SIGNAL: 2, API: 3 }
    return (levels[user?.tier] || 0) >= (levels[requiredTier] || 99)
  }, [user])

  const isLoggedIn   = !!token && !!user
  const tier         = user?.tier || null
  const subscription = user?.subscription || null

  return {
    user, token, loading, error,
    login, register, logout, refreshToken,
    authHeaders, canAccess,
    isLoggedIn, tier, subscription,
  }
}
