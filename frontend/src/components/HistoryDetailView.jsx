import React, { useState } from 'react';
import {
  ArrowLeft, Calendar, Tag, CheckSquare, Square,
  FileCheck, Database, Clock, Plus, FileText, Trash2, X, Loader2
} from 'lucide-react';

/* ── Shared helpers ──────────────────────────────────────────────── */
function PriorityBadge({ priority }) {
  const p = (priority || 'medium').toLowerCase();
  const cfg = {
    high:   { cls: 'priority-high',   label: 'HIGH'   },
    medium: { cls: 'priority-medium', label: 'MEDIUM' },
    low:    { cls: 'priority-low',    label: 'LOW'    },
  }[p] || { cls: 'priority-medium', label: 'MEDIUM' };
  return (
    <span className={`priority-badge-wrapper ${cfg.cls}`} style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}>
      {cfg.label}
    </span>
  );
}

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr.includes('T') ? dateStr : dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
  } catch { return dateStr; }
}

function formatDateTime(isoStr) {
  if (!isoStr) return null;
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return isoStr; }
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
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={isDeleting}>Cancel</button>
          <button
            type="button"
            id="btn-confirm-delete-detail"
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

/* ── Main component ──────────────────────────────────────────────── */
export default function HistoryDetailView({ item, onBack, onNewAnalysis, onDeleteItem }) {
  const [completedIndices, setCompletedIndices] = useState(new Set());
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  if (!item) return null;

  const { id, title, category, summary, deadline, priority, actions = [], required_documents = [], created_at } = item;

  const toggleAction = (idx) => {
    setCompletedIndices(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    try {
      await onDeleteItem(id);
      // onDeleteItem navigates away; no need to reset here
    } finally {
      setIsDeleting(false);
      setShowDeleteModal(false);
    }
  };

  return (
    <div className="results-dashboard" style={{ animation: 'fadeIn 0.25s ease-out' }}>
      {showDeleteModal && (
        <DeleteModal
          title={title}
          onConfirm={handleConfirmDelete}
          onCancel={() => setShowDeleteModal(false)}
          isDeleting={isDeleting}
        />
      )}

      {/* Nav row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <button id="btn-back-to-history" type="button" className="btn-secondary" onClick={onBack}>
          <ArrowLeft size={15} /> Back to History
        </button>
        <div style={{ display: 'flex', gap: '0.625rem' }}>
          <button
            id="btn-delete-from-detail"
            type="button"
            className="btn-danger-outline"
            onClick={() => setShowDeleteModal(true)}
          >
            <Trash2 size={14} /> Delete
          </button>
          <button
            id="btn-new-analysis-detail"
            type="button"
            className="btn-primary"
            style={{ width: 'auto', padding: '0.55rem 1.1rem', fontSize: '0.875rem', boxShadow: 'none' }}
            onClick={onNewAnalysis}
          >
            <Plus size={15} /> New Analysis
          </button>
        </div>
      </div>

      <div className="card">
        {/* Title section */}
        <div className="doc-title-card">
          <div className="results-header-bar">
            <div className="results-meta-badges">
              <span className="category-tag"><Tag size={12} />{category}</span>
              <PriorityBadge priority={priority} />
              {id && (
                <span className="snowflake-badge">
                  <Database size={12} /> Record #{id}
                </span>
              )}
            </div>
          </div>
          <h2 className="doc-title">{title}</h2>
          {created_at && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <Clock size={12} /> Analyzed on {formatDateTime(created_at)}
            </div>
          )}
        </div>

        {/* Highlights */}
        <div className="highlights-grid">
          <div className="highlight-card">
            <div className="highlight-label"><Tag size={13} />Priority Level</div>
            <PriorityBadge priority={priority} />
          </div>
          <div className="highlight-card">
            <div className="highlight-label"><Calendar size={13} />Deadline / Due Date</div>
            <div className="deadline-value">
              <Calendar size={17} style={{ color: deadline ? '#dc2626' : '#64748b' }} />
              <span>{deadline ? formatDate(deadline) : 'No strict deadline'}</span>
              {deadline && <span className="deadline-pill">Action Required</span>}
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="dashboard-body">
          {/* Summary */}
          <div className="summary-section">
            <h3 className="section-title" style={{ color: 'var(--text-main)' }}>Executive Summary</h3>
            <div className="summary-text">{summary || 'No summary available.'}</div>
          </div>

          {/* Actions checklist */}
          <div className="actions-section">
            <div className="actions-header-row">
              <h3 className="section-title" style={{ margin: 0 }}>
                <CheckSquare size={17} style={{ color: 'var(--primary-600)' }} />
                Actionable Decisions &amp; Next Steps
              </h3>
              <span className="actions-count-pill">{completedIndices.size} of {actions.length} Completed</span>
            </div>
            {actions.length > 0 ? (
              <div className="actions-list">
                {actions.map((action, idx) => {
                  const isChecked = completedIndices.has(idx);
                  return (
                    <div
                      key={idx}
                      className={`action-item ${isChecked ? 'checked' : ''}`}
                      onClick={() => toggleAction(idx)}
                      role="checkbox"
                      aria-checked={isChecked}
                      tabIndex={0}
                      onKeyDown={e => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggleAction(idx); } }}
                    >
                      <div className="action-checkbox">
                        {isChecked ? <CheckSquare size={13} /> : <Square size={13} color="#94a3b8" />}
                      </div>
                      <span className="action-text">{action}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="empty-docs-notice">No specific action items detected.</div>
            )}
          </div>

          {/* Required docs */}
          <div className="docs-section">
            <h3 className="section-title">
              <FileCheck size={17} style={{ color: '#0891b2' }} />
              Required Documents &amp; Evidence
            </h3>
            {required_documents.length > 0 ? (
              <div className="docs-grid">
                {required_documents.map((doc, idx) => (
                  <div key={idx} className="doc-chip-item">
                    <div className="doc-chip-icon"><FileText size={15} /></div>
                    <span className="doc-chip-name">{doc}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-docs-notice">No specific documents required.</div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="dashboard-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            <Database size={13} />
            <span>Snowflake DECISIONFLOW_DB.PUBLIC.DOCUMENTS</span>
          </div>
          <div style={{ display: 'flex', gap: '0.625rem' }}>
            <button type="button" className="btn-danger-outline" onClick={() => setShowDeleteModal(true)}>
              <Trash2 size={14} /> Delete Record
            </button>
            <button type="button" className="btn-secondary" onClick={onBack}>
              <ArrowLeft size={14} /> Back to History
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
