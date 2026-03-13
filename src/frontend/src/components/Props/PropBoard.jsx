import React, { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Filter, TrendingUp, Info, Zap } from 'lucide-react'

const MOCK_PROPS = [
  { id: 1, player: 'Stephen Curry', prop: 'Points', line: 28.5, over: 0.62, edge: 0.08, confidence: 'High', distribution: d3.randomNormal(29.2, 4) },
  { id: 2, player: 'Draymond Green', prop: 'Assists', line: 7.5, over: 0.54, edge: 0.03, confidence: 'Med', distribution: d3.randomNormal(7.8, 2) },
  { id: 3, player: 'Andrew Wiggins', prop: 'Rebounds', line: 5.5, over: 0.48, edge: -0.01, confidence: 'Low', distribution: d3.randomNormal(5.2, 1.5) },
]

function PropCurve({ distribution, line, color = '#58A6FF' }) {
  const svgRef = useRef()
  
  useEffect(() => {
    if (!svgRef.current) return
    const width = 280
    const height = 100
    const margin = { top: 10, right: 10, bottom: 20, left: 10 }

    const svg = d3.select(svgRef.current)
    svg.selectAll("*").remove()

    // Generate samples for the curve
    const samples = Array.from({ length: 1000 }, distribution)
    const x = d3.scaleLinear()
      .domain([d3.min(samples), d3.max(samples)])
      .range([margin.left, width - margin.right])

    const bins = d3.bin()
      .domain(x.domain())
      .thresholds(40)(samples)

    const y = d3.scaleLinear()
      .domain([0, d3.max(bins, d => d.length)])
      .range([height - margin.bottom, margin.top])

    const area = d3.area()
      .x(d => x(d.x0 + (d.x1 - d.x0) / 2))
      .y0(y(0))
      .y1(d => y(d.length))
      .curve(d3.curveBasis)

    // Shaded areas for Over/Under
    svg.append("path")
      .datum(bins)
      .attr("fill", "#F8514933") // Red for Under
      .attr("d", area)

    svg.append("clipPath")
      .attr("id", `clip-over-${color.replace('#', '')}`)
      .append("rect")
      .attr("x", x(line))
      .attr("y", 0)
      .attr("width", width - x(line))
      .attr("height", height)

    svg.append("path")
      .datum(bins)
      .attr("fill", "#3FB95066") // Green for Over
      .attr("clip-path", `url(#clip-over-${color.replace('#', '')})`)
      .attr("d", area)

    // Border line
    const lineGen = d3.line()
      .x(d => x(d.x0 + (d.x1 - d.x0) / 2))
      .y(d => y(d.length))
      .curve(d3.curveBasis)

    svg.append("path")
      .datum(bins)
      .attr("fill", "none")
      .attr("stroke", color)
      .attr("stroke-width", 1.5)
      .attr("d", lineGen)
      .attr("stroke-dasharray", function() { return this.getTotalLength() })
      .attr("stroke-dashoffset", function() { return this.getTotalLength() })
      .transition()
      .duration(600)
      .attr("stroke-dashoffset", 0)

    // Prop Line
    svg.append("line")
      .attr("x1", x(line))
      .attr("x2", x(line))
      .attr("y1", margin.top)
      .attr("y2", height - margin.bottom)
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "2,2")

    // Mean Line
    const mean = d3.mean(samples)
    svg.append("line")
      .attr("x1", x(mean))
      .attr("x2", x(mean))
      .attr("y1", margin.top)
      .attr("y2", height - margin.bottom)
      .attr("stroke", color)
      .attr("stroke-width", 1)
      .attr("opacity", 0.5)

  }, [distribution, line, color])

  return <svg ref={svgRef} width="280" height="100" className="overflow-visible" />
}

export default function PropBoard() {
  const [filter, setFilter] = useState('')

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center bg-terminal-surface border border-terminal-border p-4">
        <div className="flex items-center gap-4">
           <Zap className="text-terminal-yellow" size={18} />
           <span className="text-sm font-bold tracking-widest uppercase">PROP_CONVICTION_BOARD</span>
        </div>
        <div className="flex items-center gap-2">
           <div className="relative">
             <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-terminal-muted" />
             <input 
               type="text" 
               placeholder="SEARCH_PLAYER..."
               className="bg-terminal-bg border border-terminal-border pl-9 pr-4 py-1.5 text-xs outline-none focus:border-terminal-orange w-64"
               onChange={(e) => setFilter(e.target.value)}
             />
           </div>
           <button className="p-2 border border-terminal-border hover:border-terminal-orange transition-all">
             <Filter size={14} />
           </button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-6">
        {MOCK_PROPS.filter(p => p.player.toLowerCase().includes(filter.toLowerCase())).map(prop => (
          <motion.div 
            key={prop.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-terminal-surface border border-terminal-border flex flex-col group hover:border-terminal-orange transition-all">
            
            <div className="p-4 border-b border-terminal-border flex justify-between items-start">
               <div>
                  <div className="text-xs font-bold text-terminal-orange mb-0.5">{prop.player}</div>
                  <div className="text-[10px] text-terminal-muted uppercase">{prop.prop} · {prop.line}</div>
               </div>
               <div className={`px-2 py-0.5 text-[8px] font-bold border ${
                 prop.confidence === 'High' ? 'border-terminal-green text-terminal-green' : 'border-terminal-yellow text-terminal-yellow'
               }`}>
                 {prop.confidence}_CONF
               </div>
            </div>

            <div className="p-4 flex flex-col items-center">
               <PropCurve distribution={prop.distribution} line={prop.line} color={prop.edge > 0 ? '#3FB950' : '#58A6FF'} />
               
               <div className="grid grid-cols-3 w-full gap-2 mt-4 text-center">
                  <div className="p-2 bg-terminal-bg border border-terminal-border">
                     <div className="text-[8px] text-terminal-muted uppercase mb-1">Over_%</div>
                     <div className="text-xs font-bold">{(prop.over * 100).toFixed(1)}%</div>
                  </div>
                  <div className="p-2 bg-terminal-bg border border-terminal-border">
                     <div className="text-[8px] text-terminal-muted uppercase mb-1">EV_Edge</div>
                     <div className={`text-xs font-bold ${prop.edge > 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                        {prop.edge > 0 ? '+' : ''}{(prop.edge * 100).toFixed(1)}%
                     </div>
                  </div>
                  <div className="p-2 bg-terminal-bg border border-terminal-border">
                     <div className="text-[8px] text-terminal-muted uppercase mb-1">Conviction</div>
                     <div className="text-xs font-bold uppercase">{prop.confidence}</div>
                  </div>
               </div>
            </div>

            <div className="mt-auto border-t border-terminal-border p-2 bg-terminal-bg/50 overflow-hidden">
               <button className="w-full text-[9px] text-terminal-muted hover:text-terminal-orange transition-all flex items-center justify-center gap-2">
                  <Info size={10} />
                  VIEW_CAUSAL_FACTORS_DROPDOWN
               </button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
