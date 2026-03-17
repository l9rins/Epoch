import React from 'react'

// positions: [{ initials, x, y, active }]
export default function CourtFormation({ players = [], teamName = '', formation = 'MOTION OFFENSE' }) {
  return (
    <svg viewBox="0 0 460 180" width="100%" style={{ display: 'block' }} xmlns="http://www.w3.org/2000/svg">
      <rect width="460" height="180" fill="#0d1a10" rx="6" />
      <rect x="10" y="10" width="440" height="160" rx="4" fill="none" stroke="#1e3028" strokeWidth="1.5" />

      {/* Paint */}
      <rect x="10" y="55" width="100" height="70" fill="rgba(255,171,0,0.04)" stroke="#1e3028" strokeWidth="1.2" />

      {/* Free throw circle */}
      <circle cx="110" cy="90" r="36" fill="none" stroke="#1e3028" strokeWidth="1" strokeDasharray="5 4" />

      {/* Basket */}
      <circle cx="22" cy="90" r="7" fill="none" stroke="#2a4a38" strokeWidth="2" />
      <line x1="10" y1="90" x2="29" y2="90" stroke="#2a4a38" strokeWidth="2" />

      {/* 3pt arc */}
      <path d="M10 30 Q10 10 40 10 Q160 10 180 90 Q160 170 40 170 Q10 170 10 150" fill="none" stroke="#1e3028" strokeWidth="1.2" />

      {/* Half court */}
      <line x1="230" y1="10" x2="230" y2="170" stroke="#1e3028" strokeWidth="1" strokeDasharray="4 3" />
      <circle cx="230" cy="90" r="36" fill="none" stroke="#1e3028" strokeWidth="1" strokeDasharray="4 3" />

      {/* Player dots */}
      {players.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={11} fill={`rgba(255,171,0,${p.active ? 0.85 : 0.6})`} stroke="#ffcc55" strokeWidth={p.active ? 2 : 1.5} />
          <text x={p.x} y={p.y + 4} textAnchor="middle" fill="#0d1a10" fontFamily="IBM Plex Mono" fontSize={7} fontWeight={700}>{p.initials}</text>
        </g>
      ))}

      {/* Formation label */}
      <text x="340" y="86" textAnchor="middle" fill="#1e3028" fontFamily="IBM Plex Mono" fontSize={9}>{formation.split(' ')[0]}</text>
      <text x="340" y="100" textAnchor="middle" fill="#1e3028" fontFamily="IBM Plex Mono" fontSize={9}>{formation.split(' ').slice(1).join(' ')}</text>
    </svg>
  )
}
