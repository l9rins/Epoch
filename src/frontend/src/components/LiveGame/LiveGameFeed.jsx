import React from 'react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Clock, TrendingUp, Info } from 'lucide-react'

export default function LiveGameFeed() {
  return (
    <div className="p-6 h-full flex flex-col space-y-6">
       {/* ACTIVE GAME HEADER */}
       <div className="bg-terminal-surface border border-terminal-border p-4 flex justify-between items-center">
          <div className="flex items-center gap-8">
             <div className="text-center">
                <div className="text-terminal-orange font-bold text-lg">GSW</div>
                <div className="text-3xl font-bold tracking-tighter">114</div>
             </div>
             <div className="flex flex-col items-center">
                <div className="text-terminal-muted text-[10px] font-bold">Q4_04:12</div>
                <div className="text-terminal-orange font-mono text-xs animate-pulse">LIVE_STREAMING_</div>
             </div>
             <div className="text-center">
                <div className="text-terminal-accent font-bold text-lg">LAL</div>
                <div className="text-3xl font-bold tracking-tighter">112</div>
             </div>
          </div>

          <div className="flex-1 max-w-xs mx-12">
             <div className="flex justify-between text-[10px] font-bold mb-1">
                <span className="text-terminal-orange">GSW_64.2%</span>
                <span className="text-terminal-accent">35.8%_LAL</span>
             </div>
             <div className="h-2 bg-terminal-bg border border-terminal-border flex">
                <motion.div 
                  initial={{ width: '50%' }}
                  animate={{ width: '64.2%' }}
                  className="h-full bg-terminal-orange" 
                />
                <motion.div 
                  initial={{ width: '50%' }}
                  animate={{ width: '35.8%' }}
                  className="h-full bg-terminal-accent" 
                />
             </div>
          </div>

          <div className="flex gap-4">
             <div className="text-right">
                <div className="text-[8px] text-terminal-muted uppercase">P_TOTAL</div>
                <div className="text-sm font-bold">228.5</div>
             </div>
             <div className="text-right">
                <div className="text-[8px] text-terminal-muted uppercase">PACE_PROJ</div>
                <div className="text-sm font-bold">104.2</div>
             </div>
          </div>
       </div>

       <div className="grid grid-cols-2 gap-6 flex-1 min-h-0">
          {/* MOMENTUM WAVEFORM */}
          <div className="bg-terminal-surface border border-terminal-border flex flex-col min-h-0">
             <div className="p-3 border-b border-terminal-border px-4 flex justify-between">
                <span className="text-xs font-bold uppercase tracking-widest">Momentum_Waveform_300t</span>
                <span className="text-[10px] text-terminal-orange font-bold">+12.4</span>
             </div>
             <div className="flex-1 p-2 bg-terminal-bg/30">
                <ResponsiveContainer width="100%" height="100%">
                   <AreaChart data={new Array(50).fill(0).map((_, i) => ({ i, val: Math.sin(i / 5) * 10 + (Math.random() * 2) }))}>
                      <Area type="monotone" dataKey="val" fill="#DB6D2833" stroke="#DB6D28" strokeWidth={1.5} dot={false} />
                   </AreaChart>
                </ResponsiveContainer>
             </div>
          </div>

          {/* CAUSAL STATE PANEL */}
          <div className="bg-terminal-surface border border-terminal-border flex flex-col min-h-0">
             <div className="p-3 border-b border-terminal-border px-4">
                <span className="text-xs font-bold uppercase tracking-widest">Ensemble_Causal_States</span>
             </div>
             <div className="flex-1 grid grid-cols-3 gap-2 p-4">
                {['REST_ADV', 'HOME_COURT', 'INJURY_VOL', 'PACE_VAR', 'OFF_RATING', 'DEF_RATING', 'MATCHUP_X', 'FOUL_TROUBLE', 'B2B_PROFILE'].map(n => (
                   <div key={n} className="p-2 border border-terminal-border bg-terminal-bg flex flex-col items-center justify-center gap-1 group hover:border-terminal-orange">
                      <div className="text-[8px] text-terminal-muted uppercase truncate w-full text-center">{n}</div>
                      <div className="text-sm font-bold text-terminal-text">{(Math.random() * 0.5 + 0.5).toFixed(2)}</div>
                   </div>
                ))}
             </div>
          </div>
       </div>

       {/* IN-GAME SENSORS */}
       <div className="h-32 grid grid-cols-4 gap-4">
          {[
            { label: 'SHOT_QUALITY', val: '1.14', color: 'text-terminal-green' },
            { label: 'TRANSITION_THREAT', val: 'HIGH', color: 'text-terminal-orange' },
            { label: 'REB_DOMINANCE', val: '54%', color: 'text-terminal-text' },
            { label: 'ADVERSARIAL_BIAS', val: '0.02', color: 'text-terminal-muted' },
          ].map(m => (
            <div key={m.label} className="bg-terminal-surface border border-terminal-border p-4 flex flex-col justify-center">
               <div className="text-[8px] text-terminal-muted uppercase mb-1 font-bold">{m.label}</div>
               <div className={`text-xl font-bold ${m.color}`}>{m.val}</div>
            </div>
          ))}
       </div>
    </div>
  )
}
