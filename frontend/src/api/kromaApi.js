import { getDemoKey } from './demoKey.js';

/**
 * Reusable fetch helper that configures demo headers, content types,
 * payload conversion, and safe JSON parsing.
 */
async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  
  // Attach demo key header if it exists
  const demoKey = getDemoKey();
  if (demoKey) {
    headers.set('X-Kroma-Demo-Key', demoKey);
  }

  let body = options.body;
  // If the body is a plain object and not FormData, stringify it and set content-type
  if (body && typeof body === 'object' && !(body instanceof FormData)) {
    body = JSON.stringify(body);
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
    body,
  });

  let data = null;
  const contentType = response.headers.get('content-type');

  if (contentType && contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch (e) {
      data = null; // safe fallback on parsing failure
    }
  } else {
    try {
      const text = await response.text();
      data = text ? { detail: text } : null;
    } catch (e) {
      data = null;
    }
  }

  if (!response.ok) {
    const errorMsg = data?.detail || response.statusText || `Request failed with status ${response.status}`;
    const error = new Error(errorMsg);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

// --- API Functions ---

export function getStatus() {
  return apiFetch('/api/status');
}

export function getPublicDemo() {
  return apiFetch('/api/demo');
}

export function sendPublicDemoChat(question) {
  return apiFetch('/api/demo/chat', {
    method: 'POST',
    body: { question },
  });
}

export function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  return apiFetch('/api/upload', {
    method: 'POST',
    body: formData,
  });
}

export function processDocuments() {
  return apiFetch('/api/process', {
    method: 'POST',
  });
}

export function deleteDocument(filename) {
  return apiFetch(`/api/docs/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
}

export function clearLibrary() {
  return apiFetch('/api/library', {
    method: 'DELETE',
  });
}

export function sendChat({ question, history = [], selectedDocs = [] }) {
  return apiFetch('/api/chat', {
    method: 'POST',
    body: {
      question,
      history,
      selected_docs: selectedDocs,
    },
  });
}

export function generateSuggestions({ selectedDocs = [] }) {
  return apiFetch('/api/suggest', {
    method: 'POST',
    body: {
      selected_docs: selectedDocs,
    },
  });
}

export function generateSummary({ selectedDocs = [] }) {
  return apiFetch('/api/summary', {
    method: 'POST',
    body: {
      selected_docs: selectedDocs,
    },
  });
}

export function generateFlashcards({ count = 8, selectedDocs = [] }) {
  return apiFetch('/api/flashcards', {
    method: 'POST',
    body: {
      count,
      selected_docs: selectedDocs,
    },
  });
}

export function generateQuiz({ difficulty = 'medium', count = 8, selectedDocs = [] }) {
  return apiFetch('/api/quiz', {
    method: 'POST',
    body: {
      difficulty,
      count,
      selected_docs: selectedDocs,
    },
  });
}

export function runKnowledgeCopilot({ taskType, audience, request, selectedDocs = [] }) {
  return apiFetch('/api/business-copilot', {
    method: 'POST',
    body: {
      task_type: taskType,
      audience,
      request,
      selected_docs: selectedDocs,
    },
  });
}

export function runKnowledgeAudit({ selectedDocs = [] }) {
  return apiFetch('/api/knowledge-audit', {
    method: 'POST',
    body: {
      selected_docs: selectedDocs,
    },
  });
}
