import React, { useState } from 'react';
import { Layers, LayoutDashboard, Clock, Plus, Sparkles, Menu, X, GitCompare, CalendarClock } from 'lucide-react';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard',        Icon: LayoutDashboard },
  { id: 'new',       label: 'New Analysis',     Icon: Plus },
  { id: 'history',   label: 'History',          Icon: Clock },
  { id: 'compare',   label: 'Decision Compare', Icon: GitCompare },
  { id: 'deadlines', label: 'Deadline Center',  Icon: CalendarClock },
];

export default function Sidebar({ activeView, onNavigate, historyCount = 0, backendConnected = true }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const currentTab =
    activeView === 'result' ? 'dashboard' :
    activeView === 'history-detail' ? 'history' :
    activeView === 'compare' ? 'compare' :
    activeView === 'deadlines' ? 'deadlines' :
    activeView === 'new' ? 'new' :
    activeView;

  const handleNav = (id) => {
    setMobileOpen(false);
    onNavigate(id);
  };

  return (
    <>
      {/* Mobile top bar */}
      <div className="sidebar-mobile-bar">
        <div className="sidebar-brand-row">
          <div className="sidebar-logo"><Layers size={18} strokeWidth={2.3} /></div>
          <span className="sidebar-brand-name">DecisionFlow AI</span>
        </div>
        <button
          type="button"
          className="sidebar-mobile-toggle"
          onClick={() => setMobileOpen(v => !v)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Overlay (mobile) */}
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}

      {/* Sidebar panel */}
      <aside className={`sidebar ${mobileOpen ? 'sidebar--open' : ''}`}>
        {/* Brand */}
        <div className="sidebar-brand">
          <div className="sidebar-logo"><Layers size={20} strokeWidth={2.3} /></div>
          <div>
            <div className="sidebar-brand-name">DecisionFlow AI</div>
            <div className="sidebar-brand-sub">Decision Intelligence</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="sidebar-nav" role="navigation" aria-label="Sidebar navigation">
          <div className="sidebar-nav-label">NAVIGATION</div>
          {NAV_ITEMS.map(({ id, label, Icon }) => {
            const isActive = currentTab === id;
            const showBadge = id === 'history' && historyCount > 0;
            return (
              <button
                key={id}
                id={`sidebar-nav-${id}`}
                type="button"
                className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
                onClick={() => handleNav(id)}
              >
                <Icon size={17} strokeWidth={isActive ? 2.3 : 2} />
                <span className="sidebar-nav-label-text">{label}</span>
                {showBadge && (
                  <span className="sidebar-nav-badge">{historyCount}</span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Status */}
        <div className="sidebar-footer">
          <div className={`sidebar-status ${backendConnected ? 'online' : 'offline'}`}>
            <span className={`sidebar-status-dot ${backendConnected ? 'online' : 'offline'}`} />
            <span className="sidebar-status-text">
              {backendConnected ? (
                <><Sparkles size={11} style={{ display: 'inline', marginRight: 3 }} />Cortex AI Ready</>
              ) : 'Backend Offline'}
            </span>
          </div>
          <div className="sidebar-db-note">DECISIONFLOW_DB · PUBLIC · DOCUMENTS</div>
        </div>
      </aside>
    </>
  );
}
