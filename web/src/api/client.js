/**
 * RAG Literature Review API Client
 * Encapsulates all backend API calls.
 */

const envApiUrl = import.meta.env.VITE_API_URL?.trim();
const defaultApiUrl = `${window.location.protocol}//${window.location.hostname}:8000`;
const API_BASE_URL = (envApiUrl || defaultApiUrl).replace(/\/+$/, '');

function formatErrorDetail(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && item.msg) {
          const where = Array.isArray(item.loc) ? item.loc.join('.') : '';
          return where ? `${where}: ${item.msg}` : String(item.msg);
        }
        return typeof item === 'string' ? item : JSON.stringify(item);
      })
      .join('; ');
  }

  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string') return detail.message;
    if (typeof detail.msg === 'string') return detail.msg;
    return JSON.stringify(detail);
  }

  return String(detail || '');
}

async function request(path, options = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, options);
    const contentType = response.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      const rawDetail =
        isJson && payload && typeof payload === 'object'
          ? payload.detail ?? payload.message ?? payload.error ?? payload
          : payload;
      const detail = formatErrorDetail(rawDetail);
      throw new Error(detail || `Request failed (${response.status})`);
    }

    return payload;
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `Network request failed to ${API_BASE_URL}. Check backend status, API URL, and CORS origin.`
      );
    }
    throw error;
  }
}

export const api = {
  async healthCheck() {
    return request('/health');
  },

  async getConfig() {
    return request('/api/config');
  },

  async getIndexStatus() {
    return request('/api/index-status');
  },

  async generateReview(params) {
    return request('/api/generate-review', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: params.query,
        detail_level: params.detailLevel || 'standard',
        source_mode: params.sourceMode || 'local_plus_arxiv',
        top_k: params.topK || null,
        arxiv_max_results: params.arxivMaxResults || null,
        subfields: params.subfields || null,
        journal_categories: params.journalCategories || null,
        journal_codes: params.journalCodes || null,
        year_from: params.yearFrom || null,
        year_to: params.yearTo || null,
      }),
    });
  },
};

export default api;
