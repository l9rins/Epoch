import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

export default function WinProbabilityChart({ history, currentProb }) {
  const displayProb = currentProb ? (currentProb * 100).toFixed(1) : 50.0;
  
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg relative overflow-hidden group flex-1">
      <div className="absolute inset-0 bg-gradient-to-b from-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
      <h3 className="text-lg font-semibold text-slate-200 mb-4 flex items-center justify-between">
        Real-Time Win Probability
        <span className="text-2xl font-mono text-blue-400 font-bold bg-blue-500/10 px-3 py-1 rounded-lg border border-blue-500/20">
          {displayProb}%
        </span>
      </h3>
      <div className="h-4/5 w-full min-h-[250px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={history} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} vertical={false} />
            <XAxis dataKey="time" stroke="#64748b" tick={{fill: '#64748b'}} tickLine={false} axisLine={false} minTickGap={30} />
            <YAxis domain={[0, 100]} stroke="#64748b" tick={{fill: '#64748b'}} tickLine={false} axisLine={false} width={40} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)' }}
              itemStyle={{ color: '#60a5fa', fontWeight: 'bold' }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <ReferenceLine y={50} stroke="#475569" strokeDasharray="3 3" opacity={0.5} />
            <Line 
              type="monotone" 
              dataKey="wp" 
              stroke="#3b82f6" 
              strokeWidth={3} 
              dot={false}
              activeDot={{ r: 6, fill: '#60a5fa', stroke: '#1e3a8a', strokeWidth: 2 }}
              isAnimationActive={false} // Prevent jumpy re-renders on rapid ticks
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
