import { Bell, ShieldAlert, Zap } from 'lucide-react';

export default function AlertFeed({ alerts, alertsEndRef }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-lg flex flex-col h-full overflow-hidden">
      <div className="p-4 border-b border-slate-800/80 bg-slate-900/50 backdrop-blur-md">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
          <Zap className="w-4 h-4 text-yellow-500" /> Live Signal Feed
        </h3>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
        {alerts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600">
            <Bell className="w-8 h-8 mb-2 opacity-50" />
            <p className="text-sm">Listening for signals...</p>
          </div>
        ) : (
          alerts.map((alert, i) => {
            // Tier 1: Red border + glow, Tier 2: Orange border, Tier 3: Slate
            const isT1 = alert.tier === 1;
            const isT2 = alert.tier === 2;
            
            return (
              <div 
                key={i} 
                className={`p-3 rounded-lg border text-sm backdrop-blur-sm transition-all animate-in fade-in slide-in-from-right-4 duration-300
                  ${isT1 ? 'bg-rose-500/10 border-rose-500/50 shadow-[0_0_15px_rgba(225,29,72,0.15)]' : 
                    isT2 ? 'bg-amber-500/10 border-amber-500/40' : 
                    'bg-slate-800/50 border-slate-700/50 text-slate-300'}
                `}
              >
                <div className="flex items-start gap-2">
                  {isT1 && <ShieldAlert className="w-4 h-4 text-rose-500 mt-0.5 shrink-0" />}
                  {!isT1 && <Bell className={`w-4 h-4 mt-0.5 shrink-0 ${isT2 ? 'text-amber-500' : 'text-slate-500'}`} />}
                  <div>
                    <div className="flex justify-between items-baseline mb-1">
                      <span className={`font-bold tracking-tight text-xs uppercase
                        ${isT1 ? 'text-rose-400' : isT2 ? 'text-amber-400' : 'text-slate-400'}
                      `}>
                        {alert.alert_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {new Date(alert.timestamp * 1000).toLocaleTimeString([], {hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit'})}
                      </span>
                    </div>
                    <p className={isT1 ? 'text-rose-100 font-medium' : isT2 ? 'text-amber-50' : ''}>
                      {alert.message}
                    </p>
                  </div>
                </div>
              </div>
            );
          })
        )}
        <div ref={alertsEndRef} />
      </div>
    </div>
  );
}
