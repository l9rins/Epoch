import { Flame } from 'lucide-react';

export default function MomentumGauge({ momentum }) {
  const momValue = momentum || 0;
  const momMagnitude = Math.min(Math.abs(momValue), 100);
  const momColor = momValue > 0 ? 'bg-emerald-500' : 'bg-red-500';

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-6 flex items-center gap-2">
        <Flame className="w-4 h-4 text-orange-500" /> Momentum Vector
      </h3>
      
      <div className="relative h-12 w-full bg-slate-950 rounded-full border border-slate-800 overflow-hidden shadow-[inset_0_2px_10px_rgba(0,0,0,0.5)]">
        {/* Center markers */}
        <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-slate-600 z-10" />
        <div className="absolute top-1/2 left-1/4 w-0.5 h-2 -mt-1 bg-slate-700 z-10" />
        <div className="absolute top-1/2 right-1/4 w-0.5 h-2 -mt-1 bg-slate-700 z-10" />
        
        {/* The animated dynamic bar */}
        <div 
          className={`absolute top-0 bottom-0 transition-all duration-300 ease-out ${momColor}`}
          style={{
            width: `${momMagnitude / 2}%`,
            left: momValue > 0 ? '50%' : `${50 - (momMagnitude / 2)}%`,
            boxShadow: momValue > 0 ? '0 0 15px rgba(16, 185, 129, 0.5)' : '0 0 15px rgba(239, 68, 68, 0.5)'
          }}
        />
      </div>
      
      <div className="flex justify-between mt-3 text-xs font-mono font-bold">
        <span className="text-red-400 tracking-wider">AWAY EDGE</span>
        <span className="text-slate-500 font-sans font-medium">Value: {momValue.toFixed(1)}</span>
        <span className="text-emerald-400 tracking-wider">HOME EDGE</span>
      </div>
    </div>
  );
}
