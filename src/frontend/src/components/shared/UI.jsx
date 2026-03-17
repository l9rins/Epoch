import React from 'react'

const s = {
  panel: {
    background: 'var(--bg1)',
    border: '1px solid var(--bg3)',
    borderRadius: 'var(--r8)',
    overflow: 'hidden',
  },
  panelHdr: {
    padding: '10px 14px',
    borderBottom: '1px solid var(--bg3)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  panelTitle: {
    fontFamily: 'var(--mono)',
    fontSize: 9,
    fontWeight: 600,
    letterSpacing: '0.15em',
    color: 'var(--text2)',
    textTransform: 'uppercase',
  },
  panelTag: {
    fontFamily: 'var(--mono)',
    fontSize: 9,
    color: 'var(--green)',
  },
  panelBody: { padding: '12px 14px' },
}

export function Panel({ title, tag, children, style }) {
  return (
    <div style={{ ...s.panel, ...style }}>
      {title && (
        <div style={s.panelHdr}>
          <span style={s.panelTitle}>{title}</span>
          {tag && <span style={s.panelTag}>{tag}</span>}
        </div>
      )}
      <div style={s.panelBody}>{children}</div>
    </div>
  )
}

export function MetricCard({ label, value, sub, color = 'var(--text0)', style }) {
  return (
    <div style={{
      background: 'var(--bg2)',
      border: '1px solid var(--bg3)',
      borderRadius: 'var(--r8)',
      padding: 12,
      ...style,
    }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontFamily: 'var(--display)', fontSize: 28, fontWeight: 800, lineHeight: 1, color }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text2)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

export function SectionLabel({ children, style }) {
  return (
    <div style={{
      fontFamily: 'var(--mono)',
      fontSize: 9,
      fontWeight: 600,
      letterSpacing: '0.2em',
      color: 'var(--text2)',
      textTransform: 'uppercase',
      marginBottom: 6,
      ...style,
    }}>
      {children}
    </div>
  )
}

export function Badge({ tier, label }) {
  const styles = {
    T1:   { background: 'rgba(0,230,118,0.12)',  color: 'var(--green)',  border: '1px solid rgba(0,230,118,0.2)' },
    T2:   { background: 'rgba(255,171,0,0.10)',  color: 'var(--amber)',  border: '1px solid rgba(255,171,0,0.2)' },
    T3:   { background: 'rgba(41,121,255,0.10)', color: 'var(--blue)',   border: '1px solid rgba(41,121,255,0.2)' },
    NONE: { background: 'var(--bg2)',            color: 'var(--text3)',  border: '1px solid var(--bg3)' },
  }
  return (
    <span style={{
      fontFamily: 'var(--mono)',
      fontSize: 8,
      fontWeight: 600,
      letterSpacing: '0.1em',
      padding: '4px 8px',
      borderRadius: 'var(--r4)',
      textTransform: 'uppercase',
      whiteSpace: 'nowrap',
      ...styles[tier || 'NONE'],
    }}>
      {label}
    </span>
  )
}

export function BarRow({ label, value, max = 100, color = 'var(--purple)', showVal = true }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9 }}>
      <div style={{ fontSize: 11, color: 'var(--text1)', flex: 1 }}>{label}</div>
      <div style={{ width: 100, height: 3, background: 'var(--bg3)', borderRadius: 2 }}>
        <div style={{ width: `${(value / max) * 100}%`, height: '100%', borderRadius: 2, background: color, transition: 'width 0.5s cubic-bezier(0.4,0,0.2,1)' }} />
      </div>
      {showVal && <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color, width: 36, textAlign: 'right' }}>{value}{max === 100 ? '%' : ''}</div>}
    </div>
  )
}

export function Spinner() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', padding: 40 }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text2)', letterSpacing: '0.15em', animation: 'blink 1.5s ease-in-out infinite' }}>
        LOADING...
      </div>
    </div>
  )
}
