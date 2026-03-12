import { FileText, Sparkles, Loader2, Flame, Network, Activity, AlertTriangle, TimerReset } from 'lucide-react';

export default function ScoutingReport({ report, isGenerating, generateReport }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg flex-1 overflow-y-auto custom-scrollbar relative min-h-[500px]">
      <h3 className="text-lg font-semibold text-slate-200 mb-6 flex items-center gap-2 border-b border-slate-800 pb-4">
        <FileText className="w-5 h-5 text-purple-400" /> System C: Causal Scouting Report
      </h3>
      
      {!report ? (
        <div className="flex flex-col items-center justify-center h-64 text-slate-400">
          <Sparkles className="w-12 h-12 mb-4 text-slate-700" />
          <p className="mb-6 text-center max-w-sm">Synthesize live simulation telemetry, knowledge graph embeddings, and situational context into a narrative causal chain.</p>
          <button 
            onClick={generateReport}
            disabled={isGenerating}
            className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2.5 rounded-lg flex items-center gap-2 font-medium transition-colors shadow-lg shadow-purple-900/20"
          >
            {isGenerating ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
            {isGenerating ? "Synthesizing Insights..." : "Generate LLM Report"}
          </button>
        </div>
      ) : (
        <div className="prose prose-invert prose-purple max-w-none">
          {report.split('\n\n').map((paragraph, i) => {
            // Quick styling for specific paragraphs expected from our prompt
            const isEdge = i === 0 || paragraph.includes('Edge');
            const isMechanism = i === 1 || paragraph.includes('Chain') || paragraph.includes('Mechanism');
            const isSignals = i === 2 || paragraph.includes('Signal');
            const isRisks = i === 3 || paragraph.includes('Risk');

            return (
              <div key={i} className={`p-4 rounded-xl mb-4 border ${
                isEdge ? 'bg-emerald-500/10 border-emerald-500/30' :
                isMechanism ? 'bg-blue-500/10 border-blue-500/30' :
                isSignals ? 'bg-purple-500/10 border-purple-500/30' :
                isRisks ? 'bg-orange-500/10 border-orange-500/30' : 'bg-slate-800/50 border-slate-700'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  {isEdge && <Flame className="w-4 h-4 text-emerald-400" />}
                  {isMechanism && <Network className="w-4 h-4 text-blue-400" />}
                  {isSignals && <Activity className="w-4 h-4 text-purple-400" />}
                  {isRisks && <AlertTriangle className="w-4 h-4 text-orange-400" />}
                  <h4 className={`text-sm font-bold tracking-wider uppercase m-0 ${
                    isEdge ? 'text-emerald-400' :
                    isMechanism ? 'text-blue-400' :
                    isSignals ? 'text-purple-400' :
                    isRisks ? 'text-orange-400' : 'text-slate-300'
                  }`}>
                    {isEdge ? "The Edge" : isMechanism ? "Causal Mechanism" : isSignals ? "System Confirmation" : isRisks ? "Invalidation Risks" : "Analysis"}
                  </h4>
                </div>
                <p className="m-0 text-slate-300 leading-relaxed text-sm">
                  {paragraph.replace(/^(THE EDGE:|Causal Chain \(Mocked\):|Signals confirm|Risks:)/i, '').trim()}
                </p>
              </div>
            );
          })}
          
          <div className="mt-8 flex justify-end">
            <button 
              onClick={generateReport}
              disabled={isGenerating}
              className="text-slate-400 hover:text-white text-sm flex items-center gap-2 transition-colors"
            >
              {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <TimerReset size={14} />}
              Re-generate from current state
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
