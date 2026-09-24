import React, { useState, useMemo } from 'react';
import {
  GitCompare,
  CheckSquare,
  Square,
  Calendar,
  Tag,
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  ArrowLeft,
  RefreshCw,
  Plus,
  ShieldCheck,
  AlertTriangle,
  Info,
  Layers,
  Sparkles,
  ExternalLink,
  ChevronRight,
  ListChecks,
  Check,
  RotateCcw
} from 'lucide-react';

/* ── Priority Badge Helper ────────────────────────────────────────── */
function PriorityBadge({ priority }) {
  const p = (priority || 'medium').toLowerCase();
  const cfg = {
    high:   { cls: 'priority-high',   label: 'HIGH'   },
    medium: { cls: 'priority-medium', label: 'MEDIUM' },
    low:    { cls: 'priority-low',    label: 'LOW'    },
  }[p] || { cls: 'priority-medium', label: 'MEDIUM' };

  return (
    <span className={`priority-badge-wrapper ${cfg.cls}`} style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem', lineHeight: 1.5 }}>
      {cfg.label}
    </span>
  );
}

/* ── Format Deadline Helper ───────────────────────────────────────── */
function formatDeadline(dateStr) {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr.includes('T') ? dateStr : dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

export default function DecisionCompareView({
  historyItems = [],
  isLoadingHistory = false,
  onNewAnalysis,
  onCompare,
  isComparing = false,
  compareError = null,
  comparisonResult = null,
  onResetComparison,
}) {
  /* Selected IDs for comparison (max 3, min 2) */
  const [selectedIds, setSelectedIds] = useState([]);
  const [selectionWarning, setSelectionWarning] = useState(null);

  /* Pending / active decisions: filter items with deadlines not expired */
  const pendingDecisions = useMemo(() => {
    return historyItems || [];
  }, [historyItems]);

  /* Handle card selection toggle */
  const handleToggleSelect = (id) => {
    setSelectionWarning(null);
    if (selectedIds.includes(id)) {
      setSelectedIds(prev => prev.filter(x => x !== id));
    } else {
      if (selectedIds.length >= 3) {
        setSelectionWarning('Maximum 3 decisions can be compared side by side.');
        return;
      }
      setSelectedIds(prev => [...prev, id]);
    }
  };

  /* Select all (up to 3) */
  const handleSelectAll = () => {
    setSelectionWarning(null);
    const topIds = pendingDecisions.slice(0, 3).map(d => d.id);
    setSelectedIds(topIds);
  };

  /* Clear selection */
  const handleClearSelection = () => {
    setSelectionWarning(null);
    setSelectedIds([]);
  };

  /* Trigger comparison */
  const handleCompareClick = () => {
    if (selectedIds.length < 2 || selectedIds.length > 3) return;
    onCompare(selectedIds);
  };

  const optionLetters = ['Option A', 'Option B', 'Option C'];

  /* ─────────────────────────────────────────────────────────────────
   * VIEW MODE 2: Side-by-Side Comparison Results
   * ───────────────────────────────────────────────────────────────── */
  if (comparisonResult) {
    const {
      options = [],
      common_information = [],
      differences = [],
      conflicts = [],
      different_deadlines = [],
      different_requirements = {},
      missing_information = [],
      important_conditions = [],
      decision_summary = [],
    } = comparisonResult;

    const numOptions = options.length;
    const hasConflicts = conflicts.some(c => !c.toLowerCase().includes('no conflicting information'));

    return (
      <div className="compare-view-container animate-fade-in">
        {/* Navigation / Action bar */}
        <div className="compare-top-nav">
          <button
            type="button"
            id="btn-back-to-selection"
            className="btn-secondary"
            onClick={onResetComparison}
          >
            <ArrowLeft size={15} /> Back to Selection
          </button>

          <div className="compare-meta-pill">
            <GitCompare size={14} className="text-primary" />
            <span>Comparing <strong>{numOptions} Decisions</strong></span>
          </div>

          <button
            type="button"
            id="btn-new-comparison"
            className="btn-secondary"
            onClick={onResetComparison}
          >
            <RotateCcw size={14} /> New Comparison
          </button>
        </div>

        {/* Comparison Header */}
        <div className="compare-header">
          <div className="compare-header-badge">
            <Sparkles size={13} />
            <span>Multi-Document Decision Comparison</span>
          </div>
          <h1 className="page-heading">Decision Intelligence Comparison</h1>
          <p className="page-subheading">
            Objective side-by-side analysis identifying commonalities, differences, conflicts, deadlines, and requirements.
          </p>
        </div>

        {/* ── 1. SIDE-BY-SIDE RESPONSIVE COMPARISON TABLE ───────────── */}
        <div className="card compare-table-card">
          <div className="card-header-row">
            <div className="card-header-left">
              <div className="card-header-icon bg-primary-subtle">
                <GitCompare size={18} />
              </div>
              <div>
                <h3 className="card-title">Side-by-Side Parameter Matrix</h3>
                <p className="card-subtitle">Comprehensive comparison across 9 standardized decision parameters</p>
              </div>
            </div>
          </div>

          <div className="compare-table-wrapper" tabIndex={0} aria-label="Comparison Table">
            <table className={`compare-table col-count-${numOptions}`}>
              <thead>
                <tr>
                  <th className="th-param">Parameter</th>
                  {options.map((opt, idx) => (
                    <th key={opt.id} className={`th-option opt-col-${idx}`}>
                      <div className="opt-header-tag">{optionLetters[idx]}</div>
                      <div className="opt-header-title">{opt.title}</div>
                      <div className="opt-header-sub">ID: #{opt.id}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* 1. Category */}
                <tr>
                  <td className="param-label"><Tag size={13} /> Category</td>
                  {options.map(opt => (
                    <td key={opt.id} className="param-val">
                      <span className="cat-badge">{opt.category || 'General'}</span>
                    </td>
                  ))}
                </tr>

                {/* 2. Deadline */}
                <tr>
                  <td className="param-label"><Calendar size={13} /> Deadline</td>
                  {options.map(opt => (
                    <td key={opt.id} className="param-val">
                      {opt.deadline ? (
                        <div className="deadline-cell highlight-date">
                          <Clock size={13} className="text-danger" />
                          <strong>{formatDeadline(opt.deadline)}</strong>
                        </div>
                      ) : (
                        <span className="text-muted font-italic">Not available</span>
                      )}
                    </td>
                  ))}
                </tr>

                {/* 3. Priority */}
                <tr>
                  <td className="param-label"><AlertCircle size={13} /> Priority</td>
                  {options.map(opt => (
                    <td key={opt.id} className="param-val">
                      <PriorityBadge priority={opt.priority} />
                    </td>
                  ))}
                </tr>

                {/* 4. Eligibility */}
                <tr>
                  <td className="param-label"><ShieldCheck size={13} /> Eligibility</td>
                  {options.map(opt => (
                    <td key={opt.id} className="param-val">
                      {opt.eligibility && opt.eligibility !== 'Not available' ? (
                        <span className="eligibility-text">{opt.eligibility}</span>
                      ) : (
                        <span className="text-muted font-italic">Not available</span>
                      )}
                    </td>
                  ))}
                </tr>

                {/* 5. Required Documents */}
                <tr>
                  <td className="param-label"><FileText size={13} /> Required Documents</td>
                  {options.map(opt => (
                    <td key={opt.id} className="param-val">
                      {opt.required_documents && opt.required_documents.length > 0 ? (
                        <ul className="cell-list">
                          {opt.required_documents.map((d, i) => (
                            <li key={i}>{d}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-muted font-italic">None specified</span>
                      )}
                    </td>
                  ))}
                </tr>

                {/* 6. Important Conditions */}
                <tr>
                  <td className="param-label"><AlertTriangle size={13} /> Important Conditions</td>
                  {options.map(opt => (
                    <td key={opt.id} className="param-val">
                      {opt.important_conditions && opt.important_conditions.length > 0 ? (
                        <ul className="cell-list condition-list">
                          {opt.important_conditions.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-muted font-italic">None specified</span>
                      )}
                    </td>
                  ))}
                </tr>

                {/* 7. Actions */}
                <tr>
                  <td className="param-label"><ListChecks size={13} /> Actions Required</td>
                  {options.map(opt => (
                    <td key={opt.id} className="param-val">
                      {opt.actions && opt.actions.length > 0 ? (
                        <ul className="cell-list action-list">
                          {opt.actions.map((a, i) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-muted font-italic">None specified</span>
                      )}
                    </td>
                  ))}
                </tr>

                {/* 8. Summary / Key Information */}
                <tr>
                  <td className="param-label"><Info size={13} /> Summary / Key Info</td>
                  {options.map(opt => (
                    <td key={opt.id} className="param-val summary-cell">
                      {opt.summary ? (
                        <p>{opt.summary}</p>
                      ) : (
                        <span className="text-muted font-italic">Not available</span>
                      )}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* ── 2. ANALYTICAL FINDINGS GRID ───────────────────────────── */}
        <div className="compare-insights-grid">
          {/* Section: Common Information */}
          <div className="card insight-card insight-common">
            <div className="insight-header">
              <div className="insight-icon icon-emerald"><Layers size={17} /></div>
              <div>
                <h4 className="insight-title">Common Information</h4>
                <p className="insight-subtitle">Shared parameters & requirements across options</p>
              </div>
            </div>
            <ul className="insight-bullets">
              {common_information.map((item, idx) => (
                <li key={idx}>
                  <Check size={14} className="bullet-icon-check" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Section: Key Differences */}
          <div className="card insight-card insight-differences">
            <div className="insight-header">
              <div className="insight-icon icon-indigo"><GitCompare size={17} /></div>
              <div>
                <h4 className="insight-title">Key Differences</h4>
                <p className="insight-subtitle">Distinct requirements, deadlines & priorities</p>
              </div>
            </div>
            <ul className="insight-bullets">
              {differences.map((item, idx) => (
                <li key={idx}>
                  <span className="bullet-dot bullet-dot-indigo" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Section: Conflicting Information */}
          <div className={`card insight-card ${hasConflicts ? 'insight-conflicts-alert' : 'insight-conflicts-clean'}`}>
            <div className="insight-header">
              <div className={`insight-icon ${hasConflicts ? 'icon-amber' : 'icon-emerald'}`}>
                {hasConflicts ? <AlertTriangle size={17} /> : <CheckCircle size={17} />}
              </div>
              <div>
                <h4 className="insight-title">Conflicting Information</h4>
                <p className="insight-subtitle">Inconsistencies or contradictory conditions</p>
              </div>
            </div>
            <ul className="insight-bullets">
              {conflicts.map((item, idx) => (
                <li key={idx} className={hasConflicts ? 'text-conflict' : 'text-clean'}>
                  {hasConflicts ? (
                    <AlertTriangle size={14} className="bullet-icon-warn" />
                  ) : (
                    <CheckCircle size={14} className="bullet-icon-clean" />
                  )}
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Section: Different Deadlines */}
          <div className="card insight-card insight-deadlines">
            <div className="insight-header">
              <div className="insight-icon icon-rose"><Calendar size={17} /></div>
              <div>
                <h4 className="insight-title">Deadline Comparison</h4>
                <p className="insight-subtitle">Chronological timeline & submission dates</p>
              </div>
            </div>
            <ul className="insight-bullets">
              {different_deadlines.map((item, idx) => (
                <li key={idx}>
                  <Clock size={14} className="bullet-icon-clock" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Section: Different Requirements */}
          <div className="card insight-card insight-requirements">
            <div className="insight-header">
              <div className="insight-icon icon-sky"><FileText size={17} /></div>
              <div>
                <h4 className="insight-title">Requirements Breakdown</h4>
                <p className="insight-subtitle">Common prerequisites vs exclusive documents</p>
              </div>
            </div>
            <div className="requirements-breakdown-body">
              {different_requirements.common && different_requirements.common.length > 0 && (
                <div className="req-sub-section">
                  <div className="req-sub-title">Common to All:</div>
                  <div className="req-tags-row">
                    {different_requirements.common.map((r, i) => (
                      <span key={i} className="badge-req-common">{r}</span>
                    ))}
                  </div>
                </div>
              )}
              {different_requirements.per_option && Object.entries(different_requirements.per_option).map(([optName, reqs]) => (
                <div key={optName} className="req-sub-section">
                  <div className="req-sub-title">{optName} Only:</div>
                  {reqs.length > 0 ? (
                    <div className="req-tags-row">
                      {reqs.map((r, i) => (
                        <span key={i} className="badge-req-exclusive">{r}</span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-muted font-italic" style={{ fontSize: '0.8125rem' }}>No exclusive documents</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Section: Missing Information */}
          <div className="card insight-card insight-missing">
            <div className="insight-header">
              <div className="insight-icon icon-slate"><AlertCircle size={17} /></div>
              <div>
                <h4 className="insight-title">Missing Information</h4>
                <p className="insight-subtitle">Unstated deadlines, criteria or instructions</p>
              </div>
            </div>
            <ul className="insight-bullets">
              {missing_information.map((item, idx) => (
                <li key={idx}>
                  <Info size={14} className="bullet-icon-info" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Section: Important Conditions */}
          <div className="card insight-card insight-conditions">
            <div className="insight-header">
              <div className="insight-icon icon-violet"><ShieldCheck size={17} /></div>
              <div>
                <h4 className="insight-title">Important Conditions</h4>
                <p className="insight-subtitle">Special instructions, verification & obligations</p>
              </div>
            </div>
            <ul className="insight-bullets">
              {important_conditions.map((item, idx) => (
                <li key={idx}>
                  <span className="bullet-dot bullet-dot-violet" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* ── 3. DECISION SUMMARY (PROMINENT AT BOTTOM) ─────────────── */}
        <section className="card decision-summary-card" id="decision-summary-section">
          <div className="decision-summary-header">
            <div className="decision-summary-icon">
              <Sparkles size={22} strokeWidth={2.2} />
            </div>
            <div>
              <h2 className="decision-summary-title">Decision Summary</h2>
              <p className="decision-summary-subtitle">Key facts to consider</p>
            </div>
          </div>

          <div className="decision-summary-body">
            <ul className="decision-summary-list">
              {decision_summary.map((finding, idx) => (
                <li key={idx} className="decision-summary-item">
                  <div className="summary-check-circle"><Check size={13} strokeWidth={2.5} /></div>
                  <div className="summary-finding-text">{finding}</div>
                </li>
              ))}
            </ul>
          </div>

          {/* Neutrality & Transparency Disclaimer */}
          <div className="decision-summary-disclaimer">
            <ShieldCheck size={15} className="disclaimer-icon" />
            <span>
              <strong>Impartial Decision Support:</strong> DecisionFlow AI presents objective, extracted factual findings without declaring a winner or recommending a specific choice. The final decision remains entirely yours.
            </span>
          </div>
        </section>
      </div>
    );
  }

  /* ─────────────────────────────────────────────────────────────────
   * VIEW MODE 1: Decision Selection Screen
   * ───────────────────────────────────────────────────────────────── */
  const selectedCount = selectedIds.length;
  const canCompare = selectedCount >= 2 && selectedCount <= 3;

  return (
    <div className="compare-view-container animate-fade-in">
      {/* Page Header */}
      <div className="compare-header">
        <div className="compare-header-badge">
          <GitCompare size={13} />
          <span>Multi-Document Comparison</span>
        </div>
        <h1 className="page-heading">Decision Compare</h1>
        <p className="page-subheading">
          Compare 2–3 analyzed decisions side by side.
        </p>
      </div>

      {/* Selection Control Bar */}
      {pendingDecisions.length > 0 && (
        <div className="compare-selection-bar">
          <div className="selection-counter-wrapper">
            <span className={`selection-counter-badge ${selectedCount >= 2 ? 'ready' : ''}`}>
              {selectedCount} of 3 selected
            </span>
            <span className="selection-helper-text">
              {selectedCount === 0 && 'Select at least 2 decisions to start comparison.'}
              {selectedCount === 1 && 'Select 1 more decision to enable comparison.'}
              {selectedCount === 2 && 'Ready to compare 2 decisions (or select a 3rd).'}
              {selectedCount === 3 && 'Maximum 3 decisions selected.'}
            </span>
          </div>

          <div className="selection-actions">
            {pendingDecisions.length > 2 && selectedCount < 3 && (
              <button
                type="button"
                id="btn-select-all"
                className="btn-text-action"
                onClick={handleSelectAll}
              >
                Select First 3
              </button>
            )}

            {selectedCount > 0 && (
              <button
                type="button"
                id="btn-clear-selection"
                className="btn-text-action"
                onClick={handleClearSelection}
              >
                Clear Selection
              </button>
            )}

            <button
              type="button"
              id="btn-compare-selected"
              className="btn-primary"
              style={{ width: 'auto', padding: '0.65rem 1.4rem' }}
              disabled={!canCompare || isComparing}
              onClick={handleCompareClick}
            >
              {isComparing ? (
                <>
                  <RefreshCw size={15} className="spin" /> Comparing…
                </>
              ) : (
                <>
                  <GitCompare size={15} /> Compare Selected ({selectedCount})
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Warning message if user tries to exceed 3 */}
      {selectionWarning && (
        <div className="alert-banner alert-warning" style={{ marginBottom: '1.25rem' }}>
          <AlertCircle size={17} className="alert-icon" />
          <div className="alert-text">{selectionWarning}</div>
        </div>
      )}

      {/* Comparison error banner */}
      {compareError && (
        <div className="alert-banner" style={{ marginBottom: '1.25rem' }}>
          <AlertCircle size={18} className="alert-icon" />
          <div style={{ flex: 1 }}>
            <div className="alert-title">Comparison Failed</div>
            <div className="alert-text">{compareError}</div>
          </div>
        </div>
      )}

      {/* ── EMPTY STATE: 0 decisions ── */}
      {!isLoadingHistory && pendingDecisions.length === 0 && (
        <div className="card compare-empty-card">
          <div className="empty-icon-box">
            <GitCompare size={32} />
          </div>
          <h3 className="empty-card-title">No pending decisions to compare yet</h3>
          <p className="empty-card-sub">
            Decision Compare uses documents analyzed and stored in your active session. Analyze documents first to compare them side by side.
          </p>
          <button
            type="button"
            id="btn-empty-analyze"
            className="btn-primary"
            style={{ width: 'auto', padding: '0.7rem 1.5rem', margin: '0 auto' }}
            onClick={onNewAnalysis}
          >
            <Plus size={16} /> Analyze a Document
          </button>
        </div>
      )}

      {/* ── EMPTY STATE: Only 1 decision ── */}
      {!isLoadingHistory && pendingDecisions.length === 1 && (
        <div className="card compare-empty-card">
          <div className="empty-icon-box icon-single">
            <AlertCircle size={32} />
          </div>
          <h3 className="empty-card-title">At least 2 decisions are required for comparison</h3>
          <p className="empty-card-sub">
            You currently have 1 active document analyzed. Analyze a second document to compare deadlines, requirements, and conditions.
          </p>
          <button
            type="button"
            id="btn-empty-analyze-another"
            className="btn-primary"
            style={{ width: 'auto', padding: '0.7rem 1.5rem', margin: '0 auto' }}
            onClick={onNewAnalysis}
          >
            <Plus size={16} /> Analyze Another Document
          </button>
        </div>
      )}

      {/* ── SELECTABLE DECISION CARDS GRID ── */}
      {pendingDecisions.length > 0 && (
        <div className="compare-cards-grid">
          {pendingDecisions.map((doc) => {
            const isSelected = selectedIds.includes(doc.id);
            const selectionIndex = selectedIds.indexOf(doc.id);

            return (
              <div
                key={doc.id}
                id={`compare-card-${doc.id}`}
                className={`compare-select-card ${isSelected ? 'selected' : ''}`}
                onClick={() => handleToggleSelect(doc.id)}
              >
                <div className="card-top-row">
                  <div className="card-checkbox-area">
                    {isSelected ? (
                      <div className="checkbox-active">
                        <Check size={13} strokeWidth={3} />
                      </div>
                    ) : (
                      <div className="checkbox-empty" />
                    )}
                    {isSelected && (
                      <span className="selected-order-tag">
                        {optionLetters[selectionIndex]}
                      </span>
                    )}
                  </div>

                  <div className="card-badges-row">
                    <span className="history-cat-tag">
                      <Tag size={10} /> {doc.category || 'General'}
                    </span>
                    <PriorityBadge priority={doc.priority} />
                  </div>
                </div>

                <h3 className="card-doc-title">{doc.title}</h3>

                {doc.summary && (
                  <p className="card-doc-summary">
                    {doc.summary.length > 120 ? doc.summary.slice(0, 120) + '…' : doc.summary}
                  </p>
                )}

                <div className="card-doc-footer">
                  {doc.deadline ? (
                    <span className="card-footer-deadline">
                      <Calendar size={12} /> {formatDeadline(doc.deadline)}
                    </span>
                  ) : (
                    <span className="card-footer-muted">No deadline specified</span>
                  )}
                  <span className="card-doc-id">ID: #{doc.id}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
