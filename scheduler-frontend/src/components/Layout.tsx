import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import AiChatWidget from './AiChatWidget'
import './Layout.css'

function DashboardIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="8" height="8" rx="1.5" /><rect x="13" y="3" width="8" height="5" rx="1.5" />
      <rect x="13" y="12" width="8" height="9" rx="1.5" /><rect x="3" y="15" width="8" height="6" rx="1.5" />
    </svg>
  )
}
function EmployeesIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" /><circle cx="10" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}
function ScheduleIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  )
}
function UploadIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M17 8l-5-5-5 5" /><path d="M12 3v12" />
    </svg>
  )
}
function ConstraintsIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3" />
      <path d="M1 14h6M9 8h6M17 16h6" />
    </svg>
  )
}
function SparkleIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2 L14.2 9.8 22 12 14.2 14.2 12 22 9.8 14.2 2 12 9.8 9.8 Z" />
    </svg>
  )
}

const NAV_ITEMS: { to: string; label: string; end?: boolean; icon: ReactNode }[] = [
  { to: '/', label: 'Dashboard', end: true, icon: <DashboardIcon /> },
  { to: '/employees', label: 'Employees', icon: <EmployeesIcon /> },
  { to: '/schedule', label: 'Schedule', icon: <ScheduleIcon /> },
  { to: '/csv-upload', label: 'CSV Upload', icon: <UploadIcon /> },
  { to: '/constraints', label: 'Constraints', icon: <ConstraintsIcon /> },
  { to: '/ai-assistant', label: 'AI Assistant', icon: <SparkleIcon /> },
]

function Layout() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-title">
          <span className="app-nav-mark" />
          Scheduler
        </div>
        <ul>
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) => (isActive ? 'active' : '')}
              >
                <span className="app-nav-icon">{item.icon}</span>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="app-content">
        <Outlet />
      </main>
      <AiChatWidget />
    </div>
  )
}

export default Layout
