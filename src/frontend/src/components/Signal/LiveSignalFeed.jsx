import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTerminalStore } from '../../store/terminalStore'
import { AlertTriangle, Activity, Zap } from 'lucide-react'

export default function LiveSignalFeed() {
  const { signals, markAllRead, audioCtx, initAudio } = useTerminalStore()

  useEffect(() => {
    initAudio()
  }, [])

  const playBeep = (freq = 800, duration = 0.1) => {
    if (!audioCtx) return
    const osc = audioCtx.createOscillator()
    const gain = audioCtx.createGain()
    osc.type = 'square'
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime)
    gain.gain.setValueAtTime(0.05, audioCtx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration)
    osc.connect(gain)
    gain.connect(audioCtx.destination)
    osc.start()
    osc.stop(audioCtx.currentTime + duration)
  }

  // Effect for Tier 1 Alerts (Audio + Flash logic handled in MainTerminal or here)
  useEffect(() => {
    if (signals.length > 0 && signals[0].tier === 1) {
      playBeep(800, 0.1)
      setTimeout(() => playBeep(800, 0.1), 150)
      setTimeout(() => playBeep(800, 0.1), 300)
    }
    markAllRead()
  }, [signals])

  return (
    <div className="space-y-3">
      <AnimatePresence initial={false}>
        {signals.length === 0 ? (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-20 opacity-20">
            <Activity size={32} className="mb-2" />
            <span className="text-[10px] tracking-widest uppercase">Awaiting Signals...</span>
          </motion.div>
        ) : (
          signals.map((signal, idx) => (
            <motion.div
              key={signal.id || idx}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className={`p-3 border text-[10px] relative overflow-hidden group ${
                signal.tier === 1 ? 'border-terminal-orange bg-terminal-orange/5' : 
                signal.tier === 2 ? 'border-terminal-yellow bg-terminal-yellow/5' : 
                'border-terminal-border bg-terminal-surface'
              }`}>
              
              {/* T1 Flash Effect */}
              {signal.tier === 1 && idx === 0 && (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0, 0.2, 0] }}
                  transition={{ duration: 0.8 }}
                  className="absolute inset-0 bg-terminal-orange pointer-events-none" 
                />
              )}

              <div className="flex justify-between items-start mb-2">
                 <span className={`font-bold uppercase ${
                   signal.tier === 1 ? 'text-terminal-orange' : 
                   signal.tier === 2 ? 'text-terminal-yellow' : 
                   'text-terminal-muted'
                 }`}>
                   TIER_{signal.tier}_ALERT
                 </span>
                 <span className="text-[8px] opacity-50">{signal.timestamp}</span>
              </div>
              
              <div className="text-terminal-text font-bold mb-1 uppercase tracking-tight">
                {signal.msg}
              </div>
              
              <div className="flex gap-2 mt-3">
                <button className="px-2 py-0.5 border border-terminal-border hover:border-terminal-orange transition-all uppercase text-[8px]">
                  View Causal Chain
                </button>
                <button className="px-2 py-0.5 border border-terminal-border hover:border-terminal-accent transition-all uppercase text-[8px]">
                  Calculate Kelly
                </button>
              </div>
            </motion.div>
          ))
        )}
      </AnimatePresence>
    </div>
  )
}
