import React from 'react';
import LiveDashboard from './LiveDashboard';

// In a real app, gameId would come from a router like reactivation-router-dom
function App() {
  return (
    <div className="bg-slate-950 min-h-screen">
      <LiveDashboard gameId="demo" />
    </div>
  );
}

export default App;
