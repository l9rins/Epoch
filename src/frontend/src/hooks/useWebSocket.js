import { useEffect, useRef, useCallback } from 'react'
import { useTerminalStore } from '../store/terminalStore'

const MAX_RECONNECT_ATTEMPTS = 5
const BASE_RECONNECT_DELAY = 1000

export function useWebSocket() {
  const wsRef = useRef(null)
  const reconnectAttempts = useRef(0)
  const reconnectTimer = useRef(null)

  const {
    setWsStatus, setGameState, addSignal,
    accessToken, wsStatus
  } = useTerminalStore()

  const connect = useCallback((gameId) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    if (!accessToken) return

    setWsStatus('connecting')
    const url = `ws://localhost:8000/ws/${gameId}?token=${accessToken}`
    const ws = new WebSocket(url)

    ws.onopen = () => {
      setWsStatus('connected')
      reconnectAttempts.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'STATE') setGameState(msg)
        if (msg.type === 'ALERT') addSignal(msg)
      } catch (e) {
        console.error('WS parse error:', e)
      }
    }

    ws.onclose = (event) => {
      setWsStatus('disconnected')
      if (!event.wasClean && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = Math.min(
          BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current),
          30000
        )
        reconnectAttempts.current++
        reconnectTimer.current = setTimeout(() => connect(gameId), delay)
      } else if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
        setWsStatus('error')
      }
    }

    ws.onerror = () => setWsStatus('error')
    wsRef.current = ws
  }, [accessToken, setWsStatus, setGameState, addSignal])

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current)
    reconnectAttempts.current = MAX_RECONNECT_ATTEMPTS
    wsRef.current?.close(1000, 'User disconnect')
    setWsStatus('disconnected')
  }, [setWsStatus])

  return { connect, disconnect, status: wsStatus }
}
