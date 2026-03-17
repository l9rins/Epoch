import React from 'react'
import { Panel, MetricCard, SectionLabel, BarRow, Spinner } from '../shared/UI.jsx'
import ShotChart from './ShotChart.jsx'
import { useFetch } from '../../hooks/useFetch.js'
import { useSignalFeed } from '../../hooks/useSignalFeed.js'
import { api } from '../../lib/api.js'

const TIER_COLOR = { 1: 'var(--green)', 2: 'var(--amber)', 3: 'var(--blue)' }

function SignalItem({ signal }) {
  const color = TIER_COLOR[signal.tier] || 'var(--text2)'
  return (
    <div style={{
      background: 'var(--bg2)',
      border: '1px solid var(--bg3)',
      borderRadius: 'var(--r8)',
      padding: '10px 12px',
      display: 'flex',
      gap: 10,
      alignItems: 'flex-start',
      marginBottom: 6,
      animation: 'slide-in 0.2s ease-out',
    }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0, marginTop: 3, boxShadow: `0 0 6px ${color}` }} />
      <div>
        <div style={{ fontSize: 11, color: 'var(--text1)', lineHeight: 1.5 }}>{signal.message}</div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', marginTop: 3 }}>
          {signal.time_ago || 'JUST NOW'} · TIER {signal.tier}
        </div>
      </div>
    </div>
  )
}

function CalibRow({ predicted, actual, warn }) {
  const color = warn ? 'var(--amber)' : 'var(--green)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text2)', width: 26, textAlign: 'right' }}>{predicted}</span>
      <div style={{ flex: 1, height: 5, background: 'var(--bg3)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${actual * 100}%`, height: '100%', borderRadius: 3, background: `linear-gradient(90deg, ${warn ? 'var(--amber-dim)' : 'var(--green-dim)'}, ${color})`, transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)' }} />
      </div>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text1)', width: 40 }}>
        {actual.toFixed(2)}{warn ? ' ⚠' : ''}
      </span>
    </div>
  )
}

// Static fallback data while API loads
const FALLBACK_ACCURACY = {
  auc: 0.857, brier: 0.183, season_accuracy: 67.4,
  signals_30d: 148, t1_accuracy: 73.0,
  calibration: [
    { predicted: 0.1, actual: 0.09 }, { predicted: 0.2, actual: 0.21 },
    { predicted: 0.3, actual: 0.28 }, { predicted: 0.5, actual: 0.56, warn: true },
    { predicted: 0.7, actual: 0.69 }, { predicted: 0.9, actual: 0.91 },
  ],
  features: [
    { name: 'Fatigue index', value: 88 }, { name: 'Home/away split', value: 74 },
    { name: 'Pace differential', value: 61 }, { name: 'Rest days delta', value: 55 },
    { name: 'Momentum score', value: 43 }, { name: 'Referee crew bias', value: 31 },
  ],
  rapm: [
    { name: 'N. Jokić',         value: 8.2 }, { name: 'L. Dončić',        value: 7.6 },
    { name: 'J. Tatum',         value: 6.9 }, { name: 'S. Curry',         value: 6.4 },
    { name: 'G. Antetokounmpo', value: 6.1 },
  ],
}

const FALLBACK_SIGNALS = [
  { tier: 1, message: 'BOS fatigue index critical low — 3 rest days vs MIA back-to-back', time_ago: '2 MIN AGO' },
  { tier: 2, message: 'DEN altitude edge detected — LAL 0-6 ATS in Denver this season', time_ago: '8 MIN AGO' },
  { tier: 1, message: 'Referee crew #14 foul rate 12% above league avg', time_ago: '14 MIN AGO' },
  { tier: 3, message: 'GSW scoring run Q3 — momentum reversal prob 71%', time_ago: '21 MIN AGO' },
  { tier: 2, message: 'MIL pace mismatch vs PHI — 4.2pt total edge vs market', time_ago: '35 MIN AGO' },
]

export default function AnalystMode() {
  const { data: accuracy } = useFetch(api.accuracy)
  const { signals: wsSignals, connected } = useSignalFeed()

  const d = accuracy || FALLBACK_ACCURACY
  const signals = wsSignals.length > 0 ? wsSignals : FALLBACK_SIGNALS

  const col = { display: 'flex', flexDirection: 'column', gap: 10, overflow: 'hidden' }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr 280px', height: '100%', overflow: 'hidden' }}>

      {/* LEFT — metrics */}
      <div style={{ background: 'var(--bg1)', borderRight: '1px solid var(--bg3)', padding: 14, overflowY: 'auto', ...col }}>
        <SectionLabel>Model Health</SectionLabel>
        <MetricCard label="AUC Score"        value={d.auc}                      color="var(--green)"  sub="RandomForest ensemble" />
        <MetricCard label="Brier Score"      value={d.brier}                    color="var(--text0)"  sub="↓ 0.012 vs last week" />
        <MetricCard label="Signals Fired"    value={d.signals_30d}              color="var(--purple)" sub="Last 30 days" />
        <MetricCard label="Season Accuracy"  value={`${d.season_accuracy}%`}   color="var(--amber)"  sub="Home: 71.2% / Away: 63.1%" />
        <MetricCard label="T1 Accuracy"      value={`${d.t1_accuracy}%`}       color="var(--green)"  sub="n=48 this season" />
      </div>

      {/* CENTER — charts */}
      <div style={{ background: 'var(--bg0)', padding: 14, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Panel title="Shot Zone Analysis — BOS vs MIA" tag="LIVE MODEL INPUT">
          <ShotChart />
        </Panel>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Panel title="Calibration Curve" tag="PLATT SCALING">
            {d.calibration.map((row, i) => (
              <CalibRow key={i} predicted={row.predicted} actual={row.actual} warn={row.warn} />
            ))}
          </Panel>

          <Panel title="Feature Importance" tag="TOP 6">
            {d.features.map((f, i) => (
              <BarRow key={i} label={f.name} value={f.value} color="var(--purple)" />
            ))}
          </Panel>
        </div>
      </div>

      {/* RIGHT — signals + RAPM */}
      <div style={{ background: 'var(--bg1)', borderLeft: '1px solid var(--bg3)', padding: 14, overflowY: 'auto', ...col }}>
        <SectionLabel>Live Signal Feed {connected && <span style={{ color: 'var(--green)', marginLeft: 4 }}>●</span>}</SectionLabel>
        {signals.map((s, i) => <SignalItem key={i} signal={s} />)}

        <SectionLabel style={{ marginTop: 8 }}>RAPM Leaders</SectionLabel>
        <Panel>
          {d.rapm.map((p, i) => (
            <BarRow key={i} label={p.name} value={p.value} max={10} color={i < 3 ? 'var(--green)' : 'var(--blue)'} showVal={true} />
          ))}
        </Panel>
      </div>
    </div>
  )
}
