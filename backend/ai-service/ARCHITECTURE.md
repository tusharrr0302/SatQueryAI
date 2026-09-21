# SatQuery AI — Architecture

## System Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              User                                          │
│           "Show deforestation in Uttarakhand 2020–2024"                    │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │  HTTP POST /api/v1/chat
                               │  { message, aoi, date_range, [images] }
                               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Layer                                      │
│                    app/api/v1/chat.py                                      │
│          (validates request, threads request_id, calls orchestrator)       │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       OrchestratorAgent                                    │
│                  app/orchestrator/agent.py                                 │
│                                                                            │
│  1. Generate request_id (UUID) for log correlation                         │
│  2. Resolve image_url vs image_path (URL takes precedence)                 │
│  3. Build messages [system_prompt + history + user_msg + context]          │
│  4. Send to GPT-OSS with ALL 7 tool definitions                            │
│  5. Detect tool_calls → execute → feed back → repeat                      │
│  6. Return ChatResponse with visualization payload                         │
└──────────┬────────────────────────────────────┬────────────────────────────┘
           │                                    │
           ▼                                    ▼
┌───────────────────────┐          ┌────────────────────────────────────────┐
│       LLMClient       │          │             ToolRegistry               │
│  app/services/        │          │  app/orchestrator/tool_registry.py     │
│    llm_client.py      │          │                                        │
│                       │          │  7 tools:                              │
│  • Groq / OpenAI      │          │  ── Satellite Acquisition ──           │
│  • GPT-OSS-120B       │          │  fetch_sentinel1                       │
│  • Tool calling       │          │  fetch_sentinel2                       │
│  • Provider-agnostic  │          │  fetch_landsat                         │
└──────────┬────────────┘          │  fetch_viirs_modis                     │
           │                       │  ── Specialist Analysis ──             │
           ▼                       │  analyze_image                         │
┌───────────────────────┐          │  detect_change                         │
│     GPT-OSS LLM       │          │  analyze_sar_optical                   │
│  (Groq / OpenAI API)  │          └───────────────────┬────────────────────┘
│                       │                              │
│  Reads 7 tool defs    │                     ┌────────┴──────────┐
│  Selects tool(s)      │                     │                   │
│  Synthesises answer   │                     ▼                   ▼
│                       │     ┌───────────────────────┐  ┌────────────────────┐
│  THIS IS THE ROUTER.  │     │  SatelliteDataService  │  │  RemoteWorkerClient│
│  No keyword matching. │     │  app/services/         │  │  app/services/     │
└───────────────────────┘     │  satellite_data.py     │  │  remote_worker.py  │
                              │                        │  │                    │
                              │  Providers:            │  │  Workers:          │
                              │  CopernicusProvider    │  │  GeoChatWorker     │
                              │  USGSProvider          │  │  ChangeDetection   │
                              │  NASACMRProvider       │  │    Worker          │
                              │  MockSatelliteService  │  │  SAROpticalWorker  │
                              └──────────┬─────────────┘  └────────┬───────────┘
                                         │                          │
                              ┌──────────┴──────┐          ┌───────┴───────────┐
                              │                 │          │                   │
                              ▼                 ▼          ▼                   ▼
                        Copernicus        USGS M2M     GeoChat-7B         VisTA /
                        OData API         JSON API    Kaggle (ngrok)    Prithvi /
                        Sentinel-1/2     Landsat 8/9                   CLASP /
                        NASA CMR                                        TerraFM
                        VIIRS/MODIS                                  Kaggle (ngrok)
```

---

## Component Responsibilities

### FastAPI Layer (`app/api/`)
- HTTP request parsing and validation
- HTTP response formatting (ChatResponse)
- CORS headers
- Request-ID propagation
- No AI/ML logic

### OrchestratorAgent (`app/orchestrator/agent.py`)
- Generate `request_id` (UUID) per turn for log correlation
- Resolve image_url vs image_path (URL takes precedence for remote workers)
- Build conversation context (system prompt + history + user message + geospatial context)
- Drive the GPT-OSS → tool → GPT-OSS loop
- Inject image references into tool arguments
- Maximum `MAX_TOOL_CALL_ROUNDS` safety limit

### LLMClient (`app/services/llm_client.py`)
- Provider-agnostic OpenAI SDK wrapper (Groq, OpenAI, Together, vLLM, Ollama)
- Configuration from environment variables only
- Handles authentication errors, rate limits, connection errors

### ToolRegistry (`app/orchestrator/tool_registry.py`)
- Single source of truth for all 7 available tools
- Converts `BaseTool` instances to OpenAI function-call JSON schema
- Executes tools by name, returns `ToolResult`

### BaseTool (`app/tools/base.py`)
- Abstract interface every tool must implement
- Defines: `name`, `description`, `input_schema`, `execute()`
- `to_openai_function()` converts to OpenAI spec automatically

### Satellite Acquisition Tools (`app/tools/fetch_*.py`)
- `fetch_sentinel1`: Sentinel-1 SAR via Copernicus OData API
- `fetch_sentinel2`: Sentinel-2 optical via Copernicus OData API
- `fetch_landsat`: Landsat 8/9 via USGS M2M JSON API
- `fetch_viirs_modis`: VIIRS/MODIS via NASA CMR REST API
- All return `SatelliteDataset` objects in `ToolResult.artifacts`

### Satellite Data Service (`app/services/satellite_data.py`)
- Facade over three provider implementations
- `CopernicusProvider`: OData API + OAuth2 (Sentinel-1, Sentinel-2)
- `USGSProvider`: M2M JSON API + token auth (Landsat)
- `NASACMRProvider`: Public REST API (VIIRS, MODIS)
- `MockSatelliteDataService`: No real API calls in mock mode
- Module-level singleton: `satellite_service`

### Remote Worker Clients (`app/services/remote_worker.py`)
- `GeoChatWorkerClient`: HTTP → GeoChat Kaggle notebook
- `ChangeDetectionWorkerClient`: HTTP → VisTA/Prithvi Kaggle notebook
- `SAROpticalWorkerClient`: HTTP → CLASP/TerraFM Kaggle notebook
- Each reads its URL from env vars (`GEOCHAT_WORKER_URL`, etc.)
- Mock mode: returns local mock results without any HTTP call
- Real mode: HTTPS POST to ngrok tunnel with `worker_timeout_seconds` timeout

### Specialist Analysis Tools (`app/tools/`)
- Thin glue between registry and remote worker clients
- Input validation (Pydantic)
- Model hint computation (passed to worker; worker makes final decision)
- Error wrapping into `ToolResult`

### Preprocessing Pipeline (`app/services/preprocessing.py`)
- Modular functions: validate_asset → load_raster → handle_crs → clip_to_aoi → resample → select_bands → normalize
- Mock mode: all steps are no-ops (passthrough)
- Real mode: rasterio required (install on Kaggle workers, not locally)

### Schemas (`app/schemas/`)
- `requests.py`: ChatRequest, all tool input models
- `responses.py`: ToolResult, ChatResponse, VisualizationPayload, MapLayer, etc.
- `satellite.py`: SatelliteDataset, SatelliteAsset (normalized satellite data)

---

## The Agentic Loop

```
Step 1: User sends POST /api/v1/chat
        { "message": "Show deforestation in Uttarakhand 2020–2024",
          "aoi": [77.0, 29.5, 81.0, 31.5],
          "date_range": ["2020-01-01", "2024-12-31"] }

Step 2: OrchestratorAgent.run() is called
        Generates request_id = "a1b2c3d4..."
        Resolves images (URLs > paths)
        Builds messages = [system_prompt, user_msg_with_aoi_and_dates]

Step 3: LLMClient.chat(messages, tools=[all 7 tools])
        GPT-OSS receives the full 7-tool catalog

Step 4: GPT-OSS responds with:
        tool_calls = [
          { name: "fetch_sentinel2", args: { bbox: [...], start_date: "2020-01-01", end_date: "2020-03-31", product_type: "S2MSI2A" } },
          { name: "fetch_sentinel2", args: { bbox: [...], start_date: "2024-09-01", end_date: "2024-09-30" } }
        ]

Step 5: Orchestrator executes fetch_sentinel2 TWICE
        → SatelliteDataService.fetch_sentinel2(params_2020) → SatelliteDataset (mock/real)
        → SatelliteDataService.fetch_sentinel2(params_2024) → SatelliteDataset (mock/real)
        Both results appended as tool role messages

Step 6: GPT-OSS sees satellite data results. Responds with:
        tool_calls = [
          { name: "detect_change", args: { query: "Detect deforestation", image_t1: "...", image_t2: "..." } }
        ]

Step 7: Orchestrator calls detect_change
        ChangeDetectionWorkerClient.call() → HTTPS POST to Kaggle worker
        (or local mock result if mock mode)
        Returns ToolResult with VisTA/Prithvi analysis

Step 8: Third LLM call — GPT-OSS synthesises answer from both tool results
        finish_reason = "stop"

Step 9: OrchestratorAgent returns ChatResponse:
        { answer, tool_calls: [trace of 3 calls], model, request_id,
          visualization: { layers, temporal_metadata, ... } }
```

---

## Data Contracts

### ChatRequest (input)
```json
{
  "message": "string (required)",
  "image_path": "string | null",
  "image_url": "string | null",
  "image_path_t2": "string | null",
  "image_url_t2": "string | null",
  "sar_image_path": "string | null",
  "sar_image_url": "string | null",
  "aoi": "[min_lon, min_lat, max_lon, max_lat] | null",
  "date_range": "['YYYY-MM-DD', 'YYYY-MM-DD'] | null",
  "metadata": {},
  "conversation_history": [],
  "request_id": "string | null"
}
```

### ChatResponse (output)
```json
{
  "answer": "GPT-OSS final synthesised answer",
  "tool_calls": [
    {
      "tool_name": "fetch_sentinel2",
      "arguments": { "bbox": [...], "start_date": "...", "end_date": "..." },
      "result": {
        "tool": "fetch_sentinel2",
        "model": "Copernicus-OData",
        "mode": "mock",
        "answer": "Retrieved 1 Sentinel-2 product...",
        "artifacts": [{ "source": "sentinel-2", "product_id": "...", ... }]
      }
    },
    {
      "tool_name": "detect_change",
      "arguments": { "query": "...", "image_t1": "...", "image_t2": "..." },
      "result": {
        "tool": "detect_change",
        "model": "like413/vista",
        "mode": "mock",
        "answer": "[MOCK — VisTA] ..."
      }
    }
  ],
  "artifacts": [...],
  "model": "openai/gpt-oss-120b",
  "request_id": "a1b2c3d4-...",
  "visualization": {
    "layers": [],
    "temporal_metadata": { "before": "2020", "after": "2024" }
  }
}
```

### SatelliteDataset (normalized satellite data)
```json
{
  "source": "sentinel-2",
  "product_id": "S2A_MSIL2A_20240601T053649...",
  "sensor": "optical",
  "platform": "Sentinel-2A",
  "acquisition_time": "2024-06-01T05:36:49Z",
  "bbox": [77.5, 29.0, 80.5, 31.5],
  "crs": "EPSG:4326",
  "bands": ["B02", "B03", "B04", "B08"],
  "assets": [{ "band": "B04", "url": "...", "format": "GeoTIFF", "resolution_m": 10.0 }],
  "cloud_cover_pct": 4.2,
  "mode": "mock"
}
```

---

## Remote Worker API Contract

Each Kaggle notebook must expose:

```
GET  /health
Response: { "status": "ok", "model": "...", "gpu": "T4", "vram_gb": 16 }

POST /tools/analyze_image
Request:  { "image_url": str|null, "query": str }
Response: { "tool": "analyze_image", "status": "success"|"error",
            "model": "MBZUAI/GeoChat-7B", "mode": "real",
            "result": { "answer": str, "confidence": float|null },
            "error": str|null }

POST /tools/detect_change
Request:  { "image_t1_url": str|null, "image_t2_url": str|null,
            "query": str, "model_hint": "vista"|"prithvi"|null }
Response: { ... "result": { "answer": str, "confidence": float|null,
                            "change_mask": dict|null } }

POST /tools/analyze_sar_optical
Request:  { "sar_image_url": str|null, "optical_image_url": str|null,
            "query": str, "model_hint": "clasp"|"terrafm"|null }
Response: { ... "result": { "answer": str, "confidence": float|null } }
```

---

## Extension Points

### Adding a New Tool
1. `app/tools/new_tool.py` — extends `BaseTool`
2. Optionally `app/services/...` — new service if needed
3. `app/orchestrator/tool_registry.py` — `registry.register(NewTool())`
4. `app/orchestrator/prompts.py` — add description to system prompt

### Switching LLM Provider
Change `.env`:
```
LLM_BASE_URL=https://api.together.xyz/v1
LLM_API_KEY=your-together-key
LLM_MODEL=meta-llama/Llama-3-70b-chat-hf
```
No code changes needed.

### Setting Up a Kaggle Worker
1. Deploy the worker notebook to Kaggle (GPU T4 or P100)
2. Run ngrok: `ngrok http 8080`
3. Copy the ngrok URL to `.env`:
   ```
   GEOCHAT_WORKER_URL=https://abc123.ngrok-free.app
   ```
4. Set `MODEL_MODE=real`

### Enabling Real Satellite Data
1. Register at Copernicus (free): https://dataspace.copernicus.eu/
2. Register at USGS (free): https://ers.cr.usgs.gov/register
3. Add credentials to `.env`:
   ```
   COPERNICUS_USER=your@email.com
   COPERNICUS_PASSWORD=yourpassword
   USGS_USERNAME=yourusername
   USGS_TOKEN=your-app-token
   ```
4. Set `MODEL_MODE=real`
5. NASA CMR requires no credentials.
