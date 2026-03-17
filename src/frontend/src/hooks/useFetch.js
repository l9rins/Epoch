import { useEffect, useState, useCallback } from 'react'

export function useFetch(fetchFn, deps = [], pollMs = 0) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const load = useCallback(async () => {
    try {
      const result = await fetchFn()
      setData(result)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, deps)

  useEffect(() => {
    load()
    if (pollMs > 0) {
      const id = setInterval(load, pollMs)
      return () => clearInterval(id)
    }
  }, [load])

  return { data, loading, error, refetch: load }
}
