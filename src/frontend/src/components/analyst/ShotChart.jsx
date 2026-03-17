import React from 'react'

const ZONE_COLORS = {
  hot:     { fill: '#00e676', text: '#4dff9e', opacity: 0.22 },
  neutral: { fill: '#ffab00', text: '#ffcc55', opacity: 0.22 },
  cold:    { fill: '#e6533c', text: '#ff8c78', opacity: 0.28 },
}

// zones: [{ x, y, w, h, rx, ry, pct, type, shape }]
function Zone({ zone }) {
  const { fill, text, opacity } = ZONE_COLORS[zone.type] || ZONE_COLORS.neutral
  const cx = zone.cx || (zone.x + zone.w / 2)
  const cy = zone.cy || (zone.y + zone.h / 2)

  return (
    <g>
      {zone.shape === 'ellipse'
        ? <ellipse cx={zone.cx} cy={zone.cy} rx={zone.rx} ry={zone.ry} fill={fill} opacity={opacity} />
        : <rect x={zone.x} y={zone.y} width={zone.w} height={zone.h} rx={3} fill={fill} opacity={opacity} />
      }
      <text x={cx} y={cy + 4} textAnchor="middle" fill={text} fontSize={9} fontFamily="IBM Plex Mono" fontWeight={600}>
        {zone.pct}%
      </text>
    </g>
  )
}

const DEFAULT_ZONES = [
  { x: 22, y: 22, w: 60, h: 38, pct: 44, type: 'cold' },
  { shape: 'ellipse', cx: 80, cy: 70, rx: 28, ry: 18, pct: 31, type: 'cold' },
  { shape: 'ellipse', cx: 130, cy: 110, rx: 22, ry: 16, pct: 46, type: 'neutral' },
  { x: 22, y: 105, w: 58, h: 70, pct: 65, type: 'hot' },
  { x: 22, y: 222, w: 60, h: 36, pct: 38, type: 'neutral' },
  { shape: 'ellipse', cx: 140, cy: 140, rx: 18, ry: 14, pct: 52, type: 'neutral' },
]

export default function ShotChart({ zones = DEFAULT_ZONES, homeTeam = 'BOS', awayTeam = 'MIA' }) {
  return (
    <div style={{ background: 'var(--bg2)', borderRadius: 'var(--r8)', overflow: 'hidden' }}>
      <svg viewBox="0 0 400 280" width="100%" style={{ display: 'block' }} xmlns="http://www.w3.org/2000/svg">
        <rect width="400" height="280" fill="#0f1a14" rx="6" />

        {/* Court lines */}
        <rect x="20" y="20" width="360" height="240" rx="4" fill="none" stroke="#1e3028" strokeWidth="1.5" />
        <line x1="200" y1="20" x2="200" y2="260" stroke="#1e3028" strokeWidth="1" />

        {/* Left paint */}
        <rect x="20" y="90" width="80" height="100" fill="none" stroke="#1e3028" strokeWidth="1.2" />
        {/* Right paint */}
        <rect x="300" y="90" width="80" height="100" fill="none" stroke="#1e3028" strokeWidth="1.2" />

        {/* Free throw circles */}
        <circle cx="100" cy="140" r="30" fill="none" stroke="#1e3028" strokeWidth="1" strokeDasharray="4 3" />
        <circle cx="300" cy="140" r="30" fill="none" stroke="#1e3028" strokeWidth="1" strokeDasharray="4 3" />

        {/* Baskets */}
        <circle cx="35" cy="140" r="6" fill="none" stroke="#2a4a38" strokeWidth="1.5" />
        <line x1="20" y1="140" x2="41" y2="140" stroke="#2a4a38" strokeWidth="1.5" />
        <circle cx="365" cy="140" r="6" fill="none" stroke="#2a4a38" strokeWidth="1.5" />
        <line x1="359" y1="140" x2="380" y2="140" stroke="#2a4a38" strokeWidth="1.5" />

        {/* 3pt arcs */}
        <path d="M20 100 Q20 60 60 60 Q140 60 160 140 Q140 220 60 220 Q20 220 20 180" fill="none" stroke="#1e3028" strokeWidth="1.2" />
        <path d="M380 100 Q380 60 340 60 Q260 60 240 140 Q260 220 340 220 Q380 220 380 180" fill="none" stroke="#1e3028" strokeWidth="1.2" />

        {/* Center circle */}
        <circle cx="200" cy="140" r="30" fill="none" stroke="#1e3028" strokeWidth="1" strokeDasharray="4 3" />

        {/* Heat zones */}
        {zones.map((z, i) => <Zone key={i} zone={z} />)}

        {/* Team labels */}
        <text x="100" y="14" textAnchor="middle" fill="#2a4a38" fontSize={9} fontFamily="IBM Plex Mono">{homeTeam}</text>
        <text x="300" y="14" textAnchor="middle" fill="#2a4a38" fontSize={9} fontFamily="IBM Plex Mono">{awayTeam}</text>

        {/* Legend */}
        <rect x="138" y="256" width="8" height="5" rx="1" fill="#e6533c" opacity={0.6} />
        <text x="149" y="263" fill="#556070" fontSize={8} fontFamily="IBM Plex Mono">Cold</text>
        <rect x="178" y="256" width="8" height="5" rx="1" fill="#ffab00" opacity={0.6} />
        <text x="189" y="263" fill="#556070" fontSize={8} fontFamily="IBM Plex Mono">Neutral</text>
        <rect x="228" y="256" width="8" height="5" rx="1" fill="#00e676" opacity={0.6} />
        <text x="239" y="263" fill="#556070" fontSize={8} fontFamily="IBM Plex Mono">Hot</text>
      </svg>
    </div>
  )
}
