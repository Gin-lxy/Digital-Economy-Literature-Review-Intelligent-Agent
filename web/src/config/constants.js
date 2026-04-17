/**
 * Environment configuration
 */

const envApiUrl = import.meta.env.VITE_API_URL?.trim();
const defaultApiUrl = `${window.location.protocol}//${window.location.hostname}:8000`;

export const API_URL = (envApiUrl || defaultApiUrl).replace(/\/+$/, '');

export const APP_CONFIG = {
  appName: 'RAG Scholar Agent',
  appVersion: '2.0.0',
  maxQueryLength: 500,
  defaultDetailLevel: 'standard',
  defaultSourceMode: 'local_plus_arxiv',
};
