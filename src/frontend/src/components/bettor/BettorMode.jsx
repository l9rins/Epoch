import React, { useState } from 'react'
import { Panel, MetricCard, SectionLabel, Badge, Spinner } from '../shared/UI.jsx'
import { useFetch } from '../../hooks/useFetch.js'
import { api } from '../../lib/api.js'

const FALLBACK_GAMES = [
  { home: 'Boston', away: 'Miami', home_rec: '47-18', away_rec: '29-36', win_prob: 71, edge: 'T1', kelly: 4.2, edge_label: 'T1 EDGE' },
  { home: 'Denver', away: 'LA Lakers', home_rec: '38-27', away_rec: '35-30', win_prob: 58, edge: 'T2', kelly: 2.1, edge_label: 'T2 VALUE' },
  { home: 'Milwaukee', away: 'Philadelphia', home_rec: '41-24', away_rec: '22-43', win_prob: 63, edge: 'T2', kelly: 1.8, edge_label: 'TOTAL' },
  { home: 'Golden State', away: 'Phoenix', home_rec: '33-32', away_rec: '27-38', win_prob: 54, edge: 'NONE', kelly: null, edge_label: 'NO EDGE' },
  { home: 'New York', away: 'Chicago', home_rec: '39-26', away_rec: '25-40', win_prob: 61, edge: 'NONE', kelly: null, edge_label: 'SKIP' },
]

const FALLBACK_ODDS = [
  { team: 'Boston Celtics', books: [{ name: 'DRAFTKINGS', line: -165, best: true }, { name: 'FANDUEL', line: -172 }, { name: 'BETMGM', line: -168 }], win_pct: 71 },
  { team: 'Denver Nuggets', books: [{ name: 'DRAFTKINGS', line: -140 }, { name: 'FANDUEL', line: -132, best: true }, { name: 'BETMGM', line: -138 }], win_pct: 58 },
]

const FALLBACK_SIGNALS = [
  { tier: 1, message: 'BOS fatigue edge — strong lean', detail: '4.2% KELLY' },
  { tier: 2, message: 'DEN altitude advantage', detail: '2.1% KELLY' },
  { tier: 2, message: 'MIL total edge vs PHI', detail: '1.8% KELLY' },
]

function GameRow({ game }) {
  const edgeColor = game.edge === 'T1' ? 'var(--green)' : game.edge === 'T2' ? 'var(--blue)' : 'var(--bg3)'
  const probColor = game.edge !== 'NONE' ? (game.edge === 'T1' ? 'var(--green)' : 'var(--blue)') : 'var(--text1)'

  return (
    <div style={{
      background: 'var(--bg1)',
      border: '1px solid var(--bg3)',
      borderRadius: 'var(--r8)',
      padding: '14px 16px',
      marginBottom: 8,
      display: 'grid',
      gridTemplateColumns: '1fr 60px 1fr 90px 72px 60px',
      alignItems: 'center',
      gap: 10,
      cursor: 'pointer',
      transition: 'all 0.15s',
      position: 'relative',
      overflow: 'hidden',
    }}
    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg2)'}
    onMouseLeave={e => e.currentTarget.style.background = 'var(--bg1)'}
    >
      {/* Edge accent */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: edgeColor }} />

      <div style={{ paddingLeft: 6 }}>
        <div style={{ fontFamily: 'var(--display)', fontSize: 15, fontWeight: 700, letterSpacing: '0.03em', color: 'var(--text0)' }}>{game.home}</div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', marginTop: 2 }}>{game.home_rec} · HOME</div>
      </div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text3)', textAlign: 'center' }}>vs</div>
      <div>
        <div style={{ fontFamily: 'var(--display)', fontSize: 15, fontWeight: 700, color: 'var(--text0)' }}>{game.away}</div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', marginTop: 2 }}>{game.away_rec} · AWAY</div>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontFamily: 'var(--display)', fontSize: 22, fontWeight: 800, color: probColor }}>{game.win_prob}%</div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--text2)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Win Prob</div>
      </div>
      <Badge tier={game.edge} label={game.edge_label} />
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontFamily: 'var(--display)', fontSize: 18, fontWeight: 700, color: game.kelly ? 'var(--green)' : 'var(--text3)' }}>
          {game.kelly ? `${game.kelly}%` : '—'}
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--text2)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Kelly</div>
      </div>
    </div>
  )
}

function OddsCard({ data }) {
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--bg3)', borderRadius: 'var(--r8)', padding: 12, marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontFamily: 'var(--display)', fontSize: 14, fontWeight: 700, color: 'var(--text0)' }}>{data.team}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--red)', letterSpacing: '0.1em', background: 'rgba(255,61,61,0.1)', border: '1px solid rgba(255,61,61,0.2)', padding: '2px 6px', borderRadius: 3 }}>LIVE</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
        {data.books.map((b, i) => (
          <div key={i} style={{ background: 'var(--bg3)', borderRadius: 'var(--r4)', padding: 8, textAlign: 'center', cursor: 'pointer', border: '1px solid transparent', transition: 'all 0.1s' }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--blue-dim)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'transparent'}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--text2)', marginBottom: 3, letterSpacing: '0.08em' }}>{b.name}</div>
            <div style={{ fontFamily: 'var(--display)', fontSize: 16, fontWeight: 700, color: b.best ? 'var(--green)' : 'var(--text0)' }}>{b.line}</div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 10 }}>
        <div style={{ height: 6, background: 'var(--bg3)', borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
          <div style={{ width: `${data.win_pct}%`, background: 'var(--green)', borderRadius: '3px 0 0 3px' }} />
          <div style={{ flex: 1, background: 'var(--red-dim)', borderRadius: '0 3px 3px 0' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)' }}>W {data.win_pct}%</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)' }}>L {100 - data.win_pct}%</span>
        </div>
      </div>
    </div>
  )
}

function KellyCalc() {
  const [prob, setProb] = useState(71)
  const [odds, setOdds] = useState(165)

  const dec = 1 + 100 / odds
  const kelly = Math.max(0, ((prob / 100) * (dec - 1) - (1 - prob / 100)) / (dec - 1) * 100).toFixed(1)

  return (
    <Panel title="Kelly Calculator">
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6 }}>
          Win Probability: {prob}%
        </div>
        <input type="range" min={50} max={90} value={prob} onChange={e => setProb(+e.target.value)} style={{ width: '100%' }} />
      </div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6 }}>
          American Odds: -{odds}
        </div>
        <input type="range" min={100} max={300} value={odds} onChange={e => setOdds(+e.target.value)} style={{ width: '100%' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 10, borderTop: '1px solid var(--bg3)' }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Kelly Bet Size</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 22, fontWeight: 600, color: 'var(--green)' }}>{kelly}%</span>
      </div>
    </Panel>
  )
}

export default function BettorMode() {
  const { data: todayData } = useFetch(api.predictionsToday, [], 30000)
  const { data: oddsData } = useFetch(api.odds, [], 60000)

  const games = todayData?.games || FALLBACK_GAMES
  const odds  = oddsData?.edges  || FALLBACK_ODDS

  const today = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).toUpperCase()

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr 300px', height: '100%', overflow: 'hidden' }}>

      {/* LEFT */}
      <div style={{ background: 'var(--bg1)', borderRight: '1px solid var(--bg3)', padding: 14, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Bankroll */}
        <div style={{ background: 'linear-gradient(135deg, var(--bg3), var(--bg2))', border: '1px solid var(--bg4)', borderRadius: 'var(--r12)', padding: 16 }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 6 }}>Bankroll</div>
          <div style={{ fontFamily: 'var(--display)', fontSize: 36, fontWeight: 800, color: 'var(--text0)', lineHeight: 1 }}>$2,460</div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--green)', marginTop: 4 }}>↑ +13% this month</div>
        </div>

        {/* W/L/G */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
          {[['290','Games','var(--text0)'],['160','Wins','var(--green)'],['130','Loss','var(--red)']].map(([v,l,c]) => (
            <div key={l} style={{ background: 'var(--bg2)', border: '1px solid var(--bg3)', borderRadius: 'var(--r8)', padding: 10, textAlign: 'center' }}>
              <div style={{ fontFamily: 'var(--display)', fontSize: 20, fontWeight: 700, color: c }}>{v}</div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--text2)', letterSpacing: '0.1em', textTransform: 'uppercase', marginTop: 2 }}>{l}</div>
            </div>
          ))}
        </div>

        <SectionLabel>Active Signals</SectionLabel>
        {FALLBACK_SIGNALS.map((s, i) => (
          <div key={i} style={{ background: 'var(--bg2)', border: '1px solid var(--bg3)', borderRadius: 'var(--r8)', padding: '10px 12px', display: 'flex', gap: 8, marginBottom: 4 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.tier === 1 ? 'var(--green)' : 'var(--amber)', flexShrink: 0, marginTop: 3 }} />
            <div>
              <div style={{ fontSize: 11, color: 'var(--text1)' }}>{s.message}</div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', marginTop: 2 }}>TIER {s.tier} · {s.detail}</div>
            </div>
          </div>
        ))}
      </div>

      {/* CENTER */}
      <div style={{ background: 'var(--bg0)', padding: 14, overflowY: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ fontFamily: 'var(--display)', fontSize: 18, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text0)' }}>TODAY'S GAMES</div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', background: 'var(--bg2)', border: '1px solid var(--bg3)', padding: '4px 10px', borderRadius: 20 }}>{today}</div>
        </div>
        {games.map((g, i) => <GameRow key={i} game={g} />)}
      </div>

      {/* RIGHT */}
      <div style={{ background: 'var(--bg1)', borderLeft: '1px solid var(--bg3)', padding: 14, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <SectionLabel>Best Odds</SectionLabel>
        {odds.map((o, i) => <OddsCard key={i} data={o} />)}
        <KellyCalc />
      </div>
    </div>
  )
}
