import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTerminalStore } from '../../store/terminalStore'

const TIERS = [
  { id: 'ROSTRA', name: 'ROSTRA TIER', desc: 'Baseline intelligence. 24h delay.', price: 'Free' },
  { id: 'SIGNAL', name: 'SIGNAL TIER', desc: 'Real-time alerts. Causal chains.', price: '$49/mo' },
  { id: 'API', name: 'API TIER', desc: 'Raw WebSocket. Headless access.', price: '$199/mo' },
]

export default function AuthTerminal() {
  const [isRegister, setIsRegister] = useState(false)
  const [selectedTier, setSelectedTier] = useState('SIGNAL')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayText, setDisplayText] = useState('')
  const login = useTerminalStore(s => s.login)

  const tagline = "COGNITIVE OVERHEAD REDUCED TO ZERO. WELCOME TO THE EPOCH."

  useEffect(() => {
    let i = 0
    const interval = setInterval(() => {
      setDisplayText(tagline.slice(0, i))
      i++
      if (i > tagline.length) clearInterval(interval)
    }, 40)
    return () => clearInterval(interval)
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    // Simulated auth logic - real JWT would come from backend
    const dummyUser = { username, tier: selectedTier }
    const dummyToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." 
    login(dummyUser, dummyToken)
  }

  return (
    <div className="flex flex-col items-center justify-center w-full h-full bg-terminal-bg text-terminal-text font-mono p-6">
      <div className="w-full max-w-xl">
        <pre className="text-terminal-orange text-[10px] leading-none mb-8">
{`
 ███████╗██████╗  ██████╗  ██████╗██╗  ██╗
 ██╔════╝██╔══██╗██╔═══██╗██╔════╝██║  ██║
 █████╗  ██████╔╝██║   ██║██║     ███████║
 ██╔══╝  ██╔═══╝ ██║   ██║██║     ██╔══██║
 ███████╗██║     ╚██████╔╝╚██████╗██║  ██║
 ╚══════╝╚═╝      ╚═════╝  ╚═════╝╚═╝  ╚═╝
`}
        </pre>
        <p className="text-terminal-muted text-sm mb-12 h-5">
          {displayText}<span className="animate-pulse">_</span>
        </p>

        <form onSubmit={handleSubmit} className="space-y-8">
          <div className="flex border-b border-terminal-border">
            <button 
              type="button"
              onClick={() => setIsRegister(false)}
              className={`px-6 py-2 transition-colors ${!isRegister ? 'text-terminal-orange border-b-2 border-terminal-orange' : 'text-terminal-muted'}`}>
              ACCESS
            </button>
            <button 
              type="button"
              onClick={() => setIsRegister(true)}
              className={`px-6 py-2 transition-colors ${isRegister ? 'text-terminal-orange border-b-2 border-terminal-orange' : 'text-terminal-muted'}`}>
              REGISTER
            </button>
          </div>

          <div className="space-y-4">
            <input 
              type="text" 
              placeholder="IDENTIFIER"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-terminal-surface border border-terminal-border p-3 focus:border-terminal-orange outline-none"
            />
            <input 
              type="password" 
              placeholder="CREDENTIAL"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-terminal-surface border border-terminal-border p-3 focus:border-terminal-orange outline-none"
            />
          </div>

          <AnimatePresence mode="wait">
            {isRegister && (
              <motion.div 
                key="register-fields"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="grid grid-cols-3 gap-4 overflow-hidden">
                {TIERS.map(tier => (
                  <div 
                    key={tier.id}
                    onClick={() => setSelectedTier(tier.id)}
                    className={`p-3 border cursor-pointer transition-all ${selectedTier === tier.id ? 'border-terminal-orange bg-terminal-orange/10' : 'border-terminal-border'}`}>
                    <div className="text-[10px] text-terminal-muted">{tier.price}</div>
                    <div className="text-xs font-bold">{tier.name}</div>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <button 
            type="submit"
            className="w-full bg-terminal-orange text-terminal-bg font-bold py-3 hover:bg-opacity-90 transition-all">
            {isRegister ? 'INITIALIZE ACCOUNT' : 'ESTABLISH LINK'}
          </button>
        </form>
      </div>
    </div>
  )
}
