import React, { useState } from 'react';
import {
  CheckSquare,
  Square,
  Calendar,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  CheckCircle2,
  FileCheck,
  RotateCcw,
  Sparkles,
  Database,
  Tag,
  Clock,
  Layers,
  FileText
} from 'lucide-react';

export default function ResultsDashboard({
  result,
  onReset,
}) {
  const { data, inserted_id, message, sources = [] } = result || {};
  const {
    title = 'Document Analysis',
    category = 'General',
    summary = '',
    deadline = null,
    priority = 'Medium',
    actions = [],
    required_documents = [],
  } = data || {};

  // Interactive state for actions checklist
  const [completedIndices, setCompletedIndices] = useState(new Set());

  const toggleAction = (idx) => {
    setCompletedIndices((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  // Priority badge styling
  const normalizedPriority = (priority || 'medium').toLowerCase();
  const getPriorityConfig = () => {
    switch (normalizedPriority) {
      case 'high':
        return {
          className: 'priority-high',
          icon: AlertCircle,
          label: 'HIGH PRIORITY',
        };
      case 'low':
        return {
          className: 'priority-low',
          icon: CheckCircle,
          label: 'LOW PRIORITY',
        };
      case 'medium':
      default:
        return {
          className: 'priority-medium',
          icon: Clock,
          label: 'MEDIUM PRIORITY',
        };
    }
  };

  const priorityConfig = getPriorityConfig();
  const PriorityIcon = priorityConfig.icon;

  // Deadline formatting
  const formattedDeadline = deadline
    ? deadline.trim()
    : 'No strict deadline specified';

  return (
    <div className="card results-dashboard">
      {/* Top Meta Bar */}
      <div className="doc-title-card">
        <div className="results-header-bar">
          <div className="results-meta-badges">
            <span className="category-tag">
              <Tag size={12} />
              {category}
            </span>

            {inserted_id && (
              <span className="snowflake-badge" title="Stored in Snowflake DECISIONFLOW_DB.PUBLIC.DOCUMENTS">
                <Database size={12} />
                Snowflake Record #{inserted_id}
              </span>
            )}
          </div>

          <button
            type="button"
            className="btn-secondary"
            onClick={onReset}
            title="Start new analysis"
          >
            <RotateCcw size={15} />
            <span>Analyze Another Document</span>
          </button>
        </div>

        <h2 className="doc-title">{title}</h2>
      </div>

      {/* Intelligence Highlights Grid */}
      <div className="highlights-grid">
        {/* Priority Highlight */}
        <div className="highlight-card">
          <div className="highlight-label">
            <PriorityIcon size={14} />
            Priority Level
          </div>
          <div className={`priority-badge-wrapper ${priorityConfig.className}`}>
            <PriorityIcon size={16} />
            <span>{priorityConfig.label}</span>
          </div>
        </div>

        {/* Deadline Highlight */}
        <div className="highlight-card">
          <div className="highlight-label">
            <Calendar size={14} />
            Deadline / Due Date
          </div>
          <div className="deadline-value">
            <Calendar size={18} style={{ color: deadline ? '#dc2626' : '#64748b' }} />
            <span>{formattedDeadline}</span>
            {deadline && <span className="deadline-pill">Action Required</span>}
          </div>
        </div>
      </div>

      {/* Sources Analyzed Section */}
      {Array.isArray(sources) && sources.length > 0 && (
        <div className="sources-analyzed-container">
          <div className="sources-analyzed-header">
            <Layers size={13} className="sources-icon" />
            <span className="sources-title">Sources Analyzed ({sources.length}):</span>
          </div>
          <div className="sources-list">
            {sources.map((src, idx) => (
              <span key={idx} className="source-item-chip">
                <CheckCircle2 size={13} className="source-check-icon" />
                <span className="source-item-name">{src}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Main Body */}
      <div className="dashboard-body">
        {/* Executive Summary */}
        <div className="summary-section">
          <h3 className="section-title">
            <Sparkles size={18} style={{ color: 'var(--primary-600)' }} />
            Executive Summary
          </h3>
          <div className="summary-text">
            {summary || 'No summary available.'}
          </div>
        </div>

        {/* Actionable Decisions / Checklist */}
        <div className="actions-section">
          <div className="actions-header-row">
            <h3 className="section-title" style={{ margin: 0 }}>
              <CheckSquare size={18} style={{ color: 'var(--primary-600)' }} />
              Actionable Decisions & Next Steps
            </h3>
            <span className="actions-count-pill">
              {completedIndices.size} of {actions.length} Completed
            </span>
          </div>

          {actions && actions.length > 0 ? (
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
                    onKeyDown={(e) => {
                      if (e.key === ' ' || e.key === 'Enter') {
                        e.preventDefault();
                        toggleAction(idx);
                      }
                    }}
                  >
                    <div className="action-checkbox">
                      {isChecked ? <CheckSquare size={14} /> : <Square size={14} color="#94a3b8" />}
                    </div>
                    <span className="action-text">{action}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-docs-notice">
              No specific action items detected in this document.
            </div>
          )}
        </div>

        {/* Required Documents Section */}
        <div className="docs-section">
          <h3 className="section-title">
            <FileCheck size={18} style={{ color: '#0891b2' }} />
            Required Documents & Evidence
          </h3>

          {required_documents && required_documents.length > 0 ? (
            <div className="docs-grid">
              {required_documents.map((doc, idx) => (
                <div key={idx} className="doc-chip-item">
                  <div className="doc-chip-icon">
                    <FileText size={16} />
                  </div>
                  <span className="doc-chip-name">{doc}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-docs-notice">
              No specific external documents or attachments required.
            </div>
          )}
        </div>
      </div>

      {/* Footer Info & Action */}
      <div className="dashboard-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
          <Database size={14} />
          <span>Extracted via Cortex AI (openai-gpt-5) and committed to Snowflake.</span>
        </div>

        <button
          type="button"
          className="btn-secondary"
          onClick={onReset}
        >
          <RotateCcw size={15} />
          <span>Analyze Another Document</span>
        </button>
      </div>
    </div>
  );
}
