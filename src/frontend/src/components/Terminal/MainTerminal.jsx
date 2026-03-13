import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  BarChart3, Settings, Shield, Zap, History, LayoutDashboard, 
  Terminal as TerminalIcon, LogOut, Search, Clock, Bell, AlertTriangle
} from 'lucide-react'
import { useTerminalStore } from '../../store/terminalStore'
import { useWebSocket } from '../../hooks/useWebSocket'

// CENTER VIEWS
import SystemOverview from '../Overview/SystemOverview'
import LiveGameFeed from '../LiveGame/LiveGameFeed'
import PropBoard from '../Props/PropBoard'
import OracleTerminal from '../Oracle/OracleTerminal'
import QuantumRunner from '../Quantum/QuantumRunner'
import JournalDashboard from '../Journal/JournalDashboard'
import LiveSignalFeed from '../Signal/LiveSignalFeed'
import KellyEngine from '../Kelly/KellyEngine'

const VIEWS = {
  OVERVIEW: { name: 'SYSTEM_OVERVIEW', component: SystemOverview, icon: LayoutDashboard },
  LIVE:     { name: 'LIVE_INTELLIGENCE', component: LiveGameFeed, icon: Zap },
  PROPS:    { name: 'PROP_ENGINE', component: PropBoard, icon: BarChart3 },
  ORACLE:   { name: 'ORACLE_ADVERSARY', component: OracleTerminal, icon: Shield },
  QUANTUM:  { name: 'QUANTUM_SAMPLER', component: QuantumRunner, icon: TerminalIcon },
  JOURNAL:  { name: 'BETTING_JOURNAL', component: JournalDashboard, icon: History },
}

export default function MainTerminal() {
  const [activeView, setActiveView] = useState('OVERVIEW')
  const { user, logout, wsStatus, unreadCount, resumeAudio } = useTerminalStore()
  const [pipelineHealth, setPipelineHealth] = useState(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch('/api/pipeline/health')
        const data = await res.json()
        setPipelineHealth(data)
      } catch (err) {
        console.error('Pipeline health check failed', err)
      }
    }
    
    checkHealth()
    const interval = setInterval(checkHealth, 60000)
    return () => clearInterval(interval)
  }, [])
  
  const ActiveComponent = VIEWS[activeView].component

  return (
    <div 
      className="relative flex w-full h-full bg-terminal-bg text-terminal-text font-mono overflow-hidden"
      onClick={resumeAudio}>
      
      {/* SESSION A: PIPELINE ARMOR BANNER */}
      {pipelineHealth?.is_stale && (
        <motion.div 
          initial={{ y: -100 }}
          animate={{ y: 0 }}
          className="absolute top-0 left-0 w-full z-[100] bg-terminal-yellow/10 border-b border-terminal-yellow/30 py-1.5 backdrop-blur-md flex items-center justify-center gap-3 animate-pulse">
          <AlertTriangle size={14} className="text-terminal-yellow" />
          <span className="text-[10px] font-bold text-terminal-yellow tracking-[0.2em]">
            SYSTEM_DEGRADED: DATA_STALE ({pipelineHealth.data_age_hours}H) // FALLBACK_INGEST_ACTIVE
          </span>
        </motion.div>
      )}
      {/* SIDEBAR */}
      <div className="w-[240px] border-r border-terminal-border flex flex-col p-4">
        <div className="mb-8 p-2 border border-terminal-orange flex items-center gap-3">
          <div className="w-3 h-3 bg-terminal-orange animate-pulse" />
          <span className="text-terminal-orange font-bold text-lg leading-none tracking-tighter">EPOCH_</span>
        </div>

        <nav className="flex-1 space-y-1">
          {Object.entries(VIEWS).map(([id, view]) => (
            <button
              key={id}
              onClick={() => setActiveView(id)}
              className={`w-full flex items-center gap-3 p-2 text-xs transition-all ${activeView === id ? 'bg-terminal-surface text-terminal-orange border-l-2 border-terminal-orange' : 'text-terminal-muted hover:text-terminal-text'}`}>
              <view.icon size={16} />
              {view.name}
            </button>
          ))}
        </nav>

        <div className="mt-auto pt-4 border-t border-terminal-border space-y-4">
          <div className="p-2 bg-terminal-surface/50 border border-terminal-border text-[10px]">
            <div className="flex justify-between mb-1">
              <span className="text-terminal-muted">TIER</span>
              <span className="text-terminal-orange font-bold italic">{user?.tier || 'SIGNAL'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-terminal-muted">CLIENT</span>
              <span>{user?.username || 'GUEST_01'}</span>
            </div>
          </div>
          
          <button 
            onClick={logout}
            className="w-full flex items-center gap-3 p-2 text-xs text-terminal-red hover:bg-terminal-red/10 transition-all">
            <LogOut size={16} />
            DISCONNECT_SYSTEM
          </button>
        </div>
      </div>

      {/* CENTER PANEL */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-terminal-border flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
             <span className="text-terminal-muted">LOCATION_</span>
             <span className="text-terminal-text uppercase tracking-widest text-xs">root/usr/{VIEWS[activeView].name.toLowerCase()}</span>
          </div>
          
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2 text-[10px]">
               <Clock size={12} className="text-terminal-muted"/>
               <span className="text-terminal-muted">14:23:09_UTC</span>
            </div>
            
            <button 
              onClick={() => useTerminalStore.getState().openCommand()}
              className="flex items-center gap-2 px-3 py-1 bg-terminal-surface border border-terminal-border text-[10px] text-terminal-muted hover:border-terminal-orange transition-all">
              <Search size={12} />
              <span className="opacity-50">CMD+K FOR COMMANDS</span>
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-auto bg-terminal-bg/50">
           <AnimatePresence mode="wait">
             <motion.div
               key={activeView}
               initial={{ opacity: 0, x: 20 }}
               animate={{ opacity: 1, x: 0 }}
               exit={{ opacity: 0, x: -20 }}
               transition={{ duration: 0.2 }}
               className="h-full">
               <ActiveComponent />
             </motion.div>
           </AnimatePresence>
        </main>
      </div>

      {/* RIGHT CHANNELS */}
      <div className="w-[380px] border-l border-terminal-border flex flex-col">
        <div className="flex-1 border-b border-terminal-border flex flex-col">
          <div className="h-10 border-b border-terminal-border px-4 flex items-center justify-between bg-terminal-surface">
            <span className="text-[10px] font-bold flex items-center gap-2">
              <Bell size={12} className="text-terminal-orange" />
              LIVE_SIGNAL_STREAM
            </span>
            {unreadCount > 0 && (
              <span className="bg-terminal-orange text-terminal-bg px-1.5 py-0.5 text-[8px] font-bold animate-bounce">
                {unreadCount}_NEW
              </span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto p-4 bg-terminal-bg">
             <LiveSignalFeed />
          </div>
        </div>

        <div className="h-[320px] flex flex-col bg-terminal-surface/20">
          <div className="h-10 border-b border-terminal-border px-4 flex items-center justify-between bg-terminal-surface">
            <span className="text-[10px] font-bold flex items-center gap-2">
              <Zap size={12} className="text-terminal-yellow" />
              KELLY_SIZING_ENGINE
            </span>
          </div>
          <div className="flex-1 p-4">
             <KellyEngine />
          </div>
        </div>
        
        <div className="p-3 border-t border-terminal-border bg-terminal-bg">
           <div className="flex items-center justify-between text-[10px]">
              <div className="flex items-center gap-2">
                 <div className={`w-1.5 h-1.5 rounded-full ${wsStatus === 'connected' ? 'bg-terminal-green' : 'bg-terminal-red'}`} />
                 <span className="text-terminal-muted uppercase">SYS_LINK: {wsStatus}</span>
              </div>
              <span className="text-terminal-muted">LATENCY: 42MS</span>
           </div>
        </div>
      </div>
    </div>
  )
}
