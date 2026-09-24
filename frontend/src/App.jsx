import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import DashboardView from './components/DashboardView';
import InputSection from './components/InputSection';
import LoadingView from './components/LoadingView';
import ResultsDashboard from './components/ResultsDashboard';
import ErrorMessage from './components/ErrorMessage';
import HistoryView from './components/HistoryView';
import HistoryDetailView from './components/HistoryDetailView';
import DecisionCompareView from './components/DecisionCompareView';
import DeadlineCenterView from './components/DeadlineCenterView';
import PageTransition from './components/PageTransition';
import {
  checkBackendHealth,
  analyzeText,
  analyzePdf,
  analyzeUnified,
  fetchHistory,
  fetchHistoryItem,
  deleteHistoryItem,
  compareDocuments,
  getDeadlines,
  updateDeadlineCompletion,
} from './api';

export default function App() {
  /* ── Backend health ─────────────────────────────────────────────── */
  const [backendConnected, setBackendConnected] = useState(true);

  /* ── Analysis state ─────────────────────────────────────────────── */
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isPdfAnalysis, setIsPdfAnalysis] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [lastAttempt, setLastAttempt] = useState(null);

  /* ── Navigation: 'dashboard' | 'result' | 'new' | 'history' | 'history-detail' | 'compare' */
  const [activeView, setActiveView] = useState('dashboard');

  /* ── History state ──────────────────────────────────────────────── */
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState(null);
  const [historyDetailLoading, setHistoryDetailLoading] = useState(false);

  /* ── Decision Compare state ─────────────────────────────────────── */
  const [comparisonResult, setComparisonResult] = useState(null);
  const [isComparing, setIsComparing] = useState(false);
  const [compareError, setCompareError] = useState(null);

  /* ── Deadline Center state ───────────────────────────────────────── */
  const [deadlineItems, setDeadlineItems] = useState([]);
  const [deadlineCounts, setDeadlineCounts] = useState({});
  const [deadlineLoading, setDeadlineLoading] = useState(false);
  const [deadlineError, setDeadlineError] = useState(null);
  const [updatingDeadlineDocId, setUpdatingDeadlineDocId] = useState(null);

  /* ── Health probe ───────────────────────────────────────────────── */
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const h = await checkBackendHealth();
        if (alive) setBackendConnected(h?.status === 'healthy');
      } catch {
        if (alive) setBackendConnected(false);
      }
    };
    check();
    const t = setInterval(check, 15000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  /* ── Load history ───────────────────────────────────────────────── */
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const data = await fetchHistory();
      setHistoryItems(data?.data ?? []);
    } catch (err) {
      setHistoryError(err.message || 'Failed to load history.');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  /* ── Load Deadlines ─────────────────────────────────────────────── */
  const loadDeadlines = useCallback(async () => {
    setDeadlineLoading(true);
    setDeadlineError(null);
    try {
      const resp = await getDeadlines();
      if (resp?.success) {
        setDeadlineItems(resp.data || []);
        setDeadlineCounts(resp.counts || {});
      } else {
        throw new Error(resp?.message || 'Failed to load deadlines.');
      }
    } catch (err) {
      console.error('Failed to load deadlines:', err);
      setDeadlineError(err.message || 'Failed to load deadlines from backend.');
    } finally {
      setDeadlineLoading(false);
    }
  }, []);

  /* ── Toggle Deadline Completion ─────────────────────────────────── */
  const handleUpdateDeadlineCompletion = async (documentId, completed) => {
    setUpdatingDeadlineDocId(documentId);
    try {
      const resp = await updateDeadlineCompletion(documentId, completed);
      if (resp?.success) {
        // Optimistic UI update
        setDeadlineItems((prev) =>
          prev.map((item) =>
            item.document_id === documentId
              ? {
                  ...item,
                  completed,
                  status: completed
                    ? 'Completed'
                    : (item.days_remaining < 0
                        ? 'Overdue'
                        : item.days_remaining <= 7
                        ? 'Due Soon'
                        : 'Upcoming'),
                }
              : item
          )
        );
        // Refresh cleanly in background to synchronize counts
        loadDeadlines();
      } else {
        throw new Error(resp?.message || 'Failed to update completion.');
      }
    } catch (err) {
      console.error('Error updating completion:', err);
      alert(err.message || 'Failed to update deadline status.');
    } finally {
      setUpdatingDeadlineDocId(null);
    }
  };

  // Load history on mount and when entering history/dashboard
  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  /* ── Navigation ─────────────────────────────────────────────────── */
  const handleNavigate = (view) => {
    if (view === 'dashboard') {
      setResult(null);
      setError(null);
      setLastAttempt(null);
      setIsAnalyzing(false);
      setActiveView('dashboard');
    } else if (view === 'new') {
      setResult(null);
      setError(null);
      setLastAttempt(null);
      setIsAnalyzing(false);
      setActiveView('new');
    } else if (view === 'history') {
      loadHistory();
      setActiveView('history');
    } else if (view === 'compare') {
      loadHistory();
      setCompareError(null);
      setActiveView('compare');
    } else if (view === 'deadlines') {
      loadDeadlines();
      setActiveView('deadlines');
    }
  };

  /* ── Compare Handler ────────────────────────────────────────────── */
  const handleCompare = async (selectedIds) => {
    setIsComparing(true);
    setCompareError(null);
    try {
      const resp = await compareDocuments(selectedIds);
      if (resp?.success && resp?.data) {
        setComparisonResult(resp.data);
      } else {
        throw new Error(resp?.message || 'Failed to compare decisions.');
      }
    } catch (err) {
      console.error('Decision comparison error:', err);
      setCompareError(err.message || 'Comparison failed. Please verify the backend connection.');
    } finally {
      setIsComparing(false);
    }
  };

  const handleResetComparison = () => {
    setComparisonResult(null);
    setCompareError(null);
  };

  /* ── Analysis ───────────────────────────────────────────────────── */
  const handleAnalyzeText = async (text) => {
    setIsAnalyzing(true);
    setIsPdfAnalysis(false);
    setError(null);
    setLastAttempt({ type: 'text', payload: text });

    try {
      const response = await analyzeText(text);
      if (response?.success) {
        setResult(response);
        setActiveView('result');
        // Refresh history in background so new item is reflected
        loadHistory();
      } else {
        throw new Error(response?.message || 'Failed to analyze text.');
      }
    } catch (err) {
      console.error('Text analysis error:', err);
      setError(err.message || 'Unable to complete analysis. Please verify the backend is running at http://127.0.0.1:8000.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleAnalyzePdf = async (file) => {
    setIsAnalyzing(true);
    setIsPdfAnalysis(true);
    setError(null);
    setLastAttempt({ type: 'pdf', payload: file });

    try {
      const response = await analyzePdf(file);
      if (response?.success) {
        setResult(response);
        setActiveView('result');
        // Refresh history in background so new item is reflected
        loadHistory();
      } else {
        throw new Error(response?.message || 'Failed to analyze PDF file.');
      }
    } catch (err) {
      console.error('PDF analysis error:', err);
      setError(err.message || 'Unable to analyze PDF. Please check backend connection or upload a standard PDF.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleAnalyzeUnified = async ({ pdf = null, images = [], text = '' }) => {
    setIsAnalyzing(true);
    setIsPdfAnalysis(!!pdf);
    setError(null);
    setLastAttempt({ type: 'unified', payload: { pdf, images, text } });

    try {
      const response = await analyzeUnified({ pdf, images, text });
      if (response?.success) {
        setResult(response);
        setActiveView('result');
        loadHistory();
      } else {
        throw new Error(response?.message || 'Failed to complete analysis.');
      }
    } catch (err) {
      console.error('Unified analysis error:', err);
      setError(err.message || 'Unable to complete analysis. Please verify the backend is running at http://127.0.0.1:8000.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleRetry = () => {
    if (!lastAttempt) return;
    if (lastAttempt.type === 'unified') handleAnalyzeUnified(lastAttempt.payload);
    else if (lastAttempt.type === 'text') handleAnalyzeText(lastAttempt.payload);
    else if (lastAttempt.type === 'pdf') handleAnalyzePdf(lastAttempt.payload);
  };

  const handleReset = () => {
    setResult(null);
    setError(null);
    setLastAttempt(null);
    setIsAnalyzing(false);
    setActiveView('dashboard');
  };

  /* ── History item view ──────────────────────────────────────────── */
  const handleViewHistoryItem = async (documentId) => {
    setHistoryDetailLoading(true);
    setSelectedHistoryItem(null);
    setActiveView('history-detail');
    try {
      const data = await fetchHistoryItem(documentId);
      setSelectedHistoryItem(data?.data ?? null);
    } catch (err) {
      console.error('Failed to load history item:', err);
      const fallback = historyItems.find(i => i.id === documentId) ?? null;
      setSelectedHistoryItem(fallback);
    } finally {
      setHistoryDetailLoading(false);
    }
  };

  /* ── Delete from history list ───────────────────────────────────── */
  const handleDeleteFromList = async (documentId) => {
    await deleteHistoryItem(documentId);
    setHistoryItems(prev => prev.filter(i => i.id !== documentId));
  };

  /* ── Delete from detail view ────────────────────────────────────── */
  const handleDeleteFromDetail = async (documentId) => {
    await deleteHistoryItem(documentId);
    setHistoryItems(prev => prev.filter(i => i.id !== documentId));
    setSelectedHistoryItem(null);
    setActiveView('history');
  };

  const handleBackToHistory = () => {
    setActiveView('history');
    setSelectedHistoryItem(null);
  };

  return (
    <div className="app-root">
      {/* Left sidebar */}
      <Sidebar
        activeView={activeView}
        onNavigate={handleNavigate}
        historyCount={historyItems.length}
        backendConnected={backendConnected}
      />

      {/* Main content column */}
      <div className="app-main-col">
        <main className="main-content">
          {/* Error Banner if any */}
          {error && (activeView === 'dashboard' || activeView === 'new') && (
            <ErrorMessage error={error} onRetry={lastAttempt ? handleRetry : null} />
          )}

          {/* ── Loading View ── */}
          {isAnalyzing && (
            <PageTransition key="loading">
              <LoadingView isPdf={isPdfAnalysis} />
            </PageTransition>
          )}

          {/* ── Dashboard View ── */}
          {!isAnalyzing && activeView === 'dashboard' && (
            <PageTransition key="dashboard">
              <DashboardView
                onNewAnalysis={() => handleNavigate('new')}
                historyItems={historyItems}
                onViewHistoryItem={handleViewHistoryItem}
                onViewAllHistory={() => handleNavigate('history')}
                isLoadingHistory={historyLoading}
              />
            </PageTransition>
          )}

          {/* ── New Analysis View ── */}
          {!isAnalyzing && activeView === 'new' && (
            <PageTransition key="new">
              <div className="new-analysis-header">
                <h1 className="page-heading">New Document Analysis</h1>
                <p className="page-subheading">
                  Submit an official circular or document below to run Cortex AI extraction and prioritization.
                </p>
              </div>
              <InputSection
                onAnalyzeUnified={handleAnalyzeUnified}
                onAnalyzeText={handleAnalyzeText}
                onAnalyzePdf={handleAnalyzePdf}
                isAnalyzing={isAnalyzing}
              />
            </PageTransition>
          )}

          {/* ── Result View ── */}
          {!isAnalyzing && activeView === 'result' && result && (
            <PageTransition key="result">
              <ResultsDashboard result={result} onReset={handleReset} />
            </PageTransition>
          )}

          {/* ── History List View ── */}
          {!isAnalyzing && activeView === 'history' && (
            <PageTransition key="history">
              <HistoryView
                historyItems={historyItems}
                isLoading={historyLoading}
                error={historyError}
                onViewItem={handleViewHistoryItem}
                onNewAnalysis={() => handleNavigate('new')}
                onRefresh={loadHistory}
                onDeleteItem={handleDeleteFromList}
                onNavigateToCompare={() => handleNavigate('compare')}
              />
            </PageTransition>
          )}

          {/* ── Decision Compare View ── */}
          {!isAnalyzing && activeView === 'compare' && (
            <PageTransition key="compare">
              <DecisionCompareView
                historyItems={historyItems}
                isLoadingHistory={historyLoading}
                onNewAnalysis={() => handleNavigate('new')}
                onCompare={handleCompare}
                isComparing={isComparing}
                compareError={compareError}
                comparisonResult={comparisonResult}
                onResetComparison={handleResetComparison}
              />
            </PageTransition>
          )}

          {/* ── Deadline Center View ── */}
          {!isAnalyzing && activeView === 'deadlines' && (
            <PageTransition key="deadlines">
              <DeadlineCenterView
                deadlineItems={deadlineItems}
                counts={deadlineCounts}
                isLoading={deadlineLoading}
                error={deadlineError}
                onRefresh={loadDeadlines}
                onUpdateCompletion={handleUpdateDeadlineCompletion}
                onNewAnalysis={() => handleNavigate('new')}
                updatingDocId={updatingDeadlineDocId}
              />
            </PageTransition>
          )}

          {/* ── History Detail View ── */}
          {!isAnalyzing && activeView === 'history-detail' && (
            <PageTransition key="history-detail">
              {historyDetailLoading ? (
                <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
                  <div className="loading-spinner-ring" style={{ margin: '0 auto 1rem' }} />
                  <p style={{ color: 'var(--text-muted)' }}>Loading document details…</p>
                </div>
              ) : (
                <HistoryDetailView
                  item={selectedHistoryItem}
                  onBack={handleBackToHistory}
                  onNewAnalysis={() => handleNavigate('new')}
                  onDeleteItem={handleDeleteFromDetail}
                />
              )}
            </PageTransition>
          )}
        </main>

        {/* App Footer */}
        <footer className="app-footer">
          <div>
            <span className="footer-highlight">DecisionFlow AI</span> • Generic Decision Intelligence Engine
          </div>
          <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', color: '#94a3b8' }}>
            Snowflake Cortex AI (openai-gpt-5) • Database: DECISIONFLOW_DB • Table: DOCUMENTS
          </div>
        </footer>
      </div>
    </div>
  );
}
