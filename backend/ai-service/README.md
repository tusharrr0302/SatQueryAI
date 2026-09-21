# SatQuery AI — AI/ML Service

> Interactive Vision-Language Assistant for Multimodal Remote Sensing Image Analysis through Natural Language Queries

---

## Architecture Overview

```
User Query (natural language)
        ↓
FastAPI  POST /api/v1/chat
        ↓
OrchestratorAgent
        ↓
GPT-OSS (via Groq / OpenAI-compatible API)
    ← receives tool definitions
    → decides which tool to call
        ↓
ToolRegistry.execute(tool_name, args)
        ↓
Specialist Tool (analyze_image / detect_change / analyze_sar_optical)
        ↓
Specialist Model (GeoChat / VisTA / Prithvi / CLOSP / TerraFM)
        ↓
ToolResult → back to GPT-OSS
        ↓
GPT-OSS → final natural-language answer
        ↓
ChatResponse (JSON)
```

**GPT-OSS is the routing decision-maker.** The system does not use keyword matching or hard-coded routing. GPT-OSS reads tool descriptions and autonomously decides which tool(s) to call.

---

## Directory Structure

```
ai-service/
├── app/
│   ├── main.py                    # FastAPI app factory + lifespan startup
│   ├── config.py                  # All config from environment variables
│   │
│   ├── api/v1/
│   │   └── chat.py                # POST /api/v1/chat  +  GET /api/v1/health
│   │
│   ├── orchestrator/
│   │   ├── agent.py               # ★ The agentic tool-calling loop
│   │   ├── prompts.py             # System prompt for GPT-OSS
│   │   └── tool_registry.py       # Tool discovery + OpenAI schema conversion
│   │
│   ├── tools/
│   │   ├── base.py                # BaseTool abstract class
│   │   ├── analyze_image.py       # Tool: VQA via GeoChat-7B
│   │   ├── detect_change.py       # Tool: change detection via VisTA / Prithvi
│   │   └── analyze_sar_optical.py # Tool: SAR+optical via CLOSP / TerraFM
│   │
│   ├── models/
│   │   ├── geochat.py             # GeoChat-7B wrapper (mock + real stub)
│   │   ├── vista.py               # VisTA wrapper
│   │   ├── prithvi.py             # Prithvi-EO-2.0-300M wrapper
│   │   ├── closp.py               # CLOSP wrapper
│   │   └── terrafm.py             # TerraFM wrapper
│   │
│   ├── schemas/
│   │   ├── requests.py            # Pydantic request models
│   │   └── responses.py           # Pydantic response models
│   │
│   └── services/
│       ├── llm_client.py          # Provider-agnostic LLM client
│       └── inference.py           # Image loading + device detection utils
│
├── tests/
│   ├── test_tools.py              # Unit tests for all three tools
│   ├── test_registry.py           # Unit tests for ToolRegistry
│   └── test_orchestrator.py       # Integration tests with mocked LLM
│
├── .env.example                   # Template — copy to .env and fill in keys
├── requirements.txt
├── README.md
└── ARCHITECTURE.md
```

---

## Installation

### Prerequisites
- Python 3.11+
- Virtual environment already at `ai-service/.venv`
- A Groq API key (get one free at https://console.groq.com)

### Steps

```powershell
# 1. Navigate to ai-service
cd SatQuery-AI\ai-service

# 2. Activate the virtual environment
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
copy .env.example .env
# Then edit .env and fill in your LLM_API_KEY
```

---

## Environment Variables

Edit `.env` after copying from `.env.example`:

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | Provider name (groq, openai, etc.) | `groq` |
| `LLM_BASE_URL` | OpenAI-compatible API URL | `https://api.groq.com/openai/v1` |
| `LLM_API_KEY` | **Your API key — never commit this** | *(empty)* |
| `LLM_MODEL` | Model name on the provider | `moonshotai/kimi-k2-instruct` |
| `LLM_MAX_TOKENS` | Max response tokens | `2048` |
| `MODEL_MODE` | `mock` or `real` for specialist models | `mock` |
| `SERVICE_HOST` | FastAPI bind host | `0.0.0.0` |
| `SERVICE_PORT` | FastAPI port | `8000` |
| `LOG_LEVEL` | Log verbosity | `DEBUG` |

**Groq models that support tool calling:**
- `moonshotai/kimi-k2-instruct` (recommended — excellent tool use)
- `llama-3.3-70b-versatile` (fast, reliable)
- `llama-3.1-70b-versatile`

---

## Running the Service

```powershell
# From ai-service/ with .venv activated:

# Option 1 — Python module (recommended)
python -m app.main

# Option 2 — uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Then visit:
#   http://localhost:8000/docs          — interactive Swagger UI
#   http://localhost:8000/api/v1/health — health check
```

---

## Testing

```powershell
# Run all tests (no API key needed — LLM is mocked)
pytest tests/ -v

# Run specific test files
pytest tests/test_tools.py -v
pytest tests/test_registry.py -v
pytest tests/test_orchestrator.py -v
```

---

## Testing Each Tool via curl

```powershell
# Test 1 — analyze_image (GPT-OSS should route here)
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"message": "What is visible in this satellite image?", "image_path": null, "metadata": {}}'

# Test 2 — detect_change (GPT-OSS should route here)
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"message": "Compare these two satellite images and identify what changed between them.", "image_path": "C:/images/before.tif", "image_path_t2": "C:/images/after.tif"}'

# Test 3 — analyze_sar_optical (GPT-OSS should route here)
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"message": "Analyze this SAR image alongside the optical image to detect flood extent.", "image_path": "C:/images/optical.tif", "sar_image_path": "C:/images/sar.tif"}'

# Health check
curl http://localhost:8000/api/v1/health
```

---

## How Tool Calling Works

1. **User sends a message** via `POST /api/v1/chat`
2. **Orchestrator builds the message list** — system prompt + user message + available tool definitions
3. **GPT-OSS receives the request** — it sees the tool list and decides which to call
4. **If GPT-OSS calls a tool:**
   - The orchestrator executes the tool via `ToolRegistry.execute()`
   - The tool calls its specialist model (GeoChat, VisTA, etc.)
   - The result is fed back to GPT-OSS as a `"role": "tool"` message
5. **GPT-OSS synthesises the final answer** using the tool result
6. **The response is returned** with `answer`, `tool_calls` trace, and `artifacts`

The `tool_calls` field in the response lets you verify exactly which tool GPT-OSS chose.

---

## How Mock Mode Works

All specialist models support `MODEL_MODE=mock` (the default).

In mock mode:
- No GPU required
- No model downloads
- Tools return clearly labelled `[MOCK — ModelName]` responses
- The orchestrator, GPT-OSS routing, and HTTP layer are **fully real**

To verify mock mode is active, check the response:
```json
{
  "tool_calls": [{
    "result": {
      "mode": "mock",
      "answer": "[MOCK — GeoChat-7B] ..."
    }
  }]
}
```

To switch to real inference:
```
MODEL_MODE=real
```
And implement `_run_real()` in the relevant model file.

---

## Adding a New Tool

1. Create `app/tools/my_new_tool.py` extending `BaseTool`
2. Create `app/models/my_model.py` for the specialist model
3. Add to `app/orchestrator/tool_registry.py`:
   ```python
   from app.tools.my_new_tool import MyNewTool
   registry.register(MyNewTool())
   ```
4. GPT-OSS automatically learns about the new tool — no other changes needed

---

## What is MOCK vs REAL

| Component | Status |
|---|---|
| FastAPI HTTP layer | ✅ **REAL** |
| GPT-OSS (Groq/OpenAI) tool-calling orchestration | ✅ **REAL** (requires API key) |
| Tool registry & routing | ✅ **REAL** |
| `analyze_image` tool interface | ✅ **REAL** |
| `detect_change` tool interface | ✅ **REAL** |
| `analyze_sar_optical` tool interface | ✅ **REAL** |
| GeoChat-7B inference | 🟡 **MOCK** (real stub documented in geochat.py) |
| VisTA inference | 🟡 **MOCK** |
| Prithvi-EO-2.0 inference | 🟡 **MOCK** |
| CLOSP inference | 🟡 **MOCK** |
| TerraFM inference | 🟡 **MOCK** |
