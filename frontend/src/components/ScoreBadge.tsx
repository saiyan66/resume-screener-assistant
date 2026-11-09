import React from 'react'

interface ScoreBadgeProps {
  score: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export const ScoreBadge: React.FC<ScoreBadgeProps> = ({
  score,
  size = 'md',
  showLabel = true,
}) => {
  let badgeClass = 'badge-low'
  let label = 'Low Match'

  if (score >= 90) {
    badgeClass = 'badge-high'
    label = 'Exceptional'
  } else if (score >= 70) {
    badgeClass = 'badge-mid'
    label = 'Strong Match'
  } else if (score >= 50) {
    badgeClass = 'badge-mod'
    label = 'Moderate'
  }

  const fontSize = size === 'sm' ? '11px' : size === 'lg' ? '14px' : '12px'
  const padding = size === 'sm' ? '2px 8px' : size === 'lg' ? '6px 14px' : '3px 10px'

  return (
    <span
      className={`badge ${badgeClass}`}
      style={{ fontSize, padding }}
      title={`Score: ${score}/100`}
    >
      <span style={{ fontWeight: 700 }}>{score}%</span>
      {showLabel && <span style={{ opacity: 0.85 }}>• {label}</span>}
    </span>
  )
}

