import React from 'react'

const MODES = ['analyst', 'bettor', 'roster']

const modeStyle = {
  analyst: { background: 'rgba(0,230,118,0.1)',   color: 'var(--green)',  border: '1px solid rgba(0,230,118,0.2)' },
  bettor:  { background: 'rgba(41,121,255,0.12)', color: 'var(--blue)',   border: '1px solid rgba(41,121,255,0.2)' },
  roster:  { background: 'rgba(255,171,0,0.10)',  color: 'var(--amber)',  border: '1px solid rgba(255,171,0,0.2)' },
}

export default function Topbar({ mode, setMode, wsConnected, user, tier, onLogout }) {
  return (
    <div style={{
      background: 'var(--bg1)',
      borderBottom: '1px solid var(--bg3)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px',
      gap: 16,
      height: 48,
      flexShrink: 0,
      zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{ fontFamily: 'var(--display)', fontSize: 20, fontWeight: 800, letterSpacing: '0.15em', color: 'var(--text0)', display: 'flex', alignItems: 'center', gap: 6 }}>
        EPOCH
        <span style={{ width: 7, height: 7, background: 'var(--green)', borderRadius: '50%', display: 'inline-block', animation: 'blink 2s ease-in-out infinite' }} />
      </div>

      {/* Mode switcher */}
      <div style={{ display: 'flex', gap: 2, background: 'var(--bg0)', border: '1px solid var(--bg3)', borderRadius: 'var(--r8)', padding: 3 }}>
        {MODES.map(m => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              fontFamily: 'var(--mono)',
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.12em',
              padding: '5px 16px',
              borderRadius: 5,
              cursor: 'pointer',
              border: 'none',
              transition: 'all 0.15s',
              textTransform: 'uppercase',
              ...(mode === m ? modeStyle[m] : { background: 'transparent', color: 'var(--text2)' }),
            }}
          >
            {m}
          </button>
        ))}
      </div>

      {/* Right status */}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', letterSpacing: '0.1em' }}>
          NBA 2025–26
        </span>
        <div style={{
          fontFamily: 'var(--mono)',
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: '0.15em',
          background: wsConnected ? 'rgba(0,230,118,0.1)' : 'rgba(255,61,61,0.1)',
          color: wsConnected ? 'var(--green)' : 'var(--red)',
          border: `1px solid ${wsConnected ? 'rgba(0,230,118,0.25)' : 'rgba(255,61,61,0.25)'}`,
          padding: '4px 10px',
          borderRadius: 20,
          display: 'flex',
          alignItems: 'center',
          gap: 5,
        }}>
          <span style={{ width: 5, height: 5, background: wsConnected ? 'var(--green)' : 'var(--red)', borderRadius: '50%', display: 'inline-block', animation: 'blink 1.5s ease-in-out infinite' }} />
          {wsConnected ? 'LIVE' : 'OFFLINE'}
        </div>
      </div>
    </div>
  )
}
