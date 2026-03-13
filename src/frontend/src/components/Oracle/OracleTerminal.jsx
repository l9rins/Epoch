import React, { useState, useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, Zap, Target, Activity, RefreshCw } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts'

const MOCK_ORACLE_FEATURES = [
  { name: 'ISO_FREQ', weight: 0.18 },
  { name: 'PNR_DENS', weight: -0.12 },
  { name: 'SPOT_UP', weight: 0.08 },
  { name: 'TRANS_EFF', weight: 0.22 },
  { name: 'HT_ADV', weight: 0.05 },
  { name: 'REST_IDX', weight: -0.09 },
]

export default function OracleTerminal() {
  const [isTraining, setIsTraining] = useState(false)
  const [efficiency, setEfficiency] = useState(74.2)
  const arcRef = useRef()

  useEffect(() => {
    if (!arcRef.current) return
    const svg = d3.select(arcRef.current)
    svg.selectAll("*").remove()

    const width = 200
    const height = 120
    const radius = 80

    const g = svg.append("g").attr("transform", `translate(${width/2},${height})`)

    const arc = d3.arc()
      .innerRadius(60)
      .outerRadius(radius)
      .startAngle(-Math.PI / 2)

    g.append("path")
      .datum({ endAngle: Math.PI / 2 })
      .attr("fill", "#1C2333")
      .attr("d", arc)

    const foreground = g.append("path")
      .datum({ endAngle: -Math.PI / 2 + (efficiency / 100) * Math.PI })
      .attr("fill", "#3FB950")
      .attr("d", arc)

    // Animation
    foreground.transition()
      .duration(1000)
      .attrTween("d", d => {
        const interpolate = d3.interpolate(d.endAngle, -Math.PI / 2 + (efficiency / 100) * Math.PI)
        return t => {
          d.endAngle = interpolate(t)
          return arc(d)
        }
      })
  }, [efficiency])

  const runTraining = () => {
    setIsTraining(true)
    setTimeout(() => {
      setIsTraining(false)
      setEfficiency(prev => Math.min(99.9, prev + 1.2))
    }, 2000)
  }

  return (
    <div className="p-6 flex flex-col h-full space-y-6">
       <div className="grid grid-cols-3 gap-6 flex-1">
          {/* ORACLE PANEL */}
          <div className="bg-terminal-surface border border-terminal-border flex flex-col">
             <div className="p-3 border-b border-terminal-border flex justify-between items-center bg-terminal-orange/5">
                <span className="text-xs font-bold text-terminal-orange flex items-center gap-2">
                   <Target size={14} /> ORACLE_ENGINE
                </span>
                <button 
                  onClick={runTraining}
                  disabled={isTraining}
                  className="p-1 hover:text-terminal-orange transition-all disabled:opacity-50">
                  <RefreshCw size={14} className={isTraining ? 'animate-spin' : ''} />
                </button>
             </div>
             <div className="flex-1 p-4">
                <ResponsiveContainer width="100%" height={200}>
                   <BarChart data={MOCK_ORACLE_FEATURES} layout="vertical">
                      <XAxis type="number" hide />
                      <YAxis dataKey="name" type="category" width={80} style={{ fontSize: '8px', fontFamily: 'monospace' }} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#0D1117', border: '1px solid #1C2333' }}
                        itemStyle={{ color: '#E6EDF3', fontSize: '10px' }}
                      />
                      <Bar dataKey="weight" fill="#58A6FF">
                        {MOCK_ORACLE_FEATURES.map((entry, index) => (
                           <motion.rect key={index} animate={isTraining ? { fill: ['#58A6FF', '#DB6D28', '#58A6FF'] } : {}} transition={{ repeat: Infinity, duration: 0.5 }} />
                        ))}
                      </Bar>
                   </BarChart>
                </ResponsiveContainer>
                <div className="mt-4 grid grid-cols-2 gap-2 text-[10px]">
                   <div className="p-2 bg-terminal-bg border border-terminal-border">
                      <div className="text-terminal-muted">CYCLES</div>
                      <div className="font-bold">48,209</div>
                   </div>
                   <div className="p-2 bg-terminal-bg border border-terminal-border">
                      <div className="text-terminal-muted">ERR_MAG</div>
                      <div className="font-bold text-terminal-green">0.0234</div>
                   </div>
                </div>
             </div>
          </div>

          {/* ADVERSARY PANEL */}
          <div className="bg-terminal-surface border border-terminal-border flex flex-col">
             <div className="p-3 border-b border-terminal-border flex justify-between items-center bg-terminal-red/5">
                <span className="text-xs font-bold text-terminal-red flex items-center gap-2">
                   <Shield size={14} /> ADVERSARY_MAP
                </span>
                <span className={`text-[10px] ${isTraining ? 'text-terminal-red animate-pulse' : 'text-terminal-muted'}`}>
                  {isTraining ? 'PRESSURE_HIGH' : 'STABLE'}
                </span>
             </div>
             <div className="flex-1 p-4">
                <div className="grid grid-cols-4 gap-1 h-32 mb-4">
                   {Array.from({ length: 16 }).map((_, i) => (
                      <div 
                        key={i} 
                        className="bg-terminal-red" 
                        style={{ opacity: Math.random() * 0.4 + 0.1 }}
                      />
                   ))}
                </div>
                <div className="space-y-2">
                   {['BLIND_SPOT_01', 'BLIND_SPOT_02', 'BLIND_SPOT_03'].map(spot => (
                      <div key={spot} className="flex justify-between items-center text-[10px]">
                         <span className="text-terminal-muted">{spot}</span>
                         <div className="w-24 h-1 bg-terminal-border">
                            <div className="h-full bg-terminal-red" style={{ width: `${Math.random() * 80}%` }} />
                         </div>
                      </div>
                   ))}
                </div>
             </div>
          </div>

          {/* MARKET PANEL */}
          <div className="bg-terminal-surface border border-terminal-border flex flex-col">
             <div className="p-3 border-b border-terminal-border flex justify-between items-center bg-terminal-green/5">
                <span className="text-xs font-bold text-terminal-green flex items-center gap-2">
                   <Activity size={14} /> MARKET_EFFICIENCY
                </span>
             </div>
             <div className="flex-1 p-4 flex flex-col items-center">
                <svg ref={arcRef} width="200" height="120" />
                <div className="text-center -mt-6">
                   <div className="text-2xl font-bold">{efficiency.toFixed(1)}%</div>
                   <div className="text-[10px] text-terminal-muted uppercase">Efficiency_Index</div>
                </div>
                <div className="mt-6 w-full space-y-1">
                   {['ALPHA_REMAINING', 'PRICED_IN_EDGE'].map((label, i) => (
                      <div key={label} className="flex justify-between text-[10px] p-1 border-b border-terminal-border border-dashed">
                         <span className="text-terminal-muted">{label}</span>
                         <span className={i === 0 ? 'text-terminal-green' : 'text-terminal-text'}>
                            {i === 0 ? '14.2%' : '85.8%'}
                         </span>
                      </div>
                   ))}
                </div>
             </div>
          </div>
       </div>

       {/* HISTORY BOTTOM PANEL */}
       <div className="h-48 bg-terminal-surface border border-terminal-border p-4">
          <div className="text-[10px] font-bold text-terminal-muted mb-4 tracking-widest uppercase">TRAINING_STABILITY_CURVE</div>
          <ResponsiveContainer width="100%" height="100%">
             <LineChart data={new Array(20).fill(0).map((_, i) => ({ i, val: 0.1 + Math.random() * 0.05 }))}>
                <Line type="monotone" dataKey="val" stroke="#DB6D28" strokeWidth={2} dot={false} />
             </LineChart>
          </ResponsiveContainer>
       </div>
    </div>
  )
}
