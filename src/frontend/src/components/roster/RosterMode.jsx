import React, { useState } from 'react'
import { Panel, MetricCard, SectionLabel, Spinner } from '../shared/UI.jsx'
import CourtFormation from './CourtFormation.jsx'
import { useFetch } from '../../hooks/useFetch.js'
import { api } from '../../lib/api.js'

const TEAMS = [
  { abbr:'GSW', name:'Warriors'     }, { abbr:'BOS', name:'Celtics'       },
  { abbr:'DEN', name:'Nuggets'      }, { abbr:'MIA', name:'Heat'          },
  { abbr:'LAL', name:'Lakers'       }, { abbr:'MIL', name:'Bucks'         },
  { abbr:'PHX', name:'Suns'         }, { abbr:'NYK', name:'Knicks'        },
  { abbr:'DAL', name:'Mavericks'    }, { abbr:'PHI', name:'76ers'         },
  { abbr:'MIN', name:'Timberwolves' }, { abbr:'OKC', name:'Thunder'       },
  { abbr:'SAC', name:'Kings'        }, { abbr:'CLE', name:'Cavaliers'     },
  { abbr:'ATL', name:'Hawks'        }, { abbr:'TOR', name:'Raptors'       },
]

const ROSTER_DB = {
  GSW: {
    players: [
      { name:'S. Curry', pos:'PG', ovr:96, spd:88, sht:99, def:72, reb:45, initials:'SC' },
      { name:'K. Thompson', pos:'SG', ovr:85, spd:74, sht:94, def:70, reb:52, initials:'KT' },
      { name:'D. Green', pos:'PF', ovr:82, spd:65, sht:58, def:94, reb:78, initials:'DG' },
      { name:'J. Wiggins', pos:'SF', ovr:79, spd:82, sht:76, def:78, reb:60, initials:'JW' },
      { name:'K. Looney', pos:'C', ovr:72, spd:58, sht:52, def:80, reb:88, initials:'KL' },
      { name:'M. Moody', pos:'SG', ovr:68, spd:78, sht:70, def:65, reb:42, initials:'MM' },
    ],
    formation: [
      { initials:'SC', x:155, y:90,  active:true  },
      { initials:'KT', x:145, y:48,  active:false },
      { initials:'JW', x:145, y:132, active:false },
      { initials:'DG', x:90,  y:68,  active:false },
      { initials:'KL', x:55,  y:90,  active:false },
    ],
    changes: [
      { name:'S. Curry',   delta: 3, dir: 'up'   },
      { name:'K. Thompson',delta: 2, dir: 'up'   },
      { name:'D. Green',   delta: 1, dir: 'up'   },
      { name:'J. Wiggins', delta:-2, dir: 'down' },
      { name:'K. Looney',  delta: 0, dir: 'none' },
    ],
  },
  BOS: {
    players: [
      { name:'J. Tatum',    pos:'SF', ovr:95, spd:80, sht:92, def:78, reb:70, initials:'JT' },
      { name:'J. Brown',    pos:'SG', ovr:94, spd:84, sht:88, def:85, reb:62, initials:'JB' },
      { name:'K. Porzingis',pos:'C',  ovr:84, spd:66, sht:82, def:86, reb:80, initials:'KP' },
      { name:'J. Holiday',  pos:'PG', ovr:83, spd:76, sht:74, def:92, reb:58, initials:'JH' },
      { name:'A. Horford',  pos:'PF', ovr:78, spd:60, sht:72, def:84, reb:76, initials:'AH' },
      { name:'P. White',    pos:'PG', ovr:72, spd:80, sht:72, def:70, reb:38, initials:'PW' },
    ],
    formation: [
      { initials:'JH', x:155, y:90,  active:true  },
      { initials:'JB', x:145, y:48,  active:false },
      { initials:'JT', x:145, y:132, active:false },
      { initials:'AH', x:90,  y:68,  active:false },
      { initials:'KP', x:55,  y:90,  active:false },
    ],
    changes: [
      { name:'J. Tatum', delta:1, dir:'up'  },
      { name:'J. Brown', delta:2, dir:'up'  },
      { name:'K. Porzingis', delta:-1, dir:'down' },
      { name:'J. Holiday', delta:0, dir:'none' },
      { name:'A. Horford', delta:1, dir:'up' },
    ],
  },
}

function PlayerCard({ player, teamAbbr }) {
  const attrs = ['spd','sht','def','reb']
  const labels = { spd:'SPD', sht:'SHT', def:'DEF', reb:'REB' }
  return (
    <div style={{
      background: 'var(--bg1)', border: '1px solid var(--bg3)', borderRadius: 'var(--r8)',
      padding: 12, cursor: 'pointer', transition: 'all 0.15s',
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--amber)'; e.currentTarget.style.background = 'var(--bg2)' }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--bg3)';  e.currentTarget.style.background = 'var(--bg1)' }}
    >
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:8 }}>
        <div>
          <div style={{ fontFamily:'var(--display)', fontSize:14, fontWeight:700, letterSpacing:'0.03em', color:'var(--text0)' }}>{player.name}</div>
          <div style={{ fontFamily:'var(--mono)', fontSize:9, color:'var(--text2)', marginTop:1 }}>{player.pos}</div>
        </div>
        <div style={{ fontFamily:'var(--display)', fontSize:26, fontWeight:800, color:'var(--amber)', lineHeight:1 }}>{player.ovr}</div>
      </div>
      {attrs.map(a => (
        <div key={a} style={{ display:'flex', alignItems:'center', gap:6, marginBottom:5 }}>
          <span style={{ fontFamily:'var(--mono)', fontSize:8, color:'var(--text3)', width:22, letterSpacing:'0.08em', textTransform:'uppercase' }}>{labels[a]}</span>
          <div style={{ flex:1, height:2, background:'var(--bg3)', borderRadius:1 }}>
            <div style={{ width:`${player[a]}%`, height:'100%', borderRadius:1, background:'var(--amber)', transition:'width 0.5s cubic-bezier(0.4,0,0.2,1)' }} />
          </div>
          <span style={{ fontFamily:'var(--mono)', fontSize:9, color:'var(--text2)', width:22, textAlign:'right' }}>{player[a]}</span>
        </div>
      ))}
      <div style={{ marginTop:8, paddingTop:8, borderTop:'1px solid var(--bg3)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <span style={{ fontFamily:'var(--mono)', fontSize:8, color:'var(--green)' }}>↑ SYNCED TODAY</span>
        <a href={api.download(teamAbbr)} download style={{
          fontFamily:'var(--mono)', fontSize:8, color:'var(--amber)',
          background:'rgba(255,171,0,0.08)', border:'1px solid rgba(255,171,0,0.2)',
          padding:'3px 8px', borderRadius:3, cursor:'pointer', textDecoration:'none',
        }}>.ROS ↓</a>
      </div>
    </div>
  )
}

function DeltaRow({ name, delta, dir }) {
  const color = dir === 'up' ? 'var(--green)' : dir === 'down' ? 'var(--red)' : 'var(--text2)'
  const label = dir === 'up' ? `+${delta}` : dir === 'down' ? `${delta}` : '±0'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:8 }}>
      <span style={{ fontSize:10, color:'var(--text1)', width:80, overflow:'hidden', whiteSpace:'nowrap', textOverflow:'ellipsis' }}>{name}</span>
      <div style={{ flex:1, height:4, background:'var(--bg3)', borderRadius:2, overflow:'hidden', display:'flex' }}>
        <div style={{ width:`${40 + (delta > 0 ? delta * 5 : 0)}%`, background:'var(--text3)', borderRadius:'2px 0 0 2px' }} />
        <div style={{ width:`${delta > 0 ? delta * 5 : 0}%`, background:'var(--amber)', borderRadius:'0 2px 2px 0' }} />
      </div>
      <span style={{ fontFamily:'var(--mono)', fontSize:9, color, width:28, textAlign:'right' }}>{label}</span>
    </div>
  )
}

export default function RosterMode() {
  const [selectedTeam, setSelectedTeam] = useState('GSW')

  const teamData = ROSTER_DB[selectedTeam] || ROSTER_DB.GSW
  const fullName = TEAMS.find(t => t.abbr === selectedTeam)
  const displayName = fullName ? `${fullName.name}` : selectedTeam

  return (
    <div style={{ display:'grid', gridTemplateColumns:'180px 1fr 300px', height:'100%', overflow:'hidden' }}>

      {/* LEFT — team list */}
      <div style={{ background:'var(--bg1)', borderRight:'1px solid var(--bg3)', padding:12, overflowY:'auto' }}>
        <SectionLabel style={{ marginBottom:8 }}>Teams</SectionLabel>
        {TEAMS.map(t => (
          <div key={t.abbr}
            onClick={() => setSelectedTeam(t.abbr)}
            style={{
              display:'flex', alignItems:'center', gap:8, padding:'8px 10px',
              borderRadius:'var(--r8)', cursor:'pointer', transition:'all 0.1s',
              marginBottom:2,
              background: selectedTeam === t.abbr ? 'rgba(255,171,0,0.08)' : 'transparent',
              border: `1px solid ${selectedTeam === t.abbr ? 'rgba(255,171,0,0.2)' : 'transparent'}`,
            }}
            onMouseEnter={e => { if(selectedTeam !== t.abbr) e.currentTarget.style.background = 'var(--bg2)' }}
            onMouseLeave={e => { if(selectedTeam !== t.abbr) e.currentTarget.style.background = 'transparent' }}
          >
            <span style={{ fontFamily:'var(--mono)', fontSize:10, fontWeight:600, color: selectedTeam === t.abbr ? 'var(--amber)' : 'var(--text2)', width:28, letterSpacing:'0.08em' }}>{t.abbr}</span>
            <span style={{ fontSize:11, color: selectedTeam === t.abbr ? 'var(--text0)' : 'var(--text1)' }}>{t.name}</span>
          </div>
        ))}
      </div>

      {/* CENTER */}
      <div style={{ background:'var(--bg0)', padding:14, overflowY:'auto', display:'flex', flexDirection:'column', gap:12 }}>
        {/* Court */}
        <div style={{ background:'var(--bg1)', border:'1px solid var(--bg3)', borderRadius:'var(--r12)', overflow:'hidden' }}>
          <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--bg3)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <span style={{ fontFamily:'var(--display)', fontSize:18, fontWeight:800, letterSpacing:'0.05em', color:'var(--amber)' }}>
              {displayName}
            </span>
            <span style={{ fontFamily:'var(--mono)', fontSize:9, color:'var(--green)' }}>↑ SYNCED TODAY · .ROS READY</span>
          </div>
          <div style={{ padding:16 }}>
            <CourtFormation players={teamData.formation} />
          </div>
        </div>

        {/* Player cards */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(3,minmax(0,1fr))', gap:8 }}>
          {teamData.players.map((p, i) => <PlayerCard key={i} player={p} teamAbbr={selectedTeam} />)}
        </div>
      </div>

      {/* RIGHT */}
      <div style={{ background:'var(--bg1)', borderLeft:'1px solid var(--bg3)', padding:14, overflowY:'auto', display:'flex', flexDirection:'column', gap:10 }}>
        <SectionLabel>Pipeline Sync</SectionLabel>
        <MetricCard label="Last Sync" value="TODAY 06:42" color="var(--green)" sub="All 30 teams · 450 players updated" style={{ background:'var(--bg2)' }} />

        <SectionLabel style={{ marginTop:4 }}>Attribute Changes — {selectedTeam}</SectionLabel>
        <Panel>
          {teamData.changes.map((c, i) => <DeltaRow key={i} {...c} />)}
        </Panel>

        <SectionLabel>ROS File Status</SectionLabel>
        <MetricCard label={`${selectedTeam.toLowerCase()}_poc.ros`} value="VALID · CRC OK" color="var(--green)" sub="2.67 MB · 832 records · 1,664 players" style={{ background:'var(--bg2)' }} />
        <MetricCard label="Boundary Records" value="19 HANDLED" color="var(--amber)" sub="EVEN+ODD TeamID shared · verified" style={{ background:'var(--bg2)' }} />

        <a href={api.download(selectedTeam)} download style={{
          display:'block', textAlign:'center', padding:10,
          background:'rgba(255,171,0,0.1)', border:'1px solid rgba(255,171,0,0.3)',
          color:'var(--amber)', fontFamily:'var(--mono)', fontSize:10, fontWeight:600,
          letterSpacing:'0.12em', borderRadius:'var(--r8)', cursor:'pointer',
          transition:'background 0.15s', textDecoration:'none', textTransform:'uppercase',
        }}
        onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,171,0,0.18)'}
        onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,171,0,0.1)'}
        >
          ↓ DOWNLOAD {selectedTeam} .ROS
        </a>
      </div>
    </div>
  )
}
