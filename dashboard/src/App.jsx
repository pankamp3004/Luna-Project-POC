import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Sidebar from './components/Sidebar.jsx'
import Dashboard from './pages/Dashboard.jsx'

// Wrapper that forces Dashboard to remount when route changes
function RoutedDashboard(props) {
  const location = useLocation()
  return <Dashboard key={location.pathname} {...props} />
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden" style={{ backgroundColor: '#0f1117' }}>
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(c => !c)}
        />
        <main className="flex-1 overflow-y-auto" style={{ backgroundColor: '#0f1117' }}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard"   element={<RoutedDashboard filter="all"       title="Dashboard" />} />
            <Route path="/inbox"       element={<RoutedDashboard filter="all"       title="Inbox" />} />
            <Route path="/all-emails"  element={<RoutedDashboard filter="all"       title="All Emails" />} />
            <Route path="/sent"        element={<RoutedDashboard filter="sent"      title="Sent" />} />
            <Route path="/drafts"      element={<RoutedDashboard filter="draft"     title="Drafts" />} />
            <Route path="/holds"       element={<RoutedDashboard filter="hold"      title="On Hold" />} />
            <Route path="/escalations" element={<RoutedDashboard filter="escalated" title="Escalations" />} />
            <Route path="/analytics"   element={<RoutedDashboard filter="all"       title="Analytics" />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

