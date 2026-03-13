import React from 'react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { TrendingUp, Target, Award, Hash, ArrowUpRight, ArrowDownRight } from 'lucide-react'

const MOCK_JOURNAL_DATA = [
  { date: '2026-03-01', roi: 0.02 },
  { date: '2026-03-02', roi: 0.035 },
  { date: '2026-03-03', roi: 0.031 },
  { date: '2026-03-04', roi: 0.048 },
  { date: '2026-03-05', roi: 0.062 },
  { date: '2026-03-06', roi: 0.082 },
]

const MOCK_LEDGER = [
  { id: 1, type: 'T1_CLUTCH', game: 'GSW vs LAL', edge: '+8.2%', amount: '$420', status: 'WIN', payout: '+$378', date: '03/06' },
  { id: 2, type: 'T2_MOMENTUM', game: 'PHX vs DEN', edge: '+4.5%', amount: '$150', status: 'LOSS', payout: '-$150', date: '03/05' },
  { id: 3, type: 'T1_ANOMALY', game: 'MIL vs BOS', edge: '+9.1%', amount: '$600', status: 'WIN', payout: '+$510', date: '03/05' },
]

export default function JournalDashboard() {
  return (
    <div className="p-6 space-y-6 flex flex-col h-full overflow-y-auto">
       {/* TOP METRICS */}
       <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'CUMULATIVE_ROI', val: '+8.2%', icon: TrendingUp, color: 'text-terminal-green' },
            { label: 'ESTABLISHED_EDGE', val: '+4.12%', icon: Target, color: 'text-terminal-accent' },
            { label: 'TOTAL_BETS', val: '154', icon: Hash, color: 'text-terminal-text' },
            { label: 'BEST_SIGNAL', val: 'T1_CLUTCH', icon: Award, color: 'text-terminal-orange' },
          ].map((m, i) => (
            <div key={i} className="bg-terminal-surface border border-terminal-border p-4 flex flex-col gap-2">
               <div className="flex justify-between items-center">
                  <span className="text-[10px] text-terminal-muted font-bold tracking-widest">{m.label}</span>
                  <m.icon size={14} className="text-terminal-muted" />
               </div>
               <div className={`text-xl font-bold ${m.color}`}>{m.val}</div>
            </div>
          ))}
       </div>

       {/* ROI CHART */}
       <div className="bg-terminal-surface border border-terminal-border p-6 h-64">
          <div className="flex justify-between items-center mb-6">
             <span className="text-[10px] font-bold text-terminal-muted uppercase tracking-widest">Performance_Trajectory_Cumulative</span>
             <div className="flex gap-4 text-[10px]">
                <span className="text-terminal-green flex items-center gap-1"><ArrowUpRight size={12}/> +12.4% MoM</span>
             </div>
          </div>
          <ResponsiveContainer width="100%" height="100%">
             <AreaChart data={MOCK_JOURNAL_DATA}>
                <defs>
                   <linearGradient id="colorRoi" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3FB950" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3FB950" stopOpacity={0}/>
                   </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1C2333" vertical={false} />
                <XAxis dataKey="date" hide />
                <YAxis hide domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0D1117', border: '1px solid #1C2333' }}
                  itemStyle={{ color: '#E6EDF3', fontSize: '10px' }}
                />
                <Area type="monotone" dataKey="roi" stroke="#3FB950" fillOpacity={1} fill="url(#colorRoi)" strokeWidth={2} />
             </AreaChart>
          </ResponsiveContainer>
       </div>

       {/* LEDGER */}
       <div className="flex-1 bg-terminal-surface border border-terminal-border flex flex-col min-h-0">
          <div className="p-4 border-b border-terminal-border flex justify-between items-center bg-terminal-surface">
             <span className="text-xs font-bold uppercase tracking-widest">Betting_Ledger_History</span>
             <button className="text-[10px] text-terminal-orange hover:underline">EXPORT_CSV</button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
             <table className="w-full text-[10px] border-separate border-spacing-y-1">
                <thead>
                   <tr className="text-terminal-muted text-left uppercase text-[8px] bg-terminal-bg">
                      <th className="p-2">Date</th>
                      <th className="p-2">Signal_Type</th>
                      <th className="p-2">Matchup</th>
                      <th className="p-2 text-right">Edge</th>
                      <th className="p-2 text-right">Sizing</th>
                      <th className="p-2 text-center">Result</th>
                      <th className="p-2 text-right">PNL</th>
                   </tr>
                </thead>
                <tbody>
                   {MOCK_LEDGER.map(row => (
                      <tr key={row.id} className="bg-terminal-bg border border-terminal-border hover:bg-terminal-surface cursor-pointer group">
                         <td className="p-2 text-terminal-muted">{row.date}</td>
                         <td className="p-2">
                            <span className={`px-1.5 py-0.5 border ${
                              row.type.startsWith('T1') ? 'border-terminal-orange text-terminal-orange' : 'border-terminal-yellow text-terminal-yellow'
                            }`}>
                               {row.type}
                            </span>
                         </td>
                         <td className="p-2 font-bold">{row.game}</td>
                         <td className="p-2 text-right text-terminal-green">{row.edge}</td>
                         <td className="p-2 text-right">{row.amount}</td>
                         <td className="p-2 text-center text-[8px] font-bold">
                            <span className={row.status === 'WIN' ? 'text-terminal-green' : 'text-terminal-red'}>{row.status}</span>
                         </td>
                         <td className={`p-2 text-right font-bold ${row.payout.startsWith('+') ? 'text-terminal-green' : 'text-terminal-red'}`}>
                            {row.payout}
                         </td>
                      </tr>
                   ))}
                </tbody>
             </table>
          </div>
       </div>
    </div>
  )
}
