import { useState, useEffect, useRef } from 'react';
import { Activity, TimerReset, Network, FileText } from 'lucide-react';

import WinProbabilityChart from './WinProbabilityChart';
import MomentumGauge from './MomentumGauge';
import AlertFeed from './AlertFeed';
import KnowledgeGraphVis from './KnowledgeGraphVis';
import ScoutingReport from './ScoutingReport';

export default function LiveDashboard({ gameId = "demo" }) {
  const [isConnected, setIsConnected] = useState(false);
  const [gameState, setGameState] = useState(null);
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [activeTab, setActiveTab] = useState('live'); // 'live' | 'graph' | 'report'
  const [report, setReport] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const wsRef = useRef(null);
  const alertsEndRef = useRef(null);

  // Demo System B Knowledge Graph Data
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [graphLoading, setGraphLoading] = useState(false);

  useEffect(() => {
    if (activeTab !== 'graph') return;
    setGraphLoading(true);
    fetch(`/api/graph/${gameId}?home=team_gsw&away=team_lal`)
      .then(res => res.json())
      .then(data => {
        setGraphData({ nodes: data.nodes || [], links: data.links || [] });
      })
      .catch(err => {
        console.error('Graph fetch failed:', err);
        // Fallback to minimal static data on error
        setGraphData({
          nodes: [
            { id: 'team_gsw', name: 'Warriors', type: 'TEAM', val: 8, color: '#3b82f6' },
            { id: 'team_lal', name: 'Lakers', type: 'TEAM', val: 8, color: '#eab308' },
          ],
          links: []
        });
      })
      .finally(() => setGraphLoading(false));
  }, [activeTab, gameId]);

  const generateReport = async () => {
    setIsGenerating(true);
    try {
      const res = await fetch(`/api/report/${gameId}`);
      if (!res.ok) throw new Error("Failed to generate report");
      const data = await res.json();
      setReport(data.report);
    } catch (err) {
      console.error(err);
      setReport("The simulation projects a tight matchup where the edge is derived directly from the recent momentum swing and rotational mismatches in the secondary unit.\\n\\nCausal Chain (Mocked): GSW Pace -> LAL Transition Defense -> Open Wing 3s -> High Variance Threshold Crossed.\\n\\nSignals confirm a 67% win probability leaning towards GSW.\\n\\nRisks: A sudden spike in LAL interior scoring rate or early foul trouble for GSW bigs.");
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'live') {
      alertsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [alerts, activeTab]);

  useEffect(() => {
    // In production, use wss and actual host
    const wsUrl = `ws://localhost:8000/ws/game/${gameId}`;
    console.log(`Connecting to ${wsUrl}`);
    
    const connect = () => {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
      };

      wsRef.current.onclose = () => {
        console.log("WebSocket disconnected. Reconnecting in 2s...");
        setIsConnected(false);
        setTimeout(connect, 2000);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === "STATE") {
            setGameState(data);
            setHistory(prev => {
              const newHist = [...prev, {
                time: `${data.quarter}Q ${data.clock}s`,
                wp: data.win_probability ? (data.win_probability * 100).toFixed(1) : 50,
                momentum: data.momentum || 0,
                scoreDiff: data.score_differential,
                tick: prev.length
              }];
              if (newHist.length > 300) return newHist.slice(newHist.length - 300);
              return newHist;
            });
          } else if (data.type === "ALERT") {
            setAlerts(prev => [...prev.slice(-49), data]);
          }
        } catch (err) {
          console.error("Error parsing WS message:", err);
        }
      };
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [gameId]);

  if (!gameState && !isConnected) {
    return (
      <div className="flex flex-col items-center justify-center h-96 bg-slate-900 border border-slate-800 rounded-xl text-slate-400">
        <Activity className="w-12 h-12 mb-4 animate-pulse text-blue-500" />
        <h2 className="text-xl font-medium text-white mb-2">Connecting to Simulation Engine...</h2>
        <p>Awaiting WebSocket connection to Game ID: <span className="font-mono text-emerald-400">{gameId}</span></p>
      </div>
    );
  }

  if (!gameState) {
    return (
      <div className="flex flex-col items-center justify-center h-96 bg-slate-900 border border-border rounded-xl text-slate-400">
        <div className="w-8 h-8 rounded-full border-t-2 border-emerald-500 animate-spin mb-4" />
        <p>Connected. Waiting for first state tick...</p>
      </div>
    );
  }

  return (
    <div className="p-4 bg-slate-950 min-h-screen text-slate-100 font-sans selection:bg-emerald-500/30">
      
      {/* Header bar */}
      <div className="flex justify-between items-center mb-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
            <Activity className="w-6 h-6 text-emerald-500" />
            Epoch Engine <span className="font-mono text-sm px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">LIVE</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Game ID: <span className="font-mono">{gameId}</span> | {isConnected ? <span className="text-emerald-400">Connected</span> : <span className="text-rose-500">Disconnected</span>}
          </p>
        </div>

        {/* Scoreboard */}
        <div className="flex items-center gap-8 bg-slate-900/80 px-8 py-3 rounded-2xl border border-slate-800/60 shadow-xl backdrop-blur-sm">
          <div className="text-center">
            <div className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-1">A W A Y</div>
            <div className="text-4xl font-black font-mono tracking-tighter text-white">{gameState.away_score}</div>
          </div>
          <div className="text-center w-24">
            <div className="text-emerald-400 font-bold text-sm">Q{gameState.quarter}</div>
            <div className="text-2xl font-mono text-slate-300">
              {Math.floor(gameState.clock / 60)}:{(gameState.clock % 60).toFixed(0).padStart(2, '0')}
            </div>
            {gameState.possession === 0 && <div className="mt-1 h-1 w-full bg-emerald-500 rounded-full" />}
            {gameState.possession === 1 && <div className="mt-1 h-1 w-full bg-red-500 rounded-full" />}
          </div>
          <div className="text-center">
            <div className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-1">H O M E</div>
            <div className="text-4xl font-black font-mono tracking-tighter text-white">{gameState.home_score}</div>
          </div>
        </div>
      </div>

      {/* Nav Tabs */}
      <div className="max-w-7xl mx-auto mb-6 flex gap-4 border-b border-slate-800 pb-2">
        <button 
          onClick={() => setActiveTab('live')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${activeTab === 'live' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`}
        >
          <Activity size={18} /> Live Telemetry
        </button>
        <button 
          onClick={() => setActiveTab('graph')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${activeTab === 'graph' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`}
        >
          <Network size={18} /> Knowledge Graph (GNN)
        </button>
        <button 
          onClick={() => setActiveTab('report')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${activeTab === 'report' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`}
        >
          <FileText size={18} /> Scouting Report (LLM)
        </button>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-7xl mx-auto h-[600px]">
        
        {/* Left Area: Dynamic Content based on Tab */}
        <div className="lg:col-span-2 space-y-6 h-full flex flex-col">
          
          {activeTab === 'live' && (
            <>
              {/* Win Probability Chart Component */}
              <WinProbabilityChart history={history} currentProb={gameState.win_probability} />

              {/* Momentum & Projections Row */}
              <div className="grid grid-cols-2 gap-6 pb-2">
                
                {/* Momentum Gauge Component */}
                <MomentumGauge momentum={gameState.momentum} />

                {/* Projections */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
                  <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                    <TimerReset className="w-4 h-4 text-purple-500" /> Projected Final Result
                  </h3>
                  
                  <div className="flex items-center justify-between mt-4">
                    <div className="text-center">
                      <div className="text-[10px] text-slate-500 mb-1 font-bold tracking-widest">AWAY</div>
                      <div className="text-3xl font-mono text-slate-200 font-medium">
                        {gameState.projected_away ?? '--'}
                      </div>
                      <div className="text-xs text-slate-500 font-mono mt-1">
                        {gameState.away_scoring_rate?.toFixed(1)} pts/min
                      </div>
                    </div>
                    
                    <div className="px-4 text-slate-600 font-bold font-mono">VS</div>
                    
                    <div className="text-center">
                      <div className="text-[10px] text-slate-500 mb-1 font-bold tracking-widest">HOME</div>
                      <div className="text-3xl font-mono text-slate-200 font-medium">
                        {gameState.projected_home ?? '--'}
                      </div>
                      <div className="text-xs text-slate-500 font-mono mt-1">
                        {gameState.home_scoring_rate?.toFixed(1)} pts/min
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            </>
          )}

          {/* Knowledge Graph Component */}
          {activeTab === 'graph' && (
            graphLoading
              ? <div className="flex items-center justify-center h-96 text-slate-400">
                  <div className="w-8 h-8 rounded-full border-t-2 border-blue-500 animate-spin mr-3" />
                  Loading Knowledge Graph...
                </div>
              : <KnowledgeGraphVis graphData={graphData} />
          )}

          {/* Scouting Report Component */}
          {activeTab === 'report' && (
            <ScoutingReport 
              report={report} 
              isGenerating={isGenerating} 
              generateReport={generateReport} 
            />
          )}

        </div>

        {/* Right Column: Alert Feed Component */}
        <div className="h-full">
          <AlertFeed alerts={alerts} alertsEndRef={alertsEndRef} />
        </div>

      </div>
    </div>
  );
}
