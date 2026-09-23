import React from 'react';
import { Layers, Sparkles } from 'lucide-react';

export default function Header({ backendConnected = true }) {
  return (
    <header className="app-header">
      <div className="header-inner">
        {/* Brand */}
        <div className="brand-wrapper">
          <div className="brand-icon">
            <Layers size={20} strokeWidth={2.2} />
          </div>
          <div>
            <div className="brand-title">
              DecisionFlow AI
              <span className="brand-badge">Cortex</span>
            </div>
            <div className="brand-tagline">Turn scattered information into clear actions.</div>
          </div>
        </div>

        {/* Status only */}
        <div
          className={`status-badge ${backendConnected ? '' : 'offline'}`}
          title={backendConnected ? 'Snowflake Cortex AI connected' : 'Backend unavailable'}
        >
          <span className={`status-dot ${backendConnected ? '' : 'offline'}`} />
          {backendConnected ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={12} /> Cortex AI Ready
            </span>
          ) : (
            <span>Backend Offline</span>
          )}
        </div>
      </div>
    </header>
  );
}
