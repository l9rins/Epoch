import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Play, Layers, Users, Zap, Info } from 'lucide-react'

export default function QuantumRunner() {
  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState(0)

  const runSim = () => {
    setIsRunning(true)
    setProgress(0)
    const interval = setInterval(() => {
      setProgress(p => {
        if (p >= 100) {
           clearInterval(interval)
           setIsRunning(false)
           return 100
        }
        return p + 1
      })
    }, 30)
  }

  return (
    <div className="p-6 space-y-6 flex flex-col h-full overflow-y-auto">
       <div className="bg-terminal-surface border border-terminal-border p-6 flex flex-col gap-8">
          <div className="flex justify-between items-start">
             <div>
                <h2 className="text-xl font-bold tracking-tight text-terminal-orange mb-1 uppercase">Quantum_Universe_Sampler</h2>
                <p className="text-xs text-terminal-muted uppercase">Run 10,000 Monte Carlo simulations using current adversarial priors</p>
             </div>
             <button 
               onClick={runSim}
               disabled={isRunning}
               className={`px-8 py-3 bg-terminal-orange text-terminal-bg font-bold tracking-widest uppercase hover:bg-opacity-90 transition-all ${isRunning ? 'opacity-50 cursor-wait' : ''}`}>
               {isRunning ? 'SAMPLING_UNIVERSE...' : 'RUN_QUANTUM_SIM'}
             </button>
          </div>

          <div className="grid grid-cols-3 gap-8">
             <div className="space-y-4">
                <div className="text-[10px] font-bold text-terminal-muted uppercase">Configuration_Parameters</div>
                <div className="space-y-3">
                   {['Iterations: 10,000', 'Prior_Strength: 0.85', 'Noise_Injection: 0.02', 'B2B_Adjustment: YES'].map(param => (
                      <div key={param} className="flex justify-between pb-1 border-b border-terminal-border border-dashed text-[10px]">
                         <span className="text-terminal-muted">{param.split(':')[0]}</span>
                         <span className="font-bold">{param.split(':')[1]}</span>
                      </div>
                   ))}
                </div>
             </div>

             <div className="col-span-2 flex flex-col justify-center">
                <div className="flex justify-between text-[10px] mb-2 font-bold uppercase">
                   <span>Universe_Simulation_Progress</span>
                   <span>{progress}%</span>
                </div>
                <div className="h-4 bg-terminal-bg border border-terminal-border relative overflow-hidden">
                   <motion.div 
                     className="h-full bg-terminal-orange"
                     animate={{ width: `${progress}%` }}
                     transition={{ type: 'spring', bounce: 0, duration: 0.1 }}
                   />
                </div>
                <div className="mt-4 text-[9px] text-terminal-muted flex justify-between uppercase">
                   <span>Thread_POOL_ACTIVE [16]</span>
                   <span>Estimated_Resolution: 0.2s</span>
                </div>
             </div>
          </div>
       </div>

       <div className="grid grid-cols-2 gap-6 flex-1 min-h-0">
          {/* Distribution Curve Placeholder */}
          <div className="bg-terminal-surface border border-terminal-border p-4 flex flex-col">
             <div className="text-[10px] font-bold text-terminal-muted uppercase mb-4">Outcome_Distribution_Map</div>
             <div className="flex-1 border border-dashed border-terminal-border flex items-center justify-center opacity-30 italic text-[10px]">
                [D3_SIMULATION_DENSITY_MAP]
             </div>
          </div>

          {/* Percentile Table */}
          <div className="bg-terminal-surface border border-terminal-border p-4 flex flex-col overflow-hidden">
             <div className="text-[10px] font-bold text-terminal-muted uppercase mb-4 tracking-widest">Percentile_Resolution_Table</div>
             <div className="space-y-1">
                {[
                  { p: 'P10', val: '-12.5' },
                  { p: 'P25', val: '-5.2' },
                  { p: 'P50 (Median)', val: '+2.1' },
                  { p: 'P75', val: '+8.4' },
                  { p: 'P90', val: '+16.8' },
                ].map(row => (
                  <div key={row.p} className="flex justify-between p-2 bg-terminal-bg/50 text-xs">
                     <span className="text-terminal-muted font-bold font-mono uppercase">{row.p}</span>
                     <span className="font-bold">{row.val}</span>
                  </div>
                ))}
             </div>
          </div>
       </div>
    </div>
  )
}
