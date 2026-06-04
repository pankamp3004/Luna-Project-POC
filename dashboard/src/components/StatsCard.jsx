import React from 'react'

/**
 * StatsCard component — displays a single metric with icon, title, and value.
 */
export default function StatsCard({ icon: Icon, title, value, color = '#6366f1' }) {
  return (
    <div
      className="rounded-lg px-4 py-5 flex items-center gap-4 transition-shadow hover:shadow-lg"
      style={{
        backgroundColor: '#1e2130',
        border: '1px solid #2a2d3e',
      }}
    >
      {/* Icon */}
      <div
        className="flex items-center justify-center rounded-lg flex-shrink-0"
        style={{
          width: '48px',
          height: '48px',
          backgroundColor: color + '20',
          color: color,
        }}
      >
        <Icon size={24} strokeWidth={2} />
      </div>

      {/* Text */}
      <div className="flex-1 min-w-0">
        <div
          className="text-sm font-medium mb-1"
          style={{ color: '#64748b' }}
        >
          {title}
        </div>
        <div
          className="text-2xl font-bold"
          style={{ color: '#e2e8f0' }}
        >
          {value}
        </div>
      </div>
    </div>
  )
}
