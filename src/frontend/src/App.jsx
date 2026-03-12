import React, { useState, useEffect } from 'react';
import { Download, ChevronDown, ChevronRight, Activity } from 'lucide-react';

const RosterApp = () => {
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetch('/api/roster/warriors')
      .then(res => res.json())
      .then(data => {
        setPlayers(data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Error fetching roster:", err);
        setLoading(false);
      });
  }, []);

  const handleDownload = () => {
    window.location.href = '/api/download/warriors';
  };

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-xl font-semibold text-blue-400 flex items-center gap-3">
          <Activity className="animate-spin" /> Fetching Golden State Warriors DNA...
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-8">
      <header className="flex justify-between items-end mb-10 pb-6 border-b border-midnight-light/50">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight text-white mb-2">Rostra <span className="text-blue-500 font-light">V1</span></h1>
          <p className="text-slate-400">Epoch Engine payload translation. Authentic dynamics mapped to NBA 2K14.</p>
        </div>
        <button 
          onClick={handleDownload}
          className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-lg flex items-center gap-2 font-medium transition-colors shadow-lg shadow-blue-900/20"
        >
          <Download size={20} />
          Download .ROS
        </button>
      </header>

      <div className="bg-midnight-light/40 border border-slate-800 rounded-xl overflow-hidden backdrop-blur-sm">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-midnight-light/60 text-slate-300 text-sm uppercase tracking-wider border-b border-slate-800">
              <th className="py-4 px-6 w-12 text-center"></th>
              <th className="py-4 px-6 font-semibold">Player</th>
              <th className="py-4 px-6 font-semibold">SSht3PT (Default &rarr; Scaled)</th>
              <th className="py-4 px-6 font-semibold">TPNR (Default &rarr; Scaled)</th>
              <th className="py-4 px-6 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {players.map((p, idx) => {
              const hasDiff = p.before.SSht3PT !== p.after.SSht3PT || p.before.TPNR !== p.after.TPNR;
              const isExpanded = expandedId === p.name;
              
              return (
                <React.Fragment key={p.name}>
                  <tr 
                    onClick={() => toggleExpand(p.name)}
                    className={`border-b border-slate-800 cursor-pointer hover:bg-slate-800/40 transition-colors ${idx % 2 === 0 ? 'bg-transparent' : 'bg-midnight-light/10'}`}
                  >
                    <td className="py-4 px-6 text-slate-500">
                      {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                    </td>
                    <td className="py-4 px-6 font-medium text-white text-lg">{p.name}</td>
                    <td className="py-4 px-6">
                      <span className="text-slate-500">{p.before.SSht3PT}</span>
                      <span className="mx-2 text-slate-600">&rarr;</span>
                      <span className={`font-semibold ${p.before.SSht3PT !== p.after.SSht3PT ? 'text-blue-400' : 'text-slate-300'}`}>
                        {p.after.SSht3PT}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <span className="text-slate-500">{p.before.TPNR}</span>
                      <span className="mx-2 text-slate-600">&rarr;</span>
                      <span className={`font-semibold ${p.before.TPNR !== p.after.TPNR ? 'text-blue-400' : 'text-slate-300'}`}>
                        {p.after.TPNR}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      {hasDiff ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                          Translated
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">
                          Untouched
                        </span>
                      )}
                    </td>
                  </tr>
                  
                  {isExpanded && (
                    <tr>
                      <td colSpan="5" className="px-0 py-0 border-b border-slate-800 bg-slate-900/50">
                        <div className="p-8 pb-10 grid grid-cols-3 gap-6">
                          <div>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">Scoring Skills</h4>
                            <div className="space-y-3">
                              {['SSht3PT', 'SShtMR', 'SShtFT', 'SShtClose'].map(f => (
                                <div key={f} className="flex justify-between items-center text-sm">
                                  <span className="text-slate-400">{f.replace('SSht', 'Shot ')}</span>
                                  <div className="flex items-center gap-3">
                                    <span className="text-slate-600">{p.before[f]}</span>
                                    {p.before[f] !== p.after[f] ? (
                                      <span className="text-blue-400 font-bold">{p.after[f]}</span>
                                    ) : (
                                      <span className="text-slate-300 font-medium">{p.after[f]}</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                          
                          <div>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">Playmaking Tendencies</h4>
                            <div className="space-y-3">
                              {['TIso', 'TPNR', 'TSpotUp', 'TTransition'].map(f => (
                                <div key={f} className="flex justify-between items-center text-sm">
                                  <span className="text-slate-400">{f.replace('T', '')}</span>
                                  <div className="flex items-center gap-3">
                                    <span className="text-slate-600">{p.before[f]}</span>
                                    {p.before[f] !== p.after[f] ? (
                                      <span className="text-blue-400 font-bold">{p.after[f]}</span>
                                    ) : (
                                      <span className="text-slate-300 font-medium">{p.after[f]}</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">Playmaking Skills</h4>
                            <div className="space-y-3">
                              {['SDribble', 'SPass'].map(f => (
                                <div key={f} className="flex justify-between items-center text-sm">
                                  <span className="text-slate-400">{f.replace('S', '')}</span>
                                  <div className="flex items-center gap-3">
                                    <span className="text-slate-600">{p.before[f]}</span>
                                    {p.before[f] !== p.after[f] ? (
                                      <span className="text-blue-400 font-bold">{p.after[f]}</span>
                                    ) : (
                                      <span className="text-slate-300 font-medium">{p.after[f]}</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RosterApp;
