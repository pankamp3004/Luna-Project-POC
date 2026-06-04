import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  Moon,
  LayoutDashboard,
  Inbox,
  Mail,
  FileEdit,
  Clock,
  AlertTriangle,
  BarChart2,
  ChevronLeft,
  ChevronRight,
  User,
  Settings,
  Send,
} from 'lucide-react'
import { useEmails } from '../hooks/useEmails.js'

const NAV_ITEMS = [
  { label: 'Dashboard',    icon: LayoutDashboard, to: '/dashboard',    badgeKey: null },
  { label: 'Inbox',        icon: Inbox,           to: '/inbox',        badgeKey: 'total_emails' },
  { label: 'All Emails',   icon: Mail,            to: '/all-emails',   badgeKey: null },
  { label: 'Drafts',       icon: FileEdit,        to: '/drafts',       badgeKey: 'drafts' },
  { label: 'Sent',         icon: Send,            to: '/sent',         badgeKey: 'auto_sent' },
  { label: 'On Hold',      icon: Clock,           to: '/holds',        badgeKey: 'on_hold' },
  { label: 'Escalations',  icon: AlertTriangle,   to: '/escalations',  badgeKey: 'escalations' },
  { label: 'Analytics',    icon: BarChart2,       to: '/analytics',    badgeKey: null },
]

function NavItem({ item, collapsed, stats }) {
  const location = useLocation()
  const isActive = location.pathname === item.to

  const badgeCount = item.badgeKey && stats ? stats[item.badgeKey] : null
  const showBadge = badgeCount != null && badgeCount > 0

  return (
    <NavLink
      to={item.to}
      className={`
        flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
        transition-all duration-150 cursor-pointer select-none
        ${collapsed ? 'justify-center' : ''}
      `}
      style={{
        backgroundColor: isActive ? '#6366f1' : undefined,
        color: isActive ? '#ffffff' : '#94a3b8',
        textDecoration: 'none',
      }}
      title={collapsed ? item.label : undefined}
    >
      <item.icon
        size={18}
        strokeWidth={isActive ? 2.5 : 2}
        style={{ flexShrink: 0, color: isActive ? '#ffffff' : '#94a3b8' }}
      />
      {!collapsed && (
        <span className="flex-1 truncate" style={{ color: isActive ? '#ffffff' : '#94a3b8' }}>
          {item.label}
        </span>
      )}
      {!collapsed && showBadge && (
        <span
          className="text-xs font-semibold px-1.5 py-0.5 rounded-full"
          style={{
            backgroundColor: isActive ? 'rgba(255,255,255,0.25)' : '#6366f1',
            color: '#fff',
            minWidth: '20px',
            textAlign: 'center',
          }}
        >
          {badgeCount}
        </span>
      )}
    </NavLink>
  )
}

export default function Sidebar({ collapsed, onToggle }) {
  const { stats } = useEmails({ page: 1, limit: 1 })

  return (
    <aside
      className="flex flex-col h-screen transition-all duration-200 flex-shrink-0"
      style={{
        width: collapsed ? '64px' : '240px',
        backgroundColor: '#1a1d27',
        borderRight: '1px solid #2a2d3e',
      }}
    >
      {/* Brand */}
      <div
        className="flex items-center gap-3 px-4 py-5"
        style={{ borderBottom: '1px solid #2a2d3e', minHeight: '72px' }}
      >
        <div
          className="flex items-center justify-center rounded-lg flex-shrink-0"
          style={{ width: '36px', height: '36px', backgroundColor: '#6366f1' }}
        >
          <Moon size={20} color="#ffffff" strokeWidth={2} />
        </div>
        {!collapsed && (
          <div className="flex flex-col min-w-0">
            <span className="font-bold text-base leading-tight" style={{ color: '#e2e8f0' }}>
              Luna
            </span>
            <span className="text-xs leading-tight truncate" style={{ color: '#64748b' }}>
              Leasing Email Agent
            </span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
        {NAV_ITEMS.map(item => (
          <NavItem key={item.label} item={item} collapsed={collapsed} stats={stats} />
        ))}
      </nav>

      {/* Bottom — user info + collapse toggle */}
      <div style={{ borderTop: '1px solid #2a2d3e' }}>
        <div className="flex items-center gap-3 px-3 py-3">
          <div
            className="flex items-center justify-center rounded-full flex-shrink-0"
            style={{ width: '32px', height: '32px', backgroundColor: '#2a2d3e', color: '#64748b' }}
          >
            <User size={16} />
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate" style={{ color: '#e2e8f0' }}>Admin</div>
              <div className="text-xs truncate" style={{ color: '#64748b' }}>Tri Star Realty</div>
            </div>
          )}
          {!collapsed && (
            <Settings size={16} style={{ color: '#64748b', flexShrink: 0, cursor: 'pointer' }} />
          )}
        </div>

        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center py-2.5 transition-colors"
          style={{
            color: '#64748b',
            borderTop: '1px solid #2a2d3e',
            backgroundColor: 'transparent',
            cursor: 'pointer',
            border: 'none',
            borderTopWidth: '1px',
            borderTopStyle: 'solid',
            borderTopColor: '#2a2d3e',
          }}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  )
}
