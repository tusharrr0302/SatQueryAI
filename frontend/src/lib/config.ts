/**
 * SatQuery AI — Centralized Environment & API Configuration
 * Single source of truth for FastAPI endpoints and WebSocket channels.
 */
import { isTauri } from './platform';

const ENV_API_BASE = import.meta.env.VITE_API_BASE_URL;
const ENV_WS_BASE = import.meta.env.VITE_WS_BASE_URL;

export function getApiBaseUrl(): string {
  if (ENV_API_BASE) {
    return ENV_API_BASE.replace(/\/+$/, '');
  }
  if (isTauri()) {
    return 'http://127.0.0.1:8000/api';
  }
  return '/api';
}

export function getWsBaseUrl(): string {
  if (ENV_WS_BASE) {
    return ENV_WS_BASE.replace(/\/+$/, '');
  }
  if (isTauri()) {
    return 'ws://127.0.0.1:8000/ws/chat';
  }
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/chat`;
  }
  return 'ws://127.0.0.1:8000/ws/chat';
}

export function getBackendOrigin(): string {
  if (isTauri()) {
    return 'http://127.0.0.1:8000';
  }
  return '';
}

export function resolveBackendUrl(path: string): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('blob:')) {
    return path;
  }
  const origin = getBackendOrigin();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${origin}${cleanPath}`;
}
