import { useEffect, useRef, useState } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/signals'

export function useSignalFeed() {
  const [signals, setSignals] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  function connect() {
    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)

      ws.onmessage = (e) => {
        try {
          const signal = JSON.parse(e.data)
          setSignals(prev => [signal, ...prev].slice(0, 50))
        } catch {}
      }

      ws.onclose = () => {
        setConnected(false)
        reconnectRef.current = setTimeout(connect, 3000)
      }

      ws.onerror = () => ws.close()
    } catch {}
  }

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [])

  return { signals, connected }
}
