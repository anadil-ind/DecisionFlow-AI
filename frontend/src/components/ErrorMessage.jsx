import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorMessage({ error, onRetry }) {
  if (!error) return null;

  return (
    <div className="alert-banner" role="alert" style={{ marginBottom: '1.5rem' }}>
      <AlertCircle size={20} className="alert-icon" />
      <div style={{ flex: 1 }}>
        <div className="alert-title">Analysis Failed</div>
        <div className="alert-text">{error}</div>
      </div>
      {onRetry && (
        <button
          type="button"
          className="btn-secondary"
          onClick={onRetry}
          style={{ padding: '0.35rem 0.75rem', fontSize: '0.8125rem' }}
        >
          <RefreshCw size={13} />
          Retry
        </button>
      )}
    </div>
  );
}
