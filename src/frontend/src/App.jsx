import { useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useTerminalStore } from './store/terminalStore'
import AuthTerminal from './components/Auth/AuthTerminal'
import MainTerminal from './components/Terminal/MainTerminal'
import CommandPalette from './components/Command/CommandPalette'
import AccuracyDashboard from './components/Public/AccuracyDashboard'
import PricingPage from './components/Public/PricingPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    }
  }
})

export default function App() {
  const isAuthenticated = useTerminalStore(s => s.isAuthenticated)
  const accessToken = useTerminalStore(s => s.accessToken)
  const isCommandOpen = useTerminalStore(s => s.isCommandOpen)

  // Global Cmd+K listener
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        useTerminalStore.getState().openCommand()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="w-screen h-screen overflow-hidden font-sans"
             style={{ background: '#080B0F', color: '#E6EDF3' }}>
          <Routes>
            <Route path="/accuracy" element={<AccuracyDashboard />} />
            <Route path="/pricing" element={<PricingPage accessToken={accessToken} />} />
            <Route path="/" element={
              <AnimatePresence mode="wait">
                {!isAuthenticated ? (
                  <motion.div key="auth"
                    className="w-full h-full"
                    initial={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -40 }}
                    transition={{ duration: 0.6 }}>
                    <AuthTerminal />
                  </motion.div>
                ) : (
                  <motion.div key="terminal"
                    className="w-full h-full"
                    initial={{ opacity: 0, y: 40 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}>
                    <MainTerminal />
                  </motion.div>
                )}
              </AnimatePresence>
            } />
          </Routes>
          {isAuthenticated && isCommandOpen && <CommandPalette />}
        </div>
      </Router>
    </QueryClientProvider>
  )
}
