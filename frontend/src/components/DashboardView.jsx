import React from 'react';
import {
  Sparkles,
  Plus,
  Clock,
  Calendar,
  CheckSquare,
  FileCheck,
  FileSearch,
  ArrowRight,
  ShieldCheck,
  Tag,
  AlertCircle,
  CheckCircle,
  Inbox
} from 'lucide-react';

export default function DashboardView({
  onNewAnalysis,
  historyItems = [],
  onViewHistoryItem,
  onViewAllHistory,
  isLoadingHistory = false,
}) {
  // Recent 3 items
  const recentItems = (historyItems || []).slice(0, 3);

  const getPriorityBadge = (priority) => {
    const p = (priority || 'medium').toLowerCase();
    if (p === 'high') {
      return (
        <span className="priority-badge priority-high">
          <AlertCircle size={12} /> High
        </span>
      );
    }
    if (p === 'low') {
      return (
        <span className="priority-badge priority-low">
          <CheckCircle size={12} /> Low
        </span>
      );
    }
    return (
      <span className="priority-badge priority-medium">
        <Clock size={12} /> Medium
      </span>
    );
  };

  return (
    <div className="dashboard-container">
      {/* ── HERO SECTION ────────────────────────────────────────── */}
      <section className="dashboard-hero">
        <div className="dashboard-hero-content">
          <div className="hero-pill">
            <Sparkles size={14} className="hero-pill-icon" />
            <span>Snowflake Cortex AI • openai-gpt-5</span>
          </div>

          <h1 className="hero-title">
            Turn Scattered Information into{' '}
            <span className="gradient-text">Clear Actions</span>
          </h1>

          <p className="hero-description">
            Upload documents, notices, or text. Let AI analyze, extract what matters,
            and give you a clear, prioritized action plan.
          </p>

          <div className="hero-cta-group">
            <button
              id="hero-btn-new-analysis"
              type="button"
              className="btn-primary"
              onClick={onNewAnalysis}
            >
              <Plus size={18} />
              <span>New Analysis</span>
            </button>

            <button
              id="hero-btn-view-history"
              type="button"
              className="btn-secondary"
              onClick={onViewAllHistory}
            >
              <Clock size={16} />
              <span>View History ({historyItems.length})</span>
            </button>
          </div>
        </div>

        {/* ── FLOATING PREVIEW CARDS (CSS Subtle Saas Mockup) ─── */}
        <div className="hero-floating-mockups" aria-hidden="true">
          <div className="mock-card mock-card-top">
            <div className="mock-card-header">
              <span className="mock-dot red"></span>
              <span className="mock-dot yellow"></span>
              <span className="mock-dot green"></span>
              <span className="mock-title">Active Directive</span>
            </div>
            <div className="mock-body">
              <div className="mock-badge-row">
                <span className="priority-badge priority-high" style={{ fontSize: '0.7rem', padding: '2px 8px' }}>
                  <AlertCircle size={11} /> High Priority
                </span>
                <span className="mock-deadline">Due in 4 days</span>
              </div>
              <div className="mock-line full"></div>
              <div className="mock-line partial"></div>
            </div>
          </div>

          <div className="mock-card mock-card-bottom">
            <div className="mock-action-header">
              <CheckSquare size={14} color="var(--primary-600)" />
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Itemized Action Plan
              </span>
            </div>
            <div className="mock-checklist-item">
              <div className="mock-chk-box checked"></div>
              <span>Upload verified CGPA transcript</span>
            </div>
            <div className="mock-checklist-item">
              <div className="mock-chk-box"></div>
              <span>Verify revenue income certificate</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── 4 FEATURE PILLARS ──────────────────────────────────── */}
      <section className="dashboard-features-section">
        <div className="section-label">CORE CAPABILITIES</div>
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon-wrapper">
              <FileSearch size={22} />
            </div>
            <h3 className="feature-title">Intelligent Extraction</h3>
            <p className="feature-desc">
              Snowflake Cortex AI parses official circulars, notices, and policies into clear, structured summaries.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper">
              <Calendar size={22} />
            </div>
            <h3 className="feature-title">Deterministic Urgency</h3>
            <p className="feature-desc">
              Priority is computed strictly from actual days remaining—never left to subjective or arbitrary guesses.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper">
              <CheckSquare size={22} />
            </div>
            <h3 className="feature-title">Action Checklists</h3>
            <p className="feature-desc">
              Instant step-by-step interactive task lists let you check off items as you complete mandatory directives.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper">
              <FileCheck size={22} />
            </div>
            <h3 className="feature-title">Required Documents</h3>
            <p className="feature-desc">
              Never miss a crucial submission requirement. All certificates, proofs, and forms are isolated clearly.
            </p>
          </div>
        </div>
      </section>

      {/* ── RECENT DOCUMENTS SECTION ───────────────────────────── */}
      <section className="dashboard-recent-section">
        <div className="recent-section-header">
          <div>
            <h2 className="recent-section-title">Active Documents</h2>
            <p className="recent-section-sub">
              Valid documents with upcoming deadlines stored in Snowflake.
            </p>
          </div>
          {historyItems.length > 0 && (
            <button
              type="button"
              className="view-all-link-btn"
              onClick={onViewAllHistory}
            >
              <span>View all ({historyItems.length})</span>
              <ArrowRight size={15} />
            </button>
          )}
        </div>

        {isLoadingHistory ? (
          <div className="card loading-card-simple">
            <div className="loading-spinner-ring" style={{ width: 28, height: 28, borderWidth: 3 }}></div>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Loading documents…</span>
          </div>
        ) : recentItems.length === 0 ? (
          <div className="card empty-recent-card">
            <div className="empty-recent-icon">
              <Inbox size={32} strokeWidth={1.5} />
            </div>
            <h4 style={{ fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.25rem' }}>
              No active documents in history
            </h4>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: 440, margin: '0 auto 1.25rem' }}>
              Get started by uploading a circular, notification, or memo. Analyzed documents will automatically appear here until their deadlines pass.
            </p>
            <button
              type="button"
              className="btn-primary"
              style={{ width: 'auto', padding: '0.625rem 1.25rem' }}
              onClick={onNewAnalysis}
            >
              <Plus size={16} /> Analyze First Document
            </button>
          </div>
        ) : (
          <div className="recent-grid">
            {recentItems.map((item) => (
              <div
                key={item.id}
                className="recent-card"
                onClick={() => onViewHistoryItem(item.id)}
              >
                <div className="recent-card-top">
                  <span className="category-tag">
                    <Tag size={11} /> {item.category || 'General'}
                  </span>
                  {getPriorityBadge(item.priority)}
                </div>

                <h3 className="recent-card-title">{item.title}</h3>

                <p className="recent-card-summary">
                  {item.summary ? item.summary.slice(0, 110) + (item.summary.length > 110 ? '…' : '') : 'No summary.'}
                </p>

                <div className="recent-card-footer">
                  <div className="recent-deadline">
                    <Calendar size={13} />
                    <span>{item.deadline || 'No deadline'}</span>
                  </div>
                  <span className="recent-arrow-icon">
                    <ArrowRight size={14} />
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
