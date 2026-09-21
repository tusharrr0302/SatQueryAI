import type { NormalizedResult } from './stores';
import { getApiBaseUrl, getWsBaseUrl } from './config';
import { getAuthToken } from './services/authService';

/**
 * Centralized authenticated fetch wrapper.
 * Automatically resolves endpoint URL and injects Clerk Bearer authorization header.
 */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const apiBase = getApiBaseUrl();
  const url = path.startsWith('http') ? path : `${apiBase}${path.startsWith('/') ? path : `/${path}`}`;

  const headers = new Headers(options.headers || {});

  const token = await getAuthToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return await fetch(url, {
    ...options,
    headers,
  });
}

export async function sendChatQuery(
  query: string,
  conversationId?: string,
  activeAssetId?: string,
  requestId?: string,
  aiMode?: string,
) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 300000);
  let resp: Response;
  try {
    resp = await apiFetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        conversation_id: conversationId || undefined,
        active_asset_id: activeAssetId || undefined,
        request_id: requestId || undefined,
        ai_mode: aiMode || undefined,
      }),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error(
        'The live satellite analysis exceeded the 5-minute limit. Try a city-sized AOI or shorter date range.',
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }

  const payload = await resp.json().catch(() => null);

  if (!resp.ok) {
    if (payload && payload.assistant_message) {
      return payload;
    }
    let detail = `status ${resp.status}`;
    if (payload && payload.detail) {
      detail = payload.detail;
    }
    throw new Error(detail);
  }

  return payload;
}

export async function fetchDatasets() {
  const resp = await apiFetch('/datasets');
  if (!resp.ok) throw new Error('Failed to fetch datasets');
  return await resp.json();
}

export async function fetchModels() {
  const resp = await apiFetch('/models');
  if (!resp.ok) throw new Error('Failed to fetch models');
  return await resp.json();
}

export async function fetchAOIs() {
  const resp = await apiFetch('/aoi');
  if (!resp.ok) throw new Error('Failed to fetch AOIs');
  return await resp.json();
}

export async function fetchCatalogSummary() {
  const resp = await apiFetch('/catalog/summary');
  if (!resp.ok) throw new Error('Failed to fetch catalog summary');
  return await resp.json();
}

export async function fetchCatalogDatasets() {
  const resp = await apiFetch('/catalog/datasets');
  if (!resp.ok) throw new Error('Failed to fetch catalog datasets');
  return await resp.json();
}

export async function fetchCatalogLayers(params?: { search?: string; category?: string; dataset_id?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.search) searchParams.set('search', params.search);
  if (params?.category) searchParams.set('category', params.category);
  if (params?.dataset_id) searchParams.set('dataset_id', params.dataset_id);
  const qStr = searchParams.toString();
  const resp = await apiFetch(`/catalog/layers${qStr ? `?${qStr}` : ''}`);
  if (!resp.ok) throw new Error('Failed to fetch catalog layers');
  return await resp.json();
}

export async function fetchCatalogDatasetDetail(datasetId: string) {
  const resp = await apiFetch(`/catalog/datasets/${encodeURIComponent(datasetId)}`);
  if (!resp.ok) throw new Error(`Failed to fetch dataset detail for ${datasetId}`);
  return await resp.json();
}

export async function validateCustomLayer(spec: any) {
  const resp = await apiFetch('/catalog/custom-layer/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(spec),
  });
  if (!resp.ok) throw new Error('Failed to validate custom layer');
  return await resp.json();
}

export async function saveInvestigation(data: any) {
  const resp = await apiFetch('/investigations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error('Failed to save investigation');
  return await resp.json();
}

export async function fetchInvestigations() {
  const resp = await apiFetch('/investigations');
  if (!resp.ok) throw new Error('Failed to fetch investigations');
  return await resp.json();
}

export async function fetchConversations() {
  const resp = await apiFetch('/conversations');
  if (!resp.ok) throw new Error('Failed to fetch conversations');
  return await resp.json();
}

export async function fetchConversation(id: string) {
  const resp = await apiFetch(`/conversations/${id}`);
  if (!resp.ok) throw new Error(`Failed to fetch conversation ${id}`);
  return await resp.json();
}

export async function deleteConversation(id: string) {
  const resp = await apiFetch(`/conversations/${id}`, {
    method: 'DELETE',
  });
  if (!resp.ok) throw new Error(`Failed to delete conversation ${id}`);
  return await resp.json();
}

export async function fetchDataAssets() {
  const resp = await apiFetch('/data/assets');
  if (!resp.ok) throw new Error('Failed to fetch user data assets');
  return await resp.json();
}

export async function fetchDataAsset(assetId: string) {
  const resp = await apiFetch(`/data/assets/${assetId}`);
  if (!resp.ok) throw new Error(`Failed to fetch data asset ${assetId}`);
  return await resp.json();
}

export async function deleteDataAsset(assetId: string) {
  const resp = await apiFetch(`/data/assets/${assetId}`, {
    method: 'DELETE',
  });
  if (!resp.ok) throw new Error(`Failed to delete asset ${assetId}`);
  return await resp.json();
}

export async function analyzeDataAsset(assetId: string, analysisType: string) {
  const resp = await apiFetch(`/data/assets/${assetId}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ analysis_type: analysisType }),
  });
  if (!resp.ok) throw new Error(`Failed to execute analysis on asset ${assetId}`);
  return await resp.json();
}

export async function initWebSocket(onEvent: (event: string, data: any) => void) {
  let wsUrl = getWsBaseUrl();
  const token = await getAuthToken();
  if (token) {
    const separator = wsUrl.includes('?') ? '&' : '?';
    wsUrl = `${wsUrl}${separator}token=${encodeURIComponent(token)}`;
  }

  let socket: WebSocket | null = null;

  try {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('SatQuery AI WebSocket connected');
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event) {
          onEvent(payload.event, payload.data);
        }
      } catch (err) {
        console.warn('Malformed WS message:', err);
      }
    };

    socket.onerror = (err) => {
      console.warn('WebSocket connection error:', err);
    };

    socket.onclose = () => {
      console.log('WebSocket connection closed');
    };
  } catch (err) {
    console.warn('Could not initialize WebSocket:', err);
  }

  return socket;
}
