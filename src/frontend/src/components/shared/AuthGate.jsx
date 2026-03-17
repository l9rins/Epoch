import React, { useState } from 'react'
import { useAuth } from '../../hooks/useAuth.js'

const TIERS = [
  { id: 'ROSTRA', label: 'Roster', desc: 'Browse + download .ROS files', price: 'Free', color: 'var(--amber)' },
  { id: 'SIGNAL', label: 'Signal', desc: 'Bettor mode + live signals', price: '$29/mo', color: 'var(--blue)' },
  { id: 'API',    label: 'Analyst', desc: 'Full platform access', price: '$79/mo', color: 'var(--green)' },
]

const MODE_TIER = { analyst: 'API', bettor: 'SIGNAL', roster: 'ROSTRA' }

export function TierBadge({ tier }) {
  const t = TIERS.find(x => x.id === tier) || TIERS[0]
  return (
    <span style={{
      fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600,
      letterSpacing: '0.12em', padding: '3px 8px',
      borderRadius: 'var(--r4)', textTransform: 'uppercase',
      background: `${t.color}18`, color: t.color,
      border: `1px solid ${t.color}33`,
    }}>{t.label}</span>
  )
}

export default function AuthGate({ mode, children }) {
  const { isLoggedIn, canAccess, tier, user, logout } = useAuth()
  const [showModal, setShowModal] = useState(false)
  const required = MODE_TIER[mode] || 'ROSTRA'

  if (isLoggedIn && canAccess(required)) {
    return children
  }

  if (!isLoggedIn) {
    return (
      <>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          height: '100%', flexDirection: 'column', gap: 20,
          background: 'var(--bg0)',
        }}>
          <div style={{ fontFamily: 'var(--display)', fontSize: 28, fontWeight: 800, color: 'var(--text0)', letterSpacing: '0.05em' }}>
            EPOCH ENGINE
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text2)', letterSpacing: '0.15em' }}>
            SIGN IN TO CONTINUE
          </div>
          <button
            onClick={() => setShowModal(true)}
            style={{
              fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
              letterSpacing: '0.12em', padding: '10px 28px',
              background: 'rgba(0,230,118,0.1)', color: 'var(--green)',
              border: '1px solid rgba(0,230,118,0.3)', borderRadius: 'var(--r8)',
              cursor: 'pointer', textTransform: 'uppercase',
            }}
          >
            LOGIN / REGISTER
          </button>
        </div>
        {showModal && <AuthModal onClose={() => setShowModal(false)} />}
      </>
    )
  }

  // Logged in but wrong tier
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100%', flexDirection: 'column', gap: 16, background: 'var(--bg0)',
    }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text2)', letterSpacing: '0.15em' }}>
        UPGRADE REQUIRED
      </div>
      <div style={{ fontFamily: 'var(--display)', fontSize: 22, fontWeight: 700, color: 'var(--text0)' }}>
        {TIERS.find(t => t.id === required)?.label} mode requires {required} tier
      </div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text2)' }}>
        Your tier: <span style={{ color: 'var(--amber)' }}>{tier}</span>
      </div>
      <a
        href="/api/stripe/checkout"
        style={{
          fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
          letterSpacing: '0.12em', padding: '10px 28px',
          background: 'rgba(41,121,255,0.1)', color: 'var(--blue)',
          border: '1px solid rgba(41,121,255,0.3)', borderRadius: 'var(--r8)',
          cursor: 'pointer', textDecoration: 'none', textTransform: 'uppercase',
        }}
      >
        UPGRADE PLAN
      </a>
    </div>
  )
}

function AuthModal({ onClose }) {
  const { login, register, loading, error } = useAuth()
  const [tab, setTab]           = useState('login')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [tier, setTier]         = useState('ROSTRA')

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      if (tab === 'login') {
        await login(email, password)
      } else {
        await register(email, password, tier)
      }
      onClose()
    } catch {}
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: 'var(--bg1)', border: '1px solid var(--bg3)',
        borderRadius: 'var(--r12)', padding: 28, width: 380,
        display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontFamily: 'var(--display)', fontSize: 20, fontWeight: 800, letterSpacing: '0.1em', color: 'var(--text0)' }}>
            {tab === 'login' ? 'SIGN IN' : 'CREATE ACCOUNT'}
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text2)', cursor: 'pointer', fontSize: 16 }}>✕</button>
        </div>

        {/* Tab switcher */}
        <div style={{ display: 'flex', gap: 4, background: 'var(--bg0)', borderRadius: 'var(--r8)', padding: 3 }}>
          {['login','register'].map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              flex: 1, fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600,
              letterSpacing: '0.1em', padding: '6px 0', border: 'none',
              borderRadius: 6, cursor: 'pointer', textTransform: 'uppercase',
              background: tab === t ? 'var(--bg3)' : 'transparent',
              color: tab === t ? 'var(--text0)' : 'var(--text2)',
            }}>{t}</button>
          ))}
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <input
            type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)} required
            style={{ width: '100%' }}
          />
          <input
            type="password" placeholder="Password" value={password}
            onChange={e => setPassword(e.target.value)} required
            style={{ width: '100%' }}
          />

          {tab === 'register' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', letterSpacing: '0.15em', textTransform: 'uppercase' }}>Select Plan</div>
              {TIERS.map(t => (
                <div
                  key={t.id}
                  onClick={() => setTier(t.id)}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 12px', borderRadius: 'var(--r8)', cursor: 'pointer',
                    border: `1px solid ${tier === t.id ? t.color + '55' : 'var(--bg3)'}`,
                    background: tier === t.id ? `${t.color}0d` : 'var(--bg2)',
                    transition: 'all 0.1s',
                  }}
                >
                  <div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: t.color, letterSpacing: '0.08em' }}>{t.label}</div>
                    <div style={{ fontSize: 10, color: 'var(--text2)', marginTop: 2 }}>{t.desc}</div>
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color: t.id === 'ROSTRA' ? 'var(--green)' : 'var(--text1)' }}>{t.price}</div>
                </div>
              ))}
            </div>
          )}

          {error && (
            <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--red)', background: 'rgba(255,61,61,0.08)', border: '1px solid rgba(255,61,61,0.2)', borderRadius: 'var(--r4)', padding: '6px 10px' }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} style={{
            fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
            letterSpacing: '0.12em', padding: '11px 0', marginTop: 4,
            background: loading ? 'var(--bg3)' : 'rgba(0,230,118,0.12)',
            color: loading ? 'var(--text2)' : 'var(--green)',
            border: `1px solid ${loading ? 'var(--bg3)' : 'rgba(0,230,118,0.3)'}`,
            borderRadius: 'var(--r8)', cursor: loading ? 'not-allowed' : 'pointer',
            textTransform: 'uppercase', transition: 'all 0.15s',
          }}>
            {loading ? 'LOADING...' : tab === 'login' ? 'SIGN IN' : 'CREATE ACCOUNT'}
          </button>
        </form>

        {tab === 'register' && (
          <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', textAlign: 'center', letterSpacing: '0.08em' }}>
            14-day free trial · No credit card required for ROSTRA
          </div>
        )}
      </div>
    </div>
  )
}
