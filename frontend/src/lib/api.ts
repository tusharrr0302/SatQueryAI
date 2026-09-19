import type { NormalizedResult } from "./stores";

const API_BASE = "/api";

export async function sendChatQuery(query: string, conversationId?: string) {
  const controller = new AbortController();
  // Planetary Computer COG reads can take several minutes on a cold cache.
  const timeout = window.setTimeout(() => controller.abort(), 300000);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        conversation_id: conversationId || undefined,
      }),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(
        "The live satellite analysis exceeded the 5-minute limit. Try a city-sized AOI or shorter date range.",
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
  if (!resp.ok) {
    let detail = `status ${resp.status}`;
    try {
      const payload = await resp.json();
      detail = payload.detail || detail;
    } catch {
      // Keep the HTTP status when the server did not return JSON.
    }
    throw new Error(detail);
  }
  return await resp.json();
}

export async function fetchDatasets() {
  const resp = await fetch(`${API_BASE}/datasets`);
  if (!resp.ok) throw new Error("Failed to fetch datasets");
  return await resp.json();
}

export async function fetchModels() {
  const resp = await fetch(`${API_BASE}/models`);
  if (!resp.ok) throw new Error("Failed to fetch models");
  return await resp.json();
}

export async function fetchAOIs() {
  const resp = await fetch(`${API_BASE}/aoi`);
  if (!resp.ok) throw new Error("Failed to fetch AOIs");
  return await resp.json();
}

export async function saveInvestigation(data: any) {
  const resp = await fetch(`${API_BASE}/investigations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error("Failed to save investigation");
  return await resp.json();
}

export async function fetchInvestigations() {
  const resp = await fetch(`${API_BASE}/investigations`);
  if (!resp.ok) throw new Error("Failed to fetch investigations");
  return await resp.json();
}

export async function fetchConversations() {
  const resp = await fetch(`${API_BASE}/conversations`);
  if (!resp.ok) throw new Error("Failed to fetch conversations");
  return await resp.json();
}

export function initWebSocket(onEvent: (event: string, data: any) => void) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/chat`;
  let socket: WebSocket | null = null;

  try {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("SatQuery AI WebSocket connected");
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event) {
          onEvent(payload.event, payload.data);
        }
      } catch (err) {
        console.warn("Malformed WS message:", err);
      }
    };

    socket.onerror = (err) => {
      console.warn("WebSocket connection error:", err);
    };

    socket.onclose = () => {
      console.log("WebSocket connection closed");
    };
  } catch (err) {
    console.warn("Could not initialize WebSocket:", err);
  }

  return socket;
}
