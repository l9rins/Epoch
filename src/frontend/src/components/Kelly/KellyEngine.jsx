import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence, useSpring } from 'framer-motion'
import { useTerminalStore } from '../../store/terminalStore'
import { DollarSign, Percent, TrendingUp, AlertCircle } from 'lucide-react'

export default function KellyEngine() {
  const { bankroll, currentRecommendation, setBankroll } = useTerminalStore()
  const [localBankroll, setLocalBankroll] = useState(bankroll)

  // Recommendation spring animations for bet size
  const betSizeSpring = useSpring(0, { stiffness: 100, damping: 20 })
  const edgeSpring = useSpring(0, { stiffness: 100, damping: 20 })

  useEffect(() => {
    if (currentRecommendation) {
       betSizeSpring.set(currentRecommendation.bet_amount)
       edgeSpring.set(currentRecommendation.edge * 100)
    } else {
       betSizeSpring.set(0)
       edgeSpring.set(0)
    }
  }, [currentRecommendation])

  return (
    <div className="h-full flex flex-col font-mono text-[10px]">
       <div className="grid grid-cols-2 gap-2 mb-4">
          <div className="bg-terminal-bg border border-terminal-border p-2">
             <div className="text-terminal-muted mb-1 text-[8px] uppercase">Bankroll_Reserve</div>
             <div className="flex items-center gap-1 text-terminal-text font-bold text-sm">
                <span className="text-terminal-orange">$</span>
                <input 
                  type="number"
                  value={localBankroll}
                  onChange={(e) => {
                    const val = parseInt(e.target.value) || 0
                    setLocalBankroll(val)
                    setBankroll(val)
                  }}
                  className="bg-transparent outline-none w-full"
                />
             </div>
          </div>
          <div className="bg-terminal-bg border border-terminal-border p-2">
             <div className="text-terminal-muted mb-1 text-[8px] uppercase">Active_Edge</div>
             <div className="text-terminal-green font-bold text-sm">
                +{(currentRecommendation?.edge * 100 || 0).toFixed(2)}%
             </div>
          </div>
       </div>

       <div className="flex-1 flex flex-col justify-center">
          <AnimatePresence mode="wait">
            {!currentRecommendation ? (
              <motion.div 
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center opacity-30 italic">
                AWAITING_SIGNAL_CONTEXT...
              </motion.div>
            ) : (
              <motion.div 
                key="active"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="space-y-4">
                 
                 <div>
                    <div className="flex justify-between items-end mb-1">
                       <span className="font-bold">RECOMMENDED_POSITION</span>
                       <span className="text-terminal-orange font-bold text-lg">${currentRecommendation.bet_amount.toLocaleString()}</span>
                    </div>
                    <div className="h-1 bg-terminal-border relative overflow-hidden">
                       <motion.div 
                         className="h-full bg-terminal-orange"
                         initial={{ width: 0 }}
                         animate={{ width: `${(currentRecommendation.bet_amount / bankroll) * 100}%` }}
                       />
                    </div>
                 </div>

                 <div className="p-2 border border-terminal-orange/30 bg-terminal-orange/5 text-[9px] leading-relaxed">
                    <span className="text-terminal-orange font-bold mr-2">[CAUSAL_CONTEXT]</span>
                    {currentRecommendation.reasoning || "High ensemble agreement among 8 models with significant graph relational anomaly."}
                 </div>

                 <div className="grid grid-cols-2 gap-2 mt-2">
                    <button className="p-2 bg-terminal-green text-terminal-bg font-bold hover:bg-opacity-90 transition-all">
                       LOG_TRANSACTION
                    </button>
                    <button className="p-2 border border-terminal-border text-terminal-muted hover:text-terminal-text transition-all uppercase">
                       IGNORE_SPOT
                    </button>
                 </div>
              </motion.div>
            )}
          </AnimatePresence>
       </div>
    </div>
  )
}
