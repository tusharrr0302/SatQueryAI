# SatQuery AI Desktop — Professional Earth Observation Intelligence Workstation

SatQuery AI provides an interactive vision-language assistant for multimodal remote sensing and Earth observation (EO) analysis. This repository houses the desktop workstation shell built with **Tauri 2.x**, **Svelte 5**, **Vite**, and **TypeScript**, communicating with the **FastAPI** backend and **ATS (Agentic Tool Synthesis)** pipeline.

---

## 1. Prerequisites

- **Node.js**: v18+ (v20+ recommended)
- **npm**: v9+
- **Rust & Cargo**: v1.77+ (`rustup default stable`)
- **Python**: 3.9+ with virtualenv configured
- **macOS Build Tools**: Xcode Command Line Tools (`xcode-select --install`)

---

## 2. Quickstart Installation

### Frontend & Tauri Shell
```bash
cd frontend
npm install
```

### Backend Services
```bash
cd ../backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Development Workflow

### Step 1: Start FastAPI Backend
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```
Backend API will be active at `http://127.0.0.1:8000` with WebSocket telemetry on `ws://127.0.0.1:8000/ws/chat`.

### Step 2A: Run in Browser Mode (Web Client)
```bash
cd frontend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser. All API requests route automatically via Vite proxy to FastAPI.

### Step 2B: Run in Desktop Mode (Tauri Workstation)
```bash
cd frontend
npm run tauri dev
```
Launches the native macOS window workstation with native file pickers and direct communication to FastAPI.

---

## 4. Production Build

### Building Desktop Binary / App Bundle
```bash
cd frontend
npm run tauri build
```
The compiled macOS `.app` and `.dmg` bundles are placed in:
```
frontend/src-tauri/target/release/bundle/macos/SatQuery AI.app
frontend/src-tauri/target/release/bundle/dmg/SatQuery AI_0.1.0_x64.dmg
```

### Building Web Production Bundle
```bash
cd frontend
npm run build
```
Builds static assets to `frontend/dist/`.

---

## 5. Environment Variables

Create `.env` in the repository root or in `backend/.env`:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Groq API Key for GPT-OSS 120B reasoning | `""` |
| `GROQ_MODEL` | LLM model ID | `openai/gpt-oss-120b` or `llama-3.3-70b-versatile` |
| `MODEL_MODE` | EO execution mode (`live`, `worker`, `mock`) | `live` |
| `PRITHVI_WORKER_URL`| Remote GPU worker URL for Prithvi/GeoChat | `""` |
| `PC_SUBSCRIPTION_KEY`| Microsoft Planetary Computer STAC key | `""` (optional) |
| `VITE_API_BASE_URL` | Frontend API override | `http://127.0.0.1:8000/api` |
| `VITE_WS_BASE_URL` | Frontend WebSocket override | `ws://127.0.0.1:8000/ws/chat` |

---

## 6. Architecture Overview

```
SATQUERY AI
├── Web Client (Svelte 5 + Vite)
├── Desktop Client (Tauri 2.x Shell)
│   ├── Native Dialog Picker (@tauri-apps/plugin-dialog)
│   └── Local File System Ingestion
└── Backend (FastAPI on http://127.0.0.1:8000)
    ├── /api/chat (LangGraph ATS Orchestration)
    ├── /ws/chat (Live Event Broadcasting)
    ├── /api/data/upload (Deterministic GeoTIFF Ingestion & Profile)
    ├── Data Inspector & Rasterio Engine
    ├── Planetary Computer Live Sentinel-2 Pipeline
    └── NormalizedResult
        ├── Raster Viewer
        ├── 3D Surface & ECharts
        └── Cesium 3D Globe (Optional Context)
```

---

## 7. Tauri Permissions & Capabilities

Permissions are declared with principle of least privilege in `src-tauri/capabilities/default.json`:
- `core:default`: Application lifecycle, window events.
- `dialog:default`: Native file picker dialog for opening GeoTIFF/satellite files without arbitrary disk execution.

---

## 8. Troubleshooting

- **WebSocket Connection Refused**:
  Ensure the FastAPI server is running on `http://127.0.0.1:8000`. In Tauri desktop mode, the client connects directly to `ws://127.0.0.1:8000/ws/chat`.
- **Rust build errors**:
  Run `cargo check` inside `frontend/src-tauri` to ensure Xcode command line tools and Rust stable are up to date.
- **Large GeoTIFF memory consumption**:
  SatQuery AI automatically reads downsampled windows and overviews with rasterio; never load full multi-gigabyte rasters directly into client memory.
