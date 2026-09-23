/**
 * DecisionFlow AI - Backend API Client
 * Connects directly to the FastAPI service at http://127.0.0.1:8000
 * Handles browser session isolation via X-Session-ID header.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const SESSION_STORAGE_KEY = 'decisionflow_session_id';

/**
 * Retrieves the current browser session ID or initializes a new UUID.
 * Preserved across page refreshes and browser restarts in localStorage.
 */
export function getSessionId() {
  if (typeof window === 'undefined') return '';
  let sessionId = localStorage.getItem(SESSION_STORAGE_KEY);
  if (!sessionId || !sessionId.trim()) {
    sessionId = (typeof crypto !== 'undefined' && crypto.randomUUID)
      ? crypto.randomUUID()
      : 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 10);
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }
  return sessionId;
}

/**
 * Returns standard headers including the active X-Session-ID.
 */
function getStandardHeaders(customHeaders = {}) {
  return {
    'Accept': 'application/json',
    'X-Session-ID': getSessionId(),
    ...customHeaders,
  };
}

/**
 * Health check endpoint
 * GET /
 */
export async function checkBackendHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/`, {
      method: 'GET',
      headers: getStandardHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Health check returned status ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Backend health check failed:', error);
    throw error;
  }
}

/**
 * Analyze unstructured text via Snowflake Cortex AI
 * POST /analyze-text
 * Body: { "text": string }
 */
export async function analyzeText(text) {
  if (!text || !text.trim()) {
    throw new Error('Please provide text to analyze.');
  }

  const response = await fetch(`${API_BASE_URL}/analyze-text`, {
    method: 'POST',
    headers: getStandardHeaders({
      'Content-Type': 'application/json',
    }),
    body: JSON.stringify({ text: text.trim() }),
  });

  const data = await response.json();

  if (!response.ok) {
    const errorMsg = data?.detail || data?.message || `Analysis failed with HTTP ${response.status}`;
    throw new Error(errorMsg);
  }

  return data;
}

/**
 * Analyze PDF document via Snowflake Cortex AI
 * POST /analyze-pdf
 * Body: multipart/form-data with "file" field
 */
export async function analyzePdf(file) {
  if (!file) {
    throw new Error('Please select a PDF file to analyze.');
  }

  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/analyze-pdf`, {
    method: 'POST',
    headers: getStandardHeaders(),
    body: formData,
  });

  const data = await response.json();

  if (!response.ok) {
    const errorMsg = data?.detail || data?.message || `PDF analysis failed with HTTP ${response.status}`;
    throw new Error(errorMsg);
  }

  return data;
}

/**
 * Unified multimodal analysis (PDF, Images, Text) via Snowflake Cortex AI
 * POST /analyze
 * Body: multipart/form-data with optional 'pdf', optional 'images' (multiple), optional 'text'
 */
export async function analyzeUnified({ pdf = null, images = [], text = '' }) {
  const formData = new FormData();
  if (pdf) {
    formData.append('pdf', pdf);
  }
  if (Array.isArray(images) && images.length > 0) {
    images.forEach((img) => {
      formData.append('images', img);
    });
  }
  if (text && text.trim()) {
    formData.append('text', text.trim());
  }

  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: getStandardHeaders(),
    body: formData,
  });

  const data = await response.json();

  if (!response.ok) {
    const errorMsg = data?.detail || data?.message || `Analysis failed with HTTP ${response.status}`;
    throw new Error(errorMsg);
  }

  return data;
}

/**
 * Fetch active document history for the current session
 * GET /history
 */
export async function fetchHistory() {
  const response = await fetch(`${API_BASE_URL}/history`, {
    method: 'GET',
    headers: getStandardHeaders(),
  });

  const data = await response.json();

  if (!response.ok) {
    const errorMsg = data?.detail || `Failed to load history (HTTP ${response.status})`;
    throw new Error(errorMsg);
  }

  return data;
}

/**
 * Fetch a single document's full detail from history (scoped to current session)
 * GET /history/{document_id}
 */
export async function fetchHistoryItem(documentId) {
  const response = await fetch(`${API_BASE_URL}/history/${documentId}`, {
    method: 'GET',
    headers: getStandardHeaders(),
  });

  const data = await response.json();

  if (!response.ok) {
    const errorMsg = data?.detail || `Document not found (HTTP ${response.status})`;
    throw new Error(errorMsg);
  }

  return data;
}

/**
 * Permanently delete a document record from Snowflake DOCUMENTS table (scoped to current session)
 * DELETE /history/{document_id}
 */
export async function deleteHistoryItem(documentId) {
  const response = await fetch(`${API_BASE_URL}/history/${documentId}`, {
    method: 'DELETE',
    headers: getStandardHeaders(),
  });

  const data = await response.json();

  if (!response.ok) {
    const errorMsg = data?.detail || `Delete failed (HTTP ${response.status})`;
    throw new Error(errorMsg);
  }

  return data;
}
