import React, { useState, useMemo } from 'react';
import {
  CalendarClock,
  AlertCircle,
  Clock,
  Calendar,
  CheckCircle2,
  Check,
  RotateCcw,
  RefreshCw,
  Search,
  Filter,
  ArrowUpDown,
  Tag,
  FileText,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Plus,
  AlertTriangle,
  CalendarDays
} from 'lucide-react';

/* ── Helper: Priority Badge ─────────────────────────────────────────── */
function PriorityBadge({ priority }) {
  const p = (priority || 'medium').toLowerCase();
  const cfg = {
    high:   { cls: 'deadline-badge--high',   label: 'HIGH PRIORITY' },
    medium: { cls: 'deadline-badge--med',    label: 'MEDIUM PRIORITY' },
    low:    { cls: 'deadline-badge--low',    label: 'LOW PRIORITY' },
  }[p] || { cls: 'deadline-badge--med', label: 'MEDIUM PRIORITY' };

  return <span className={`deadline-badge ${cfg.cls}`}>{cfg.label}</span>;
}

/* ── Helper: Status Badge ───────────────────────────────────────────── */
function StatusBadge({ status, daysRemaining }) {
  if (status === 'Completed') {
    return (
      <span className="deadline-status-pill status-completed">
        <CheckCircle2 size={13} strokeWidth={2.5} />
        <span>Completed</span>
      </span>
    );
  }
  if (status === 'Overdue') {
    const days = Math.abs(daysRemaining ?? 0);
    return (
      <span className="deadline-status-pill status-overdue">
        <AlertCircle size={13} strokeWidth={2.5} />
        <span>Overdue ({days === 0 ? 'today' : `${days}d ago`})</span>
      </span>
    );
  }
  if (status === 'Due Soon') {
    const days = daysRemaining ?? 0;
    return (
      <span className="deadline-status-pill status-due-soon">
        <Clock size={13} strokeWidth={2.5} />
        <span>{days === 0 ? 'Due Today' : `Due Soon (${days}d left)`}</span>
      </span>
    );
  }
  // Upcoming
  const days = daysRemaining ?? 0;
  return (
    <span className="deadline-status-pill status-upcoming">
      <CalendarDays size={13} strokeWidth={2.5} />
      <span>Upcoming ({days}d left)</span>
    </span>
  );
}

/* ── Helper: Format Deadline Date ───────────────────────────────────── */
function formatDeadlineDate(dateStr) {
  if (!dateStr) return 'No deadline set';
  try {
    const d = new Date(dateStr.includes('T') ? dateStr : `${dateStr}T00:00:00`);
    return d.toLocaleDateString('en-IN', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export default function DeadlineCenterView({
  deadlineItems = [],
  counts = {},
  isLoading = false,
  error = null,
  onRefresh,
  onUpdateCompletion,
  onNewAnalysis,
  updatingDocId = null,
}) {
  const [activeFilter, setActiveFilter] = useState('ALL'); // ALL | Overdue | Due Soon | Upcoming | Completed
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('deadline-asc'); // deadline-asc | deadline-desc | priority | name
  const [expandedDocIds, setExpandedDocIds] = useState(new Set());

  // Toggle multi-actions expanded state
  const toggleExpand = (docId) => {
    setExpandedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  };

  // Dynamic counts calculation
  const calculatedCounts = useMemo(() => {
    const c = {
      Overdue: 0,
      'Due Soon': 0,
      Upcoming: 0,
      Completed: 0,
      ...counts,
    };
    if (!counts || Object.keys(counts).length === 0) {
      deadlineItems.forEach((item) => {
        if (item.status && c[item.status] !== undefined) {
          c[item.status] += 1;
        }
      });
    }
    return c;
  }, [deadlineItems, counts]);

  // Filtered & sorted deadline items
  const processedItems = useMemo(() => {
    let result = [...deadlineItems];

    // Filter by status
    if (activeFilter !== 'ALL') {
      result = result.filter((item) => item.status === activeFilter);
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        (item) =>
          item.task?.toLowerCase().includes(q) ||
          item.category?.toLowerCase().includes(q) ||
          item.required_action?.toLowerCase().includes(q) ||
          item.source_document?.toLowerCase().includes(q)
      );
    }

    // Sorting
    result.sort((a, b) => {
      if (sortBy === 'deadline-asc') {
        const da = a.days_remaining ?? 999999;
        const db = b.days_remaining ?? 999999;
        return da - db;
      }
      if (sortBy === 'deadline-desc') {
        const da = a.days_remaining ?? -999999;
        const db = b.days_remaining ?? -999999;
        return db - da;
      }
      if (sortBy === 'priority') {
        const rank = { High: 3, Medium: 2, Low: 1 };
        const pa = rank[a.priority] || 2;
        const pb = rank[b.priority] || 2;
        if (pb !== pa) return pb - pa;
        return (a.days_remaining ?? 999999) - (b.days_remaining ?? 999999);
      }
      if (sortBy === 'name') {
        return (a.task || '').localeCompare(b.task || '');
      }
      return 0;
    });

    return result;
  }, [deadlineItems, activeFilter, searchQuery, sortBy]);

  return (
    <div className="deadline-center-container">
      {/* ── Page Header ── */}
      <div className="deadline-center-header">
        <div className="deadline-header-left">
          <div className="deadline-title-row">
            <div className="deadline-title-icon-badge">
              <CalendarClock size={24} strokeWidth={2.2} />
            </div>
            <div>
              <div className="deadline-section-tag">
                <Sparkles size={13} style={{ display: 'inline', marginRight: 4 }} />
                MINOR USP • SMART DEADLINE TRACKER
              </div>
              <h1 className="deadline-page-title">Deadline Center</h1>
            </div>
          </div>
          <p className="deadline-page-subtitle">
            Automatically organized deadlines and time-sensitive requirements extracted from your analyzed documents.
          </p>
        </div>

        <div className="deadline-header-actions">
          {onRefresh && (
            <button
              type="button"
              className="btn btn-secondary deadline-refresh-btn"
              onClick={onRefresh}
              disabled={isLoading}
              title="Refresh deadlines from database"
            >
              <RefreshCw size={15} className={isLoading ? 'spinning' : ''} />
              <span>Refresh</span>
            </button>
          )}
          {onNewAnalysis && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onNewAnalysis}
            >
              <Plus size={16} />
              <span>New Analysis</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Summary / Stat Cards ── */}
      <div className="deadline-stats-grid">
        {/* Overdue */}
        <div
          className={`deadline-stat-card stat-card--overdue ${activeFilter === 'Overdue' ? 'active-filter' : ''}`}
          onClick={() => setActiveFilter((prev) => (prev === 'Overdue' ? 'ALL' : 'Overdue'))}
          role="button"
          tabIndex={0}
          title="Click to filter by Overdue"
        >
          <div className="stat-card-top">
            <span className="stat-card-label">Overdue</span>
            <div className="stat-icon-wrapper icon--overdue">
              <AlertCircle size={18} strokeWidth={2.4} />
            </div>
          </div>
          <div className="stat-card-value text--overdue">{calculatedCounts.Overdue || 0}</div>
          <div className="stat-card-desc">Passed deadlines requiring attention</div>
        </div>

        {/* Due Soon */}
        <div
          className={`deadline-stat-card stat-card--due-soon ${activeFilter === 'Due Soon' ? 'active-filter' : ''}`}
          onClick={() => setActiveFilter((prev) => (prev === 'Due Soon' ? 'ALL' : 'Due Soon'))}
          role="button"
          tabIndex={0}
          title="Click to filter by Due Soon"
        >
          <div className="stat-card-top">
            <span className="stat-card-label">Due Soon</span>
            <div className="stat-icon-wrapper icon--due-soon">
              <Clock size={18} strokeWidth={2.4} />
            </div>
          </div>
          <div className="stat-card-value text--due-soon">{calculatedCounts['Due Soon'] || 0}</div>
          <div className="stat-card-desc">Deadlines within the next 7 days</div>
        </div>

        {/* Upcoming */}
        <div
          className={`deadline-stat-card stat-card--upcoming ${activeFilter === 'Upcoming' ? 'active-filter' : ''}`}
          onClick={() => setActiveFilter((prev) => (prev === 'Upcoming' ? 'ALL' : 'Upcoming'))}
          role="button"
          tabIndex={0}
          title="Click to filter by Upcoming"
        >
          <div className="stat-card-top">
            <span className="stat-card-label">Upcoming</span>
            <div className="stat-icon-wrapper icon--upcoming">
              <CalendarDays size={18} strokeWidth={2.4} />
            </div>
          </div>
          <div className="stat-card-value text--upcoming">{calculatedCounts.Upcoming || 0}</div>
          <div className="stat-card-desc">Scheduled for more than 7 days out</div>
        </div>

        {/* Completed */}
        <div
          className={`deadline-stat-card stat-card--completed ${activeFilter === 'Completed' ? 'active-filter' : ''}`}
          onClick={() => setActiveFilter((prev) => (prev === 'Completed' ? 'ALL' : 'Completed'))}
          role="button"
          tabIndex={0}
          title="Click to filter by Completed"
        >
          <div className="stat-card-top">
            <span className="stat-card-label">Completed</span>
            <div className="stat-icon-wrapper icon--completed">
              <CheckCircle2 size={18} strokeWidth={2.4} />
            </div>
          </div>
          <div className="stat-card-value text--completed">{calculatedCounts.Completed || 0}</div>
          <div className="stat-card-desc">Manually resolved tasks</div>
        </div>
      </div>

      {/* ── Controls Bar: Filters, Search, Sort ── */}
      <div className="deadline-controls-bar">
        {/* Filter Pills */}
        <div className="deadline-filter-pills" role="tablist">
          {[
            { id: 'ALL', label: 'All Items', count: deadlineItems.length },
            { id: 'Overdue', label: 'Overdue', count: calculatedCounts.Overdue || 0 },
            { id: 'Due Soon', label: 'Due Soon', count: calculatedCounts['Due Soon'] || 0 },
            { id: 'Upcoming', label: 'Upcoming', count: calculatedCounts.Upcoming || 0 },
            { id: 'Completed', label: 'Completed', count: calculatedCounts.Completed || 0 },
          ].map(({ id, label, count }) => (
            <button
              key={id}
              type="button"
              className={`deadline-filter-pill ${activeFilter === id ? 'active' : ''}`}
              onClick={() => setActiveFilter(id)}
            >
              <span>{label}</span>
              <span className="pill-badge">{count}</span>
            </button>
          ))}
        </div>

        {/* Right side: Search & Sort */}
        <div className="deadline-controls-right">
          {/* Search */}
          <div className="deadline-search-box">
            <Search size={15} className="search-icon" />
            <input
              type="text"
              placeholder="Search tasks, categories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="deadline-search-input"
            />
            {searchQuery && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => setSearchQuery('')}
                title="Clear search"
              >
                ×
              </button>
            )}
          </div>

          {/* Sort Selector */}
          <div className="deadline-sort-box">
            <ArrowUpDown size={14} className="sort-icon" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="deadline-sort-select"
            >
              <option value="deadline-asc">Deadline (Nearest first)</option>
              <option value="deadline-desc">Deadline (Furthest first)</option>
              <option value="priority">Priority (High to Low)</option>
              <option value="name">Task Name (A to Z)</option>
            </select>
          </div>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="deadline-error-banner">
          <AlertTriangle size={18} />
          <div className="error-text">
            <strong>Error loading deadlines:</strong> {error}
          </div>
          {onRefresh && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={onRefresh}>
              Retry
            </button>
          )}
        </div>
      )}

      {/* ── Loading State ── */}
      {isLoading && (
        <div className="deadline-loading-state">
          <div className="loading-spinner-ring" />
          <p>Loading deadline schedule from Snowflake...</p>
        </div>
      )}

      {/* ── Empty State 1: No documents analyzed yet ── */}
      {!isLoading && deadlineItems.length === 0 && (
        <div className="deadline-empty-card">
          <div className="empty-icon-circle">
            <CalendarClock size={36} strokeWidth={1.8} />
          </div>
          <h3 className="empty-title">No Deadlines Detected Yet</h3>
          <p className="empty-description">
            When you analyze circulars, contracts, or notices that contain dates and deadlines,
            they will automatically be organized and tracked here with urgency alerts.
          </p>
          {onNewAnalysis && (
            <button
              type="button"
              className="btn btn-primary btn-lg"
              onClick={onNewAnalysis}
            >
              <Plus size={18} />
              <span>Analyze Your First Document</span>
            </button>
          )}
        </div>
      )}

      {/* ── Empty State 2: Filters returned 0 results ── */}
      {!isLoading && deadlineItems.length > 0 && processedItems.length === 0 && (
        <div className="deadline-empty-card deadline-empty-card--filtered">
          <div className="empty-icon-circle">
            <Filter size={30} strokeWidth={1.8} />
          </div>
          <h3 className="empty-title">No Deadlines Match Your Filters</h3>
          <p className="empty-description">
            There are no deadline items matching the currently selected status filter ({activeFilter})
            {searchQuery ? ` and search query "${searchQuery}"` : ''}.
          </p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setActiveFilter('ALL');
              setSearchQuery('');
            }}
          >
            Clear All Filters
          </button>
        </div>
      )}

      {/* ── Deadlines Cards List ── */}
      {!isLoading && processedItems.length > 0 && (
        <div className="deadline-cards-list">
          {processedItems.map((item) => {
            const isUpdating = updatingDocId === item.document_id;
            const isCompleted = Boolean(item.completed);
            const isExpanded = expandedDocIds.has(item.document_id);
            const hasExtraActions = Array.isArray(item.actions) && item.actions.length > 1;

            return (
              <div
                key={item.document_id}
                className={`deadline-card ${isCompleted ? 'deadline-card--completed' : ''} ${
                  item.status === 'Overdue' && !isCompleted ? 'deadline-card--overdue' : ''
                } ${item.status === 'Due Soon' && !isCompleted ? 'deadline-card--due-soon' : ''}`}
              >
                {/* Card Top Row: Status, Priority, Category */}
                <div className="deadline-card-header">
                  <div className="deadline-card-badges">
                    <StatusBadge status={item.status} daysRemaining={item.days_remaining} />
                    <PriorityBadge priority={item.priority} />
                    {item.category && (
                      <span className="deadline-category-badge">
                        <Tag size={11} />
                        <span>{item.category}</span>
                      </span>
                    )}
                  </div>

                  {/* Quick completion toggle */}
                  <button
                    type="button"
                    className={`deadline-toggle-btn ${isCompleted ? 'btn-is-completed' : 'btn-mark-complete'}`}
                    disabled={isUpdating}
                    onClick={() => onUpdateCompletion && onUpdateCompletion(item.document_id, !isCompleted)}
                    title={isCompleted ? 'Mark as incomplete' : 'Mark task completed'}
                  >
                    {isUpdating ? (
                      <div className="btn-spinner" />
                    ) : isCompleted ? (
                      <>
                        <Check size={14} strokeWidth={2.5} />
                        <span>Completed</span>
                      </>
                    ) : (
                      <>
                        <span className="checkbox-empty" />
                        <span>Mark Complete</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Card Body: Task Name & Source Document */}
                <div className="deadline-card-body">
                  <h3 className={`deadline-task-title ${isCompleted ? 'title--completed' : ''}`}>
                    {item.task}
                  </h3>

                  {item.source_document && item.source_document !== item.task && (
                    <div className="deadline-source-row">
                      <FileText size={13} />
                      <span>Source: {item.source_document}</span>
                    </div>
                  )}

                  {/* Deadline Date Pill Row */}
                  <div className="deadline-date-box">
                    <div className="date-box-left">
                      <Calendar size={15} className="date-box-icon" />
                      <div>
                        <div className="date-box-label">Official Deadline</div>
                        <div className="date-box-val">{formatDeadlineDate(item.deadline)}</div>
                      </div>
                    </div>

                    <div className="date-box-right">
                      {isCompleted ? (
                        <span className="remaining-pill pill-completed">
                          <CheckCircle2 size={12} />
                          Resolved
                        </span>
                      ) : item.days_remaining < 0 ? (
                        <span className="remaining-pill pill-overdue">
                          Overdue by {Math.abs(item.days_remaining)} day{Math.abs(item.days_remaining) === 1 ? '' : 's'}
                        </span>
                      ) : item.days_remaining === 0 ? (
                        <span className="remaining-pill pill-today">
                          Due today
                        </span>
                      ) : (
                        <span className={`remaining-pill ${item.days_remaining <= 7 ? 'pill-due-soon' : 'pill-upcoming'}`}>
                          {item.days_remaining} day{item.days_remaining === 1 ? '' : 's'} remaining
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Required Action Highlight Box */}
                  <div className="deadline-action-box">
                    <div className="action-box-header">
                      <span className="action-box-tag">REQUIRED ACTION</span>
                    </div>
                    <p className="action-box-text">{item.required_action}</p>

                    {/* Additional actions accordion if present */}
                    {hasExtraActions && (
                      <div className="deadline-extra-actions">
                        <button
                          type="button"
                          className="extra-actions-toggle"
                          onClick={() => toggleExpand(item.document_id)}
                        >
                          <span>{isExpanded ? 'Hide' : 'View'} other actions ({item.actions.length})</span>
                          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>

                        {isExpanded && (
                          <ul className="extra-actions-list">
                            {item.actions.map((act, idx) => (
                              <li key={idx} className="extra-action-item">
                                <span className="action-bullet">{idx + 1}</span>
                                <span>{act}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Footer: Toggle and details */}
                <div className="deadline-card-footer">
                  <div className="footer-doc-id">
                    Doc #{item.document_id}
                  </div>
                  {isCompleted && (
                    <button
                      type="button"
                      className="reopen-link-btn"
                      disabled={isUpdating}
                      onClick={() => onUpdateCompletion && onUpdateCompletion(item.document_id, false)}
                    >
                      <RotateCcw size={12} />
                      <span>Reopen Task</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
