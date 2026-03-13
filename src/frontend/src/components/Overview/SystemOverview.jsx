import React from 'react'
import { motion } from 'framer-motion'
import { Activity, Shield, Cpu, Gauge, AlertCircle, TrendingUp, Zap } from 'lucide-react'

export default function SystemOverview() {
  const cards = [
    { title: 'ENSEMBLE_ORACLE', status: 'SYNCHRONIZED', icon: Cpu, val: '8/8 Models', color: 'text-terminal-green' },
    { title: 'SIGNAL_VALIDATION', status: 'OPTIMAL', icon: Activity, val: '0.023 RMSE', color: 'text-terminal-accent' },
    { title: 'CAUSAL_CALIBRATION', status: 'ACTIVE', icon: Gauge, val: 'Alpha+ 4.2%', color: 'text-terminal-orange' },
    { title: 'PIPELINE_STABILITY', status: 'STABLE', icon: Shield, val: '99.9% Up', color: 'text-terminal-green' },
  ]

  return (
    <div className="p-6 space-y-6 flex flex-col h-full overflow-y-auto">
       <div className="grid grid-cols-4 gap-6">
          {cards.map((card, i) => (
            <motion.div 
              key={card.title}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.1 }}
              className="bg-terminal-surface border border-terminal-border p-4 flex flex-col gap-3 group hover:border-terminal-orange transition-all">
               <div className="flex justify-between items-start">
                  <card.icon size={20} className="text-terminal-muted" />
                  <span className={`text-[8px] font-bold ${card.color}`}>{card.status}</span>
               </div>
               <div>
                  <div className="text-[10px] text-terminal-muted font-bold tracking-widest uppercase">{card.title}</div>
                  <div className="text-xl font-bold font-mono tracking-tighter">{card.val}</div>
               </div>
            </motion.div>
          ))}
       </div>

       <div className="grid grid-cols-2 gap-6 flex-1">
          {/* Causal DAG Status */}
          <div className="bg-terminal-surface border border-terminal-border flex flex-col overflow-hidden">
             <div className="p-3 border-b border-terminal-border flex justify-between bg-terminal-orange/5">
                <span className="text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                   <Zap size={14} className="text-terminal-orange" /> CAUSAL_RELATIONAL_HEALTH
                </span>
                <span className="text-[10px] text-terminal-muted">R²: 0.892</span>
             </div>
             <div className="flex-1 p-4 grid grid-cols-2 gap-4">
                {['MOMENTUM_DRIVE', 'OFF_EFFICIENCY', 'DEF_COLLAPSE', 'CLUTCH_VARIANCE'].map(node => (
                   <div key={node} className="space-y-1">
                      <div className="flex justify-between text-[8px] uppercase font-bold">
                         <span>{node}</span>
                         <span className="text-terminal-orange">0.84</span>
                      </div>
                      <div className="h-1 bg-terminal-bg border border-terminal-border">
                         <div className="h-full bg-terminal-orange" style={{ width: '84%' }} />
                      </div>
                   </div>
                ))}
             </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-terminal-surface border border-terminal-border flex flex-col overflow-hidden">
             <div className="p-3 border-b border-terminal-border bg-terminal-accent/5">
                <span className="text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                   <AlertCircle size={14} className="text-terminal-accent" /> RECENT_SYS_EVENTS
                </span>
             </div>
             <div className="flex-1 p-2 space-y-1">
                {[
                  { msg: 'ENSEMBLE_CALIBRATION_COMPLETE', time: '2m ago', type: 'SYS' },
                  { msg: 'H_CONV_SIGNAL_FIRED (GSW_LAL)', time: '8m ago', type: 'SIG' },
                  { msg: 'ORACLE_WEIGHTS_UPDATED (CYCLE_4021)', time: '14m ago', type: 'ML' },
                  { msg: 'RETRAINER_STARTING_ON_DATA_POOL', time: '1h ago', type: 'SYS' },
                ].map((event, i) => (
                   <div key={i} className="flex justify-between items-center bg-terminal-bg p-2 text-[10px] border border-transparent hover:border-terminal-border transition-all">
                      <div className="flex items-center gap-2">
                         <span className="text-terminal-muted">[{event.type}]</span>
                         <span>{event.msg}</span>
                      </div>
                      <span className="text-terminal-muted opacity-50">{event.time}</span>
                   </div>
                ))}
             </div>
          </div>
       </div>

       <div className="bg-terminal-bg border border-terminal-dashed border-terminal-border p-4 flex gap-4">
          <button className="flex-1 bg-terminal-orange text-terminal-bg font-bold py-2 text-xs hover:bg-opacity-90 transition-all uppercase">
             RUN_FULL_RETRAINER
          </button>
          <button className="flex-1 bg-terminal-surface border border-terminal-border text-terminal-text font-bold py-2 text-xs hover:border-terminal-orange transition-all uppercase">
             VALIDATE_SIGNAL_SET
          </button>
       </div>
    </div>
  )
}
