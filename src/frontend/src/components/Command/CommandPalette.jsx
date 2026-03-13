import React, { useState, useEffect } from 'react'
import { Command } from 'cmdk'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Search, Zap, Shield, BarChart3, History, LayoutDashboard,
  Terminal, Settings, Play, RefreshCw, Calculator, BookOpen
} from 'lucide-react'
import { useTerminalStore } from '../../store/terminalStore'

export default function CommandPalette() {
  const { isCommandOpen, closeCommand } = useTerminalStore()
  const [search, setSearch] = useState('')

  if (!isCommandOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] bg-terminal-bg/80 backdrop-blur-sm p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: -20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: -20 }}
        className="w-full max-w-xl bg-terminal-surface border border-terminal-orange shadow-2xl overflow-hidden">
        
        <Command className="flex flex-col h-full font-mono">
           <div className="flex items-center px-4 border-b border-terminal-border bg-terminal-surface">
              <Search className="text-terminal-orange mr-3" size={18} />
              <Command.Input 
                autoFocus
                value={search}
                onValueChange={setSearch}
                placeholder="ENTER_COMMAND_OR_SEARCH_QUERY..."
                className="flex-1 h-14 bg-transparent outline-none text-sm text-terminal-text placeholder:text-terminal-muted uppercase"
              />
              <button onClick={closeCommand} className="text-[10px] text-terminal-muted hover:text-terminal-orange px-2 border border-terminal-border">ESC</button>
           </div>

           <Command.List className="max-h-[300px] overflow-y-auto p-2 scrollbar-hide">
              <Command.Empty className="py-8 text-center text-xs text-terminal-muted uppercase">No_Matches_Found</Command.Empty>

              <Command.Group heading="NAVIGATION" className="text-[10px] text-terminal-orange font-bold uppercase mb-2 mt-2 px-2">
                 <CommandItem onSelect={closeCommand} icon={LayoutDashboard} label="Jump to System Overview" />
                 <CommandItem onSelect={closeCommand} icon={Zap} label="Monitor Live Game Intelligence" />
                 <CommandItem onSelect={closeCommand} icon={BarChart3} label="Analyze Prop Board" />
                 <CommandItem onSelect={closeCommand} icon={Shield} label="Inspect Oracle & Adversary" />
                 <CommandItem onSelect={closeCommand} icon={History} label="View Betting Journal" />
              </Command.Group>

              <Command.Group heading="MODEL_OPERATIONS" className="text-[10px] text-terminal-orange font-bold uppercase mb-2 mt-4 px-2">
                 <CommandItem onSelect={closeCommand} icon={RefreshCw} label="Trigger Full Retraining Pipeline" shortcut="CMD+R" />
                 <CommandItem onSelect={closeCommand} icon={Play} label="Run Headless Simulation" />
                 <CommandItem onSelect={closeCommand} icon={Terminal} label="Spin Up Quantum Sampler" />
              </Command.Group>

              <Command.Group heading="TOOLS" className="text-[10px] text-terminal-orange font-bold uppercase mb-2 mt-4 px-2">
                 <CommandItem onSelect={closeCommand} icon={Calculator} label="Calculate Kelly Sizing" />
                 <CommandItem onSelect={closeCommand} icon={BookOpen} label="Open API Documentation" />
                 <CommandItem onSelect={closeCommand} icon={Settings} label="System Configuration" />
              </Command.Group>
           </Command.List>

           <div className="p-3 border-t border-terminal-border bg-terminal-bg/50 flex justify-between items-center text-[10px] text-terminal-muted">
              <div className="flex gap-4">
                 <span>↑↓ NAVIGATE</span>
                 <span>ENTER SELECT</span>
                 <span>ESC CLOSE</span>
              </div>
              <span className="text-terminal-orange/50">V1.0.42_STABLE</span>
           </div>
        </Command>
      </motion.div>
    </div>
  )
}

function CommandItem({ label, icon: Icon, onSelect, shortcut }) {
  return (
    <Command.Item 
      onSelect={onSelect}
      className="flex items-center justify-between p-2 text-xs text-terminal-text cursor-pointer hover:bg-terminal-orange/10 aria-selected:bg-terminal-orange/10 group transition-all">
       <div className="flex items-center gap-3">
          <Icon size={14} className="text-terminal-muted group-hover:text-terminal-orange transition-colors" />
          <span className="group-aria-selected:text-terminal-orange uppercase">{label}</span>
       </div>
       {shortcut && <span className="text-[9px] text-terminal-muted opacity-50 px-1 border border-terminal-border">{shortcut}</span>}
    </Command.Item>
  )
}
