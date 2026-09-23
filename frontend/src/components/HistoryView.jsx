import React, { useState } from 'react';
import {
  Clock, Calendar, Tag, AlertCircle, CheckCircle,
  RefreshCw, Plus, ChevronRight, FileText, Loader2,
  Inbox, Trash2, X
} from 'lucide-react';

/* ── Shared mini-components ──────────────────────────────────────── */
function PriorityBadge({ priority }) {
  const p = (priority || 'medium').toLowerCase();
  const cfg = {
    high:   { cls: 'priority-high',   label: 'HIGH'   },
    medium: { cls: 'priority-medium', label: 'MEDIUM' },
    low:    { cls: 'priority-low',    label: 'LOW'    },
  }[p] || { cls: 'priority-medium', label: 'MEDIUM' };
  return (
    <span className={`priority-badge-wrapper ${cfg.cls}`}
      style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem', lineHeight: 1.5 }}>
      {cfg.label}
    </span>
  );
}

function formatDeadline(dateStr) {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr.includes('T') ? dateStr : dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return dateStr; }
}

/* ── Delete Confirmation Modal ───────────────────────────────────── */
function DeleteModal({ title, onConfirm, onCancel, isDeleting }) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-danger-icon"><Trash2 size={20} /></div>
          <h3 className="modal-title">Delete Document?</h3>
          <button type="button" className="modal-close-btn" onClick={onCancel}><X size={16} /></button>
        </div>
        <p className="modal-body">
          You are about to permanently delete <strong>"{title}"</strong> from Snowflake.
          This action <strong>cannot be undone</strong>.
        </p>
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={isDeleting}>
            Cancel
          </button>
          <button
            type="button"
            id="btn-confirm-delete"
            className="btn-danger"
            onClick={onConfirm}
            disabled={isDeleting}
          >
            {isDeleting ? <><Loader2 size={14} className="spin" /> Deleting…</> : <><Trash2 size={14} /> Delete Permanently</>}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Main HistoryView component ──────────────────────────────────── */
export default function HistoryView({
  historyItems = [],
  isLoading = false,
  error = null,
  onViewItem,
  onNewAnalysis,
  onRefresh,
  onDeleteItem,   // (id) => Promise<void>
}) {
  const [deleteTarget, setDeleteTarget] = useState(null); // { id, title }
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDeleteClick = (e, item) => {
    e.stopPropagation();
    setDeleteTarget({ id: item.id, title: item.title });
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await onDeleteItem(deleteTarget.id);
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  };

  return (
    <div className="history-view">
      {/* Delete Modal */}
      {deleteTarget && (
        <DeleteModal
          title={deleteTarget.title}
          onConfirm={handleConfirmDelete}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={isDeleting}
        />
      )}

      {/* Banner */}
      <div className="history-banner">
        <div className="history-banner-left">
          <div className="history-banner-icon"><Clock size={22} strokeWidth={2.1} /></div>
          <div>
            <h2 className="history-banner-title">Active History</h2>
            <p className="history-banner-subtitle">Documents remain here until their deadline passes.</p>
          </div>
        </div>
        <div className="history-banner-actions">
          {!isLoading && (
            <button id="btn-refresh-history" type="button" className="btn-secondary" onClick={onRefresh}>
              <RefreshCw size={14} /> Refresh
            </button>
          )}
          <button
            id="btn-history-new-analysis"
            type="button"
            className="btn-primary"
            style={{ width: 'auto', padding: '0.6rem 1.1rem', fontSize: '0.875rem', boxShadow: '0 2px 8px rgba(79,70,229,0.22)' }}
            onClick={onNewAnalysis}
          >
            <Plus size={15} /> New Analysis
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="alert-banner" style={{ marginBottom: '1.25rem' }}>
          <AlertCircle size={18} className="alert-icon" />
          <div style={{ flex: 1 }}>
            <div className="alert-title">Failed to Load History</div>
            <div className="alert-text">{error}</div>
          </div>
          <button type="button" className="btn-secondary" onClick={onRefresh}
            style={{ padding: '0.3rem 0.7rem', fontSize: '0.8125rem' }}>
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="card" style={{ padding: '3rem 1.5rem', textAlign: 'center' }}>
          <Loader2 size={36} style={{ color: 'var(--primary-600)', margin: '0 auto 1rem', animation: 'spin 1s linear infinite' }} />
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem' }}>Loading document history from Snowflake…</p>
        </div>
      )}

      {/* Empty */}
      {!isLoading && !error && historyItems.length === 0 && (
        <div className="card" style={{ padding: '3.5rem 1.5rem', textAlign: 'center' }}>
          <div style={{
            width: 56, height: 56, borderRadius: 'var(--radius-md)',
            background: 'var(--bg-muted)', display: 'flex', alignItems: 'center',
            justifyContent: 'center', margin: '0 auto 1rem', color: 'var(--text-disabled)',
          }}>
            <Inbox size={28} />
          </div>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.375rem' }}>
            Your History is empty
          </h3>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', maxWidth: 380, margin: '0 auto 1.5rem' }}>
            No documents have been analyzed yet.
          </p>
          <button
            id="btn-empty-state-analyze"
            type="button"
            className="btn-primary"
            style={{ width: 'auto', padding: '0.7rem 1.5rem', margin: '0 auto' }}
            onClick={onNewAnalysis}
          >
            <Plus size={16} /> New Analysis
          </button>
        </div>
      )}

      {/* Card Grid */}
      {!isLoading && !error && historyItems.length > 0 && (
        <>
          <div className="history-stats-bar">
            <span className="history-stats-count">
              <CheckCircle size={14} style={{ color: '#16a34a' }} />
              {historyItems.length} Active Document{historyItems.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="history-grid">
            {historyItems.map(item => (
              <div key={item.id} className="history-card-wrapper">
                {/* Clickable area — opens detail */}
                <button
                  id={`history-card-${item.id}`}
                  type="button"
                  className="history-card"
                  onClick={() => onViewItem(item.id)}
                >
                  {/* Header row */}
                  <div className="history-card-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                      <span className="history-cat-tag"><Tag size={10} />{item.category}</span>
                      <PriorityBadge priority={item.priority} />
                    </div>
                    <ChevronRight size={15} style={{ color: 'var(--text-disabled)', flexShrink: 0 }} />
                  </div>

                  {/* Title */}
                  <div className="history-card-title">{item.title}</div>

                  {/* Summary preview */}
                  {item.summary && (
                    <div className="history-card-summary">
                      {item.summary.length > 110 ? item.summary.slice(0, 110) + '…' : item.summary}
                    </div>
                  )}

                  {/* Footer */}
                  <div className="history-card-footer">
                    {item.deadline ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', fontWeight: 600, color: '#b91c1c' }}>
                        <Calendar size={11} />{formatDeadline(item.deadline)}
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No deadline</span>
                    )}
                    {item.actions && item.actions.length > 0 && (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        <FileText size={11} />{item.actions.length} action{item.actions.length !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </button>

                {/* Delete button — SEPARATE from card-click area */}
                <button
                  type="button"
                  id={`btn-delete-${item.id}`}
                  className="history-card-delete-btn"
                  title="Delete document"
                  onClick={e => handleDeleteClick(e, item)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
