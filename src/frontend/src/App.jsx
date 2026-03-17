import React, { useState } from 'react'
import Topbar from './components/shared/Topbar.jsx'
import AnalystMode from './components/analyst/AnalystMode.jsx'
import BettorMode from './components/bettor/BettorMode.jsx'
import RosterMode from './components/roster/RosterMode.jsx'
import { useSignalFeed } from './hooks/useSignalFeed.js'
import './styles/globals.css'

const MODES = {
  analyst: AnalystMode,
  bettor:  BettorMode,
  roster:  RosterMode,
}

export default function App() {
  const [mode, setMode] = useState('analyst')
  const { connected } = useSignalFeed()

  const ModeComponent = MODES[mode]

  return (
    <div style={{ display:'grid', gridTemplateRows:'48px 1fr', height:'100vh', background:'var(--bg0)', overflow:'hidden' }}>
      <Topbar mode={mode} setMode={setMode} wsConnected={connected} />
      <div style={{ overflow:'hidden', animation:'fade-in 0.2s ease-out' }} key={mode}>
        <ModeComponent />
      </div>
    </div>
  )
}
