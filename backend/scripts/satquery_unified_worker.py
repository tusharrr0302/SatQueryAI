#!/usr/bin/env python3
"""SatQuery Unified Specialist Remote Worker (Prithvi + CLOSP + EarthDial)"""

# --- Cell 1 ---
# 1. Environment diagnostics (no installs yet)
import sys
import torch

print("Python:", sys.version)
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print("CUDA runtime:", torch.version.cuda)
print("GPU count:", torch.cuda.device_count())

if not torch.cuda.is_available():
    raise RuntimeError(
        "CUDA is unavailable. In Kaggle: Settings -> Accelerator -> GPU (T4 x2), then restart."
    )

for i in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(i)
    print(f"GPU {i}: {props.name} | {props.total_memory / (1024**3):.1f} GB")

# --- Cell 2 ---
# 2. Kaggle Secrets - credentials come ONLY from Kaggle Secrets / env vars. Never printed.
import os

def _get_secret(name: str, required: bool = False, default: str = "") -> str:
    value = ""
    try:
        from kaggle_secrets import UserSecretsClient
        value = UserSecretsClient().get_secret(name) or ""
    except Exception:
        value = ""
    if not value:
        value = os.environ.get(name, "") or ""
    value = value.strip()
    if required and not value:
        raise RuntimeError(
            f"Kaggle Secret '{name}' is not available. Add it under Add-ons -> Secrets "
            "and attach it to this notebook."
        )
    return value or default


HF_TOKEN = _get_secret("HF_TOKEN")
NGROK_AUTHTOKEN = _get_secret("NGROK_AUTHTOKEN", required=True)
WORKER_NGROK_DOMAIN = (
    _get_secret("WORKER_NGROK_DOMAIN")
    .removeprefix("https://").removeprefix("http://").strip("/")
)
ADMIN_TOKEN = _get_secret("ADMIN_TOKEN")
MODEL_IDLE_TIMEOUT_SECONDS = float(_get_secret("MODEL_IDLE_TIMEOUT_SECONDS", default="60"))

os.environ["HF_TOKEN"] = HF_TOKEN
os.environ["HUGGINGFACE_HUB_TOKEN"] = HF_TOKEN
os.environ["NGROK_AUTHTOKEN"] = NGROK_AUTHTOKEN  # read by ngrok.forward(authtoken_from_env=True)

# Cache model weights once, reuse across restarts within this session's disk.
os.environ.setdefault("HF_HOME", "/kaggle/working/.hf_home")
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", "/kaggle/working/.hf_home/hub")
os.environ.setdefault("TRANSFORMERS_CACHE", "/kaggle/working/.hf_home/hub")

print("HF_TOKEN loaded:", bool(HF_TOKEN))
print("NGROK_AUTHTOKEN loaded:", bool(NGROK_AUTHTOKEN))
print("WORKER_NGROK_DOMAIN configured:", bool(WORKER_NGROK_DOMAIN))
print("ADMIN_TOKEN configured:", bool(ADMIN_TOKEN))
print("MODEL_IDLE_TIMEOUT_SECONDS:", MODEL_IDLE_TIMEOUT_SECONDS)

# ------------------------------------------------------------------------------------
# SECURITY NOTE
# ------------------------------------------------------------------------------------
# The three ORIGINAL source notebooks that were merged into this one each contained a
# hardcoded fallback HF_TOKEN and/or NGROK_AUTHTOKEN string literal (used only if the
# Kaggle Secret lookup failed). Those literals were real-looking tokens pasted directly
# into notebook source. This merged notebook intentionally has NO hardcoded fallback:
# if a secret is missing, the corresponding cell raises instead of silently using a
# leaked value. If those old tokens were ever real, rotate them now (regenerate the HF
# token at huggingface.co/settings/tokens and the ngrok token at dashboard.ngrok.com).

# --- Cell 3 ---
# 3. Consolidated dependency install for the MAIN process (Prithvi + CLOSP + server).
# Do NOT reinstall torch/torchvision/CUDA - keep Kaggle's working GPU stack.
# Versions below reconcile all THREE original notebooks' pins for everything that runs
# in-process. EarthDial's conflicting transformers==4.37.2 pin is handled in its own
# isolated venv (next section) and is deliberately NOT installed here.
import subprocess
import sys


def _run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-4000:])
        print(proc.stderr[-4000:])
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc


def pip_install(*args, no_deps=False):
    cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-q"]
    if no_deps:
        cmd.append("--no-deps")
    cmd.extend(args)
    _run(cmd)


import torch
print("Keeping existing Kaggle torch:", torch.__version__, "| CUDA:", torch.version.cuda)

# NumPy/SciPy/scikit-learn: pinned together to avoid the CLOSP notebook's previously
# observed `ImportError: cannot import name '_center' from 'numpy._core.umath'`
# (a NumPy/SciPy/sklearn binary mismatch), which happens when these are upgraded
# independently.
pip_install("numpy==2.2.6")
pip_install("scipy==1.15.3")
pip_install("scikit-learn==1.6.1")
pip_install("Pillow==11.3.0")
pip_install("timm", no_deps=True)
pip_install("transformers>=4.40,<5.0", "huggingface_hub<1.0", "accelerate", "safetensors",
            "einops", "einops-exts", "sentencepiece")
pip_install("rasterio", "fastapi", "uvicorn", "python-multipart", "requests", "ngrok")

print("Main-process dependencies installed.")

# --- Cell 4 ---
# 4. Clone the official Prithvi-EO-2.0-300M repository (idempotent) and its checkpoint.
from pathlib import Path

PRITHVI_REPO_URL = "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M"
PRITHVI_DIR = Path("/kaggle/working/Prithvi-EO-2.0-300M")
PRITHVI_CHECKPOINT = PRITHVI_DIR / "Prithvi_EO_V2_300M.pt"
PRITHVI_CONFIG = PRITHVI_DIR / "config.json"

if PRITHVI_CONFIG.exists():
    print("Prithvi repository already present:", PRITHVI_DIR)
else:
    _run(["git", "clone", PRITHVI_REPO_URL, str(PRITHVI_DIR)])

pip_install("-r", str(PRITHVI_DIR / "requirements.txt"))

if not PRITHVI_CHECKPOINT.exists():
    raise RuntimeError(f"Checkpoint not found: {PRITHVI_CHECKPOINT}")

checkpoint_gb = PRITHVI_CHECKPOINT.stat().st_size / (1024 ** 3)
print(f"Checkpoint: {PRITHVI_CHECKPOINT.name} ({checkpoint_gb:.2f} GB)")
if checkpoint_gb < 1.0:
    raise RuntimeError(
        "Checkpoint is too small - git-lfs probably did not download the real weights "
        "(expected about 1.24 GB)."
    )

if str(PRITHVI_DIR) not in sys.path:
    sys.path.insert(0, str(PRITHVI_DIR))

# --- Cell 5 ---
# 5. Compatibility patch for the official inference.py (idempotent) - preserved verbatim
# from the working Prithvi notebook. This keeps the official CLI script runnable; the
# worker's own run_prithvi_inference() below never imports inference.py and already uses
# torch.tensor(...) on the correct device, so this patch is defense-in-depth, not required
# for the API path.
PRITHVI_INFERENCE_PY = PRITHVI_DIR / "inference.py"
_text = PRITHVI_INFERENCE_PY.read_text()

_PATCHES = {
    "temporal_coords": (
        "temporal_coords = torch.Tensor(temporal_coords, device=device).unsqueeze(0)",
        "temporal_coords = torch.tensor(\n"
        "    temporal_coords,\n"
        "    dtype=torch.float32,\n"
        "    device=device\n"
        ").unsqueeze(0)",
    ),
    "location_coords": (
        "location_coords = torch.Tensor(location_coords[0], device=device).unsqueeze(0)",
        "location_coords = torch.tensor(\n"
        "    location_coords[0],\n"
        "    dtype=torch.float32,\n"
        "    device=device\n"
        ").unsqueeze(0)",
    ),
}

for _name, (_old, _new) in _PATCHES.items():
    if _old in _text:
        _text = _text.replace(_old, _new)
        print(f"Patched {_name} in inference.py")
    elif _new in _text:
        print(f"{_name}: already patched")
    else:
        print(f"{_name}: legacy line not found (upstream may have changed) - no patch applied")

PRITHVI_INFERENCE_PY.write_text(_text)

# --- Cell 6 ---
# 6. Clone the official CLOSP repository (idempotent).
import shutil

CLOSP_REPO_DIR = Path("/kaggle/working/closp")

if not CLOSP_REPO_DIR.exists():
    _run(["git", "clone", "https://github.com/DarthReca/closp.git", str(CLOSP_REPO_DIR)])
else:
    print("CLOSP repository already present:", CLOSP_REPO_DIR)

if str(CLOSP_REPO_DIR / "src") not in sys.path:
    sys.path.insert(0, str(CLOSP_REPO_DIR / "src"))

print("CLOSP repo:", CLOSP_REPO_DIR, "| files:", [p.name for p in CLOSP_REPO_DIR.iterdir()])

# --- Cell 8 ---
# 7. Isolated EarthDial virtualenv (own transformers/tokenizers/peft pins).
import subprocess as _sp

EARTHDIAL_VENV = Path("/kaggle/working/venv_earthdial")
EARTHDIAL_REPO_DIR = Path("/kaggle/working/EarthDial")
EARTHDIAL_MODEL_ID = "akshaydudhane/EarthDial_4B_MS"
EARTHDIAL_MODEL_DIR = Path("/kaggle/working/checkpoints/EarthDial_4B_MS")
EARTHDIAL_PORT = 9010
EARTHDIAL_SERVER_FILE = Path("/kaggle/working/earthdial_subprocess_server.py")

if not EARTHDIAL_VENV.exists():
    _run([sys.executable, "-m", "venv", "--system-site-packages", str(EARTHDIAL_VENV)])
    print("Created isolated venv:", EARTHDIAL_VENV)
else:
    print("Isolated venv already present:", EARTHDIAL_VENV)

EARTHDIAL_PY = str(EARTHDIAL_VENV / "bin" / "python")

# --system-site-packages lets the venv reuse Kaggle's compiled torch/CUDA build (never
# reinstalled), while these packages are installed venv-local so they do NOT collide with
# the main process's transformers>=4.40.
_run([
    EARTHDIAL_PY, "-m", "pip", "install", "-q", "--no-cache-dir",
    "transformers==4.37.2",
    "tokenizers==0.15.1",
    "huggingface-hub<1.0",
    "sentencepiece==0.1.99",
    "peft==0.4.0",
    "shortuuid", "accelerate", "pydantic", "markdown2", "numpy",
    "scikit-learn>=1.2.2", "requests", "httpx>=0.28.1,<1.0",
    "uvicorn", "fastapi", "einops", "einops-exts", "timm==0.9.12",
    "Pillow", "rasterio", "decord",
])
print("EarthDial venv dependencies installed.")

if not EARTHDIAL_REPO_DIR.exists():
    _run(["git", "clone", "https://github.com/hiyamdebary/EarthDial.git", str(EARTHDIAL_REPO_DIR)])
else:
    print("EarthDial repository already present:", EARTHDIAL_REPO_DIR)

# Ensure earthdial package and subpackages have __init__.py
for pkg_dir in [
    EARTHDIAL_REPO_DIR / "src" / "earthdial",
    EARTHDIAL_REPO_DIR / "src" / "earthdial" / "model",
    EARTHDIAL_REPO_DIR / "src" / "earthdial" / "train",
]:
    if pkg_dir.exists():
        init_f = pkg_dir / "__init__.py"
        if not init_f.exists():
            init_f.touch()

# Add earthdial to isolated venv site-packages via .pth file and pip editable
_run([
    EARTHDIAL_PY, "-c",
    f"import site, pathlib; [pathlib.Path(p).joinpath('earthdial.pth').write_text('{EARTHDIAL_REPO_DIR / 'src'}\n{EARTHDIAL_REPO_DIR}\n') for p in site.getsitepackages() if pathlib.Path(p).is_dir()]"
])
_run([EARTHDIAL_PY, "-m", "pip", "install", "-q", "-e", str(EARTHDIAL_REPO_DIR), "--no-deps"])
print("EarthDial installed in editable mode inside the isolated venv.")

# Verification test
_run([EARTHDIAL_PY, "-c", "import earthdial; print('EarthDial successfully imported:', earthdial.__file__)"])

EARTHDIAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
_run([
    EARTHDIAL_PY, "-c",
    "import os; from huggingface_hub import snapshot_download; "
    f"snapshot_download(repo_id='{EARTHDIAL_MODEL_ID}', repo_type='model', "
    f"local_dir='{EARTHDIAL_MODEL_DIR}', token=os.environ.get('HF_TOKEN') or None)",
])

if not (EARTHDIAL_MODEL_DIR / "config.json").exists():
    raise RuntimeError("EarthDial checkpoint download did not produce config.json.")

print("EarthDial checkpoint ready:", EARTHDIAL_MODEL_DIR)

# --- Cell 9 ---
# 8a. EarthDial subprocess server source (verbatim-preserved model code)
EARTHDIAL_SERVER_CODE = '\nimport gc\nimport os\nimport sys\nimport time\nimport threading\nfrom pathlib import Path\n\nimport numpy as np\nimport rasterio\nimport torch\nfrom fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel\nfrom PIL import Image\n\nREPO_DIR = Path("/kaggle/working/EarthDial")\nMODEL_DIR = Path("/kaggle/working/checkpoints/EarthDial_4B_MS")\n\n# Add both repo root and src to sys.path\nfor p in [\n    REPO_DIR / "src",\n    REPO_DIR,\n    Path("/kaggle/working/earthdial/src"),\n    Path("/kaggle/working/earthdial"),\n    Path("/kaggle/working"),\n]:\n    if p.exists() and str(p) not in sys.path:\n        sys.path.insert(0, str(p))\n\n# Ensure init exists\ninit_file = REPO_DIR / "src" / "earthdial" / "__init__.py"\nif not init_file.exists() and (REPO_DIR / "src" / "earthdial").exists():\n    try:\n        init_file.touch()\n    except Exception:\n        pass\n\nfrom transformers import AutoTokenizer\nfrom earthdial.model.internvl_chat import InternVLChatModel\nfrom earthdial.train.dataset import build_transform\n\nMODEL_ID = "akshaydudhane/EarthDial_4B_MS"\nDEVICE = "cuda:1" if torch.cuda.device_count() > 1 else "cuda:0"\nADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")\n\napp = FastAPI(title="SatQuery EarthDial Subprocess Worker", version="1.0")\n\n# ---- lazy load / unload, mirroring the main process\'s model-manager states ----\nSTATE = "NOT_LOADED"\nSTATE_LOCK = threading.Lock()\nmodel = None\ntokenizer = None\nIMAGE_SIZE = None\n\n\ndef _gpu_mem():\n    if not torch.cuda.is_available():\n        return {}\n    return {\n        "allocated_gb": round(torch.cuda.memory_allocated() / (1024 ** 3), 3),\n        "reserved_gb": round(torch.cuda.memory_reserved() / (1024 ** 3), 3),\n    }\n\n\ndef load_model():\n    global model, tokenizer, IMAGE_SIZE, STATE\n    with STATE_LOCK:\n        if model is not None:\n            return\n        STATE = "LOADING"\n        print("[earthdial-subprocess] loading EarthDial-4B-MS ...", "mem before:", _gpu_mem())\n        try:\n            tokenizer = AutoTokenizer.from_pretrained(\n                str(MODEL_DIR), trust_remote_code=True, use_fast=False,\n            )\n            model = InternVLChatModel.from_pretrained(\n                str(MODEL_DIR),\n                low_cpu_mem_usage=True,\n                torch_dtype=torch.bfloat16,\n                device_map={"": DEVICE},\n            ).eval()\n            IMAGE_SIZE = int(model.config.force_image_size or model.config.vision_config.image_size)\n            STATE = "READY"\n            print("[earthdial-subprocess] loaded. mem after:", _gpu_mem())\n        except Exception:\n            STATE = "ERROR"\n            model = None\n            tokenizer = None\n            raise\n\n\ndef unload_model():\n    global model, tokenizer, IMAGE_SIZE, STATE\n    with STATE_LOCK:\n        if model is None:\n            STATE = "NOT_LOADED"\n            return\n        STATE = "OFFLOADING"\n        print("[earthdial-subprocess] offloading. mem before:", _gpu_mem())\n        try:\n            del model\n        except Exception:\n            pass\n        try:\n            del tokenizer\n        except Exception:\n            pass\n        model = None\n        tokenizer = None\n        IMAGE_SIZE = None\n        gc.collect()\n        torch.cuda.empty_cache()\n        try:\n            torch.cuda.ipc_collect()\n        except Exception:\n            pass\n        STATE = "NOT_LOADED"\n        print("[earthdial-subprocess] offloaded. mem after:", _gpu_mem())\n\n\ndef load_worker_image(path: str) -> Image.Image:\n    p = Path(path)\n    if p.suffix.lower() in {".tif", ".tiff"}:\n        with rasterio.open(p) as src:\n            if src.count != 3:\n                raise ValueError(f"EarthDial worker accepts 3-band GeoTIFF only; received {src.count} bands.")\n            arr = np.transpose(src.read([1, 2, 3]), (1, 2, 0))\n            if np.issubdtype(arr.dtype, np.integer):\n                info = np.iinfo(arr.dtype)\n                arr = (arr.astype(np.float32) - info.min) / max(info.max - info.min, 1)\n            else:\n                arr = arr.astype(np.float32)\n                lo, hi = np.nanpercentile(arr, (2, 98))\n                arr = np.clip((arr - lo) / max(hi - lo, 1e-8), 0, 1)\n            arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0)\n            return Image.fromarray((arr * 255).astype(np.uint8), "RGB")\n    return Image.open(p).convert("RGB")\n\n\ndef format_question(question: str) -> str:\n    question = str(question).strip()\n    if question.startswith("<image>"):\n        return question\n    return "<image>\\n" + question\n\n\ndef earthdial_infer(image_path: str, question: str, max_new_tokens: int = 256) -> str:\n    image = load_worker_image(image_path)\n    transform = build_transform(is_train=False, input_size=IMAGE_SIZE, normalize_type="imagenet")\n    pixel_values = transform(image).unsqueeze(0).to(device=DEVICE, dtype=torch.bfloat16)\n    question = format_question(question)\n    generation_config = {\n        "num_beams": 1,\n        "max_new_tokens": max_new_tokens,\n        "min_new_tokens": 1,\n        "do_sample": False,\n    }\n    with torch.inference_mode():\n        answer = model.chat(\n            tokenizer=tokenizer,\n            pixel_values=pixel_values,\n            question=question,\n            generation_config=generation_config,\n            verbose=False,\n        )\n    return str(answer).strip()\n\n\nclass InferRequest(BaseModel):\n    image_path: str\n    question: str\n    max_new_tokens: int = 256\n\n\n@app.get("/health")\ndef health():\n    return {\n        "status": "ok",\n        "worker": "earthdial-subprocess",\n        "state": STATE,\n        "model_loaded": model is not None,\n        "model": MODEL_ID,\n        "cuda_available": torch.cuda.is_available(),\n        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,\n        "device": DEVICE,\n    }\n\n\n@app.post("/infer")\ndef infer(request: InferRequest):\n    global STATE\n    if not Path(request.image_path).exists():\n        raise HTTPException(status_code=400, detail=f"image_path does not exist: {request.image_path}")\n    try:\n        load_model()\n        STATE = "INFERENCE"\n        t0 = time.time()\n        answer = earthdial_infer(request.image_path, request.question, request.max_new_tokens)\n        dt = time.time() - t0\n        return {"answer": answer, "model": MODEL_ID, "inference_seconds": round(dt, 2)}\n    except HTTPException:\n        raise\n    except Exception as exc:\n        raise HTTPException(status_code=500, detail=f"EarthDial inference failed: {type(exc).__name__}: {exc}")\n    finally:\n        unload_model()\n\n\n@app.post("/admin/unload")\ndef admin_unload(token: str = ""):\n    if ADMIN_TOKEN and token != ADMIN_TOKEN:\n        raise HTTPException(status_code=403, detail="Invalid admin token.")\n    unload_model()\n    return {"status": "unloaded", "state": STATE}\n'

# --- Cell 10 ---
# 8. Write the EarthDial subprocess server file (venv-isolated) - model code preserved
# verbatim from the working `earthdial_kaggle_worker_ready.ipynb` (InternVLChatModel,
# build_transform, model.chat), only wrapped with lazy load/unload + a small HTTP contract.
EARTHDIAL_SERVER_FILE.write_text(EARTHDIAL_SERVER_CODE)
print("EarthDial subprocess server written to:", EARTHDIAL_SERVER_FILE)

# --- Cell 11 ---
# 9. EarthDialSubprocessManager - starts/stops the isolated venv subprocess and proxies
# requests to it. The subprocess is started once (lazily, on first EarthDial request) and
# left running with its OWN model NOT_LOADED between requests; the 4B model itself is
# loaded/unloaded per-request inside the subprocess (see earthdial_subprocess_server.py),
# so normal steady state is: subprocess process alive, GPU memory free.
import socket
import subprocess
import threading
import time

import requests


class EarthDialSubprocessManager:
    def __init__(self, python_bin, server_file, port, cwd="/kaggle/working"):
        self.python_bin = python_bin
        self.server_file = str(server_file)
        self.port = port
        self.cwd = cwd
        self.base_url = f"http://127.0.0.1:{port}"
        self.proc = None
        self._lock = threading.Lock()

    def _port_is_open(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", self.port)) == 0

    def ensure_started(self, timeout=180):
        with self._lock:
            if self.proc is not None and self.proc.poll() is None and self._port_is_open():
                return
            if self.proc is not None and self.proc.poll() is not None:
                print("[earthdial-manager] previous subprocess exited; restarting.")

            env = os.environ.copy()
            existing_pp = env.get("PYTHONPATH", "")
            ed_paths = "/kaggle/working/EarthDial/src:/kaggle/working/EarthDial:/kaggle/working/earthdial/src:/kaggle/working/earthdial"
            env["PYTHONPATH"] = f"{ed_paths}:{existing_pp}" if existing_pp else ed_paths
            self.proc = subprocess.Popen(
                [self.python_bin, "-m", "uvicorn",
                 f"{Path(self.server_file).stem}:app",
                 "--host", "127.0.0.1", "--port", str(self.port)],
                cwd=self.cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            print(f"[earthdial-manager] started subprocess pid={self.proc.pid} on {self.base_url}")

            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.proc.poll() is not None:
                    out = self.proc.stdout.read() if self.proc.stdout else ""
                    raise RuntimeError(
                        f"EarthDial subprocess exited during startup:\n{out[-4000:]}"
                    )
                try:
                    r = requests.get(self.base_url + "/health", timeout=3)
                    if r.status_code == 200:
                        print("[earthdial-manager] subprocess healthy:", r.json())
                        return
                except requests.RequestException:
                    pass
                time.sleep(1)
            raise RuntimeError("EarthDial subprocess did not become healthy in time.")

    def health(self):
        if self.proc is None or self.proc.poll() is not None:
            return {"status": "not_started", "model_loaded": False, "state": "NOT_LOADED"}
        try:
            r = requests.get(self.base_url + "/health", timeout=5)
            return r.json()
        except requests.RequestException as exc:
            return {"status": "unreachable", "error": str(exc)}

    def infer(self, image_path: str, question: str, max_new_tokens: int = 256, timeout=600):
        self.ensure_started()
        r = requests.post(
            self.base_url + "/infer",
            json={"image_path": image_path, "question": question, "max_new_tokens": max_new_tokens},
            timeout=timeout,
        )
        if r.status_code != 200:
            raise RuntimeError(f"EarthDial subprocess error (HTTP {r.status_code}): {r.text[:2000]}")
        return r.json()

    def unload(self):
        if self.proc is None or self.proc.poll() is not None:
            return {"status": "not_started"}
        try:
            r = requests.post(
                self.base_url + "/admin/unload",
                params={"token": ADMIN_TOKEN} if ADMIN_TOKEN else {},
                timeout=30,
            )
            return r.json()
        except requests.RequestException as exc:
            return {"status": "error", "error": str(exc)}

    def stop(self):
        with self._lock:
            if self.proc is not None and self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None


earthdial_subprocess = EarthDialSubprocessManager(
    python_bin=EARTHDIAL_PY,
    server_file=EARTHDIAL_SERVER_FILE,
    port=EARTHDIAL_PORT,
)
print("EarthDial subprocess manager ready (not started yet - lazy).")

# --- Cell 12 ---
# 10. Shared GPU memory utilities used by every specialist's cleanup handler.
import gc

import torch


def gpu_memory_summary():
    if not torch.cuda.is_available():
        return {"cuda_available": False}
    summary = {"cuda_available": True, "devices": []}
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        summary["devices"].append({
            "index": i,
            "name": props.name,
            "total_gb": round(props.total_memory / (1024 ** 3), 2),
            "allocated_gb": round(torch.cuda.memory_allocated(i) / (1024 ** 3), 3),
            "reserved_gb": round(torch.cuda.memory_reserved(i) / (1024 ** 3), 3),
        })
    return summary


def print_gpu(label: str):
    s = gpu_memory_summary()
    if not s.get("cuda_available"):
        print(f"[GPU] {label}: CUDA not available")
        return
    parts = [f"gpu{d['index']}={d['allocated_gb']}GB/{d['total_gb']}GB" for d in s["devices"]]
    print(f"[GPU] {label}: " + ", ".join(parts))


def generic_gpu_cleanup():
    gc.collect()
    torch.cuda.empty_cache()
    try:
        torch.cuda.ipc_collect()
    except Exception:
        pass


print("GPU utilities ready.")
print_gpu("startup")

# --- Cell 14 ---
# 11. Prithvi constants + remote GeoTIFF validation/downloading (preserved verbatim).
import tempfile
import uuid
from urllib.parse import urlparse

from fastapi import HTTPException

PRITHVI_MODEL_NAME = "Prithvi-EO-2.0-300M"
PRITHVI_EXPECTED_FRAMES = 4
PRITHVI_MAX_DOWNLOAD_BYTES = int(os.getenv("PRITHVI_MAX_DOWNLOAD_BYTES", str(512 * 1024 * 1024)))
PRITHVI_CHANGE_AREA_MIN_PERCENT = float(os.getenv("PRITHVI_CHANGE_MIN_PERCENT", "1.0"))


def _validate_image_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Each image URL must be an absolute http(s) URL.")
    return url


def _download_worker_image(url: str, frame_index: int) -> str:
    _validate_image_url(url)
    response = requests.get(
        url, stream=True, timeout=(15, 120),
        headers={"User-Agent": "SatQuery-Unified-Worker/1.0"},
    )
    response.raise_for_status()

    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > PRITHVI_MAX_DOWNLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Remote image exceeds {PRITHVI_MAX_DOWNLOAD_BYTES} byte limit.")

    parsed_path = Path(urlparse(url).path)
    orig_name = parsed_path.name or f"frame_{frame_index}.tif"
    suffix = parsed_path.suffix.lower()
    if suffix not in {".tif", ".tiff"}:
        suffix = ".tif"

    # Preserve the original filename so acquisition dates (.YYYYDDDTHHMMSS. etc) remain in the temp path
    rand_tag = uuid.uuid4().hex[:8]
    tmp_dir = Path(tempfile.gettempdir())
    output_path = tmp_dir / f"satquery_prithvi_t{frame_index}_{rand_tag}_{orig_name}"

    total = 0
    try:
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > PRITHVI_MAX_DOWNLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"Remote image exceeds {PRITHVI_MAX_DOWNLOAD_BYTES} byte limit.")
                f.write(chunk)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return str(output_path)

# --- Cell 15 ---
# 12. Prithvi load / unload (wraps the exact working model-loading cell in a function).
PRITHVI_MODEL = None


def load_prithvi():
    global PRITHVI_MODEL
    if PRITHVI_MODEL is not None:
        return PRITHVI_MODEL

    import json as _json
    from prithvi_mae import PrithviMAE

    with open(PRITHVI_CONFIG, "r") as f:
        full_config = _json.load(f)

    config = full_config["pretrained_cfg"].copy()
    config.update(num_frames=4, in_chans=6)

    m = PrithviMAE(**config)

    checkpoint = torch.load(PRITHVI_CHECKPOINT, map_location="cuda", weights_only=True)
    for key in list(checkpoint.keys()):
        if "pos_embed" in key:
            del checkpoint[key]
    m.load_state_dict(checkpoint, strict=False)

    m = m.cuda()
    m.eval()

    PRITHVI_MODEL = m
    return PRITHVI_MODEL


def unload_prithvi():
    global PRITHVI_MODEL
    if PRITHVI_MODEL is None:
        return
    try:
        PRITHVI_MODEL.to("cpu")
    except Exception:
        pass
    PRITHVI_MODEL = None
    generic_gpu_cleanup()


print("Prithvi load/unload wrappers ready (model not loaded yet).")

# --- Cell 16 ---
# 13. Prithvi inference (official windowed inference path) - preserved verbatim, the
# only change is that it now takes  as a parameter instead of reading a notebook
# global, so the model manager controls its lifetime.
import datetime
import re

import numpy as np
import rasterio
from einops import rearrange


def _extract_prithvi_date(file_path: str, src=None):
    fname = Path(file_path).name

    # 1. Official HLS format: .YYYYDDDTHHMMSS. or YYYYDDDTHHMMSS
    match_hls = re.search(r"(\d{4})(\d{3})T\d{6}", fname)
    if match_hls:
        year = int(match_hls.group(1))
        julian_day = int(match_hls.group(2))
        return [year, julian_day]

    # 2. Julian date: YYYYDDD (e.g. 2018026)
    match_julian = re.search(r"(?:_||\.)(\d{4})(\d{3})(?:_||\.)", fname)
    if match_julian:
        year = int(match_julian.group(1))
        julian_day = int(match_julian.group(2))
        if 1 <= julian_day <= 366:
            return [year, julian_day]

    # 3. Calendar date: YYYYMMDD or YYYY-MM-DD
    match_cal = re.search(r"(?:_||\.)(\d{4})[-_]?(\d{2})[-_]?(\d{2})(?:_||\.)", fname)
    if match_cal:
        year = int(match_cal.group(1))
        month = int(match_cal.group(2))
        day = int(match_cal.group(3))
        try:
            d = datetime.date(year, month, day)
            return [year, d.timetuple().tm_yday]
        except ValueError:
            pass

    # 4. Raster metadata tags
    if src is not None:
        for tag in ("ACQUISITION_DATE", "DATETIME", "TIFFTAG_DATETIME"):
            val = src.tags().get(tag)
            if val:
                m = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", str(val))
                if m:
                    d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    return [d.year, d.timetuple().tm_yday]

    raise ValueError(
        f"Could not extract acquisition date from filename: {file_path}. "
        "Prithvi requires acquisition dates (e.g. 2018026T173609 or 2024-01-01) in filename or metadata."
    )


def run_prithvi_inference(model, data_files, mask_ratio=0.75):
    if len(data_files) != 4:
        raise ValueError(f"Prithvi requires exactly 4 temporal frames, got {len(data_files)}")

    IMG_SIZE = 224
    MEAN = np.array([1087.0, 1342.0, 1433.0, 2734.0, 1958.0, 1363.0], dtype=np.float32)
    STD = np.array([2248.0, 2179.0, 2178.0, 1850.0, 1242.0, 1049.0], dtype=np.float32)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model_device = next(model.parameters()).device
    if model_device != device:
        model.to(device)
    model.eval()

    images = []
    temporal_coords = []
    location_coords = []

    for file_path in data_files:
        with rasterio.open(file_path) as src:
            img = src.read()
            print(f"Loaded {file_path}: shape={img.shape}, crs={src.crs}")
            images.append(img)
            lng, lat = src.lnglat()
            location_coords.append([lng, lat])
            temporal_coords.append(_extract_prithvi_date(file_path, src))

    shapes = [img.shape for img in images]
    if len(set(shapes)) != 1:
        raise ValueError(f"All temporal images must have identical dimensions. Got: {shapes}")

    input_data = np.stack(images, axis=0)
    input_data = np.transpose(input_data, (1, 0, 2, 3))
    original_h = input_data.shape[-2]
    original_w = input_data.shape[-1]

    if input_data.shape[0] != 6:
        raise ValueError(f"Prithvi expects 6 input bands, but received {input_data.shape[0]}")

    input_data = input_data.astype(np.float32)
    input_data = (input_data - MEAN[:, None, None, None]) / STD[:, None, None, None]

    pad_h = (IMG_SIZE - (original_h % IMG_SIZE)) % IMG_SIZE
    pad_w = (IMG_SIZE - (original_w % IMG_SIZE)) % IMG_SIZE
    if pad_h > 0 or pad_w > 0:
        input_data = np.pad(input_data, ((0, 0), (0, 0), (0, pad_h), (0, pad_w)), mode="reflect")

    batch = torch.tensor(input_data, dtype=torch.float32, device="cpu").unsqueeze(0)

    windows = batch.unfold(3, IMG_SIZE, IMG_SIZE).unfold(4, IMG_SIZE, IMG_SIZE)
    h1, w1 = windows.shape[3:5]
    windows = rearrange(windows, "b c t h1 w1 h w -> (b h1 w1) c t h w", h=IMG_SIZE, w=IMG_SIZE)
    print(f"Total windows: {windows.shape[0]}")

    temporal_coords_tensor = torch.tensor(temporal_coords, dtype=torch.float32, device=device).unsqueeze(0)
    location_coords_tensor = torch.tensor(location_coords[0], dtype=torch.float32, device=device).unsqueeze(0)

    model.eval()
    rec_imgs = []
    mask_imgs = []

    with torch.no_grad():
        for index, x in enumerate(windows):
            x = x.unsqueeze(0).to(device)
            _, pred, mask = model(x, temporal_coords_tensor, location_coords_tensor, mask_ratio)

            mask_img = model.unpatchify(
                mask.unsqueeze(-1).repeat(1, 1, pred.shape[-1])
            ).detach().cpu()
            pred_img = model.unpatchify(pred).detach().cpu()

            rec_img = x.cpu().clone()
            rec_img[mask_img == 1] = pred_img[mask_img == 1]
            mask_img = (~(mask_img.to(torch.bool))).to(torch.float32)

            rec_imgs.append(rec_img)
            mask_imgs.append(mask_img)

    rec_imgs = torch.concat(rec_imgs, dim=0)
    mask_imgs = torch.concat(mask_imgs, dim=0)

    rec_imgs = rearrange(rec_imgs, "(b h1 w1) c t h w -> b c t (h1 h) (w1 w)",
                          h=IMG_SIZE, w=IMG_SIZE, b=1, c=6, t=4, h1=h1, w1=w1)
    mask_imgs = rearrange(mask_imgs, "(b h1 w1) c t h w -> b c t (h1 h) (w1 w)",
                           h=IMG_SIZE, w=IMG_SIZE, b=1, c=6, t=4, h1=h1, w1=w1)

    rec_imgs_full = rec_imgs[..., :original_h, :original_w]
    mask_imgs_full = mask_imgs[..., :original_h, :original_w]
    batch_full = batch[..., :original_h, :original_w]

    return {
        "reconstruction": rec_imgs_full,
        "mask": mask_imgs_full,
        "original": batch_full,
        "temporal_coords": temporal_coords_tensor.cpu(),
        "location_coords": location_coords_tensor.cpu(),
    }


def analyze_temporal_change(result, threshold_percentile=90):
    if not 0 < threshold_percentile < 100:
        raise ValueError("threshold_percentile must be between 0 and 100.")

    original = result["original"].float()
    if original.ndim != 5 or original.shape[2] != 4:
        raise ValueError(f"Expected original tensor with shape [B,C,4,H,W], got {tuple(original.shape)}")

    t1 = original[:, :, 0, :, :]
    t4 = original[:, :, 3, :, :]
    difference = torch.abs(t4 - t1)
    change_score = difference.mean(dim=1).squeeze(0).cpu().numpy()

    threshold = np.percentile(change_score, threshold_percentile)
    change_mask = change_score >= threshold
    changed_pixels = int(change_mask.sum())
    total_pixels = int(change_mask.size)
    change_percentage = (changed_pixels / total_pixels) * 100.0

    return {
        "change_score": change_score,
        "change_mask": change_mask,
        "threshold": float(threshold),
        "threshold_percentile": float(threshold_percentile),
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "change_percentage": float(change_percentage),
    }


print("Prithvi inference + change-heuristic functions ready.")

# --- Cell 18 ---
# 14. CLOSP load / unload.
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel

CLOSP_MODEL_ID = "DarthReca/CLOSP-VL"
CLOSP_MODEL = None
CLOSP_SAR_CHANNELS = None
CLOSP_MSI_CHANNELS = None


def load_closp():
    global CLOSP_MODEL, CLOSP_SAR_CHANNELS, CLOSP_MSI_CHANNELS
    if CLOSP_MODEL is not None:
        return CLOSP_MODEL

    m = AutoModel.from_pretrained(
        CLOSP_MODEL_ID,
        trust_remote_code=True,
        token=HF_TOKEN or None,
        low_cpu_mem_usage=True,
        device_map={"": "cuda:0"},
    )
    m.eval()

    CLOSP_MODEL = m
    CLOSP_SAR_CHANNELS = _closp_expected_channels(m, "sar")
    CLOSP_MSI_CHANNELS = _closp_expected_channels(m, "msi")
    return CLOSP_MODEL


def unload_closp():
    global CLOSP_MODEL, CLOSP_SAR_CHANNELS, CLOSP_MSI_CHANNELS
    if CLOSP_MODEL is None:
        return
    try:
        CLOSP_MODEL.to("cpu")
    except Exception:
        pass
    CLOSP_MODEL = None
    CLOSP_SAR_CHANNELS = None
    CLOSP_MSI_CHANNELS = None
    generic_gpu_cleanup()


print("CLOSP load/unload wrappers ready (model not loaded yet).")

# --- Cell 19 ---
# 15. CLOSP GeoTIFF utilities (channel count / input size read from the loaded model,
# preserved verbatim from the working CLOSP notebook).
def read_geotiff(path):
    with rasterio.open(str(path)) as src:
        return src.read().astype(np.float32)


def robust_scale(arr, low=2.0, high=98.0):
    out = np.zeros_like(arr, dtype=np.float32)
    for c in range(arr.shape[0]):
        band = arr[c]
        finite = np.isfinite(band)
        if not finite.any():
            continue
        values = band[finite]
        lo, hi = np.percentile(values, [low, high])
        if hi > lo:
            out[c] = np.clip((band - lo) / (hi - lo), 0, 1)
        else:
            out[c] = np.clip(band, 0, 1)
    return out


def _closp_encoder_for(model, which):
    return getattr(model, "s1_encoder" if which == "sar" else "s2_encoder", None)


def _first_conv_in_channels(module):
    for m in module.modules():
        if isinstance(m, nn.Conv2d):
            return int(m.in_channels)
    return None


def _closp_expected_channels(model, which):
    enc = _closp_encoder_for(model, which)
    n = _first_conv_in_channels(enc) if enc is not None else None
    return n or (2 if which == "sar" else 12)


def _closp_expected_image_size(model, which):
    enc = _closp_encoder_for(model, which)
    size = 224
    try:
        img = getattr(getattr(enc, "patch_embed", None), "img_size", None)
        if img is None:
            cfg = getattr(enc, "pretrained_cfg", None) or getattr(enc, "default_cfg", None) or {}
            inp = cfg.get("input_size")
            img = inp[-2:] if inp else None
        if img is not None:
            size = int(img[0]) if isinstance(img, (tuple, list)) else int(img)
    except Exception:
        pass
    return size


def _load_modality_geotiff(model, path, which, size=None):
    arr = read_geotiff(path)
    expected = _closp_expected_channels(model, which)
    if arr.shape[0] != expected:
        if which == "sar":
            raise ValueError(f"Expected Sentinel-1 VV/VH ({expected} bands) for this CLOSP checkpoint, got {arr.shape[0]} bands.")
        raise ValueError(
            f"This CLOSP checkpoint's Sentinel-2 encoder expects {expected} input channels, got {arr.shape[0]} bands."
        )
    size = size or _closp_expected_image_size(model, which)
    arr = robust_scale(arr)
    x = torch.from_numpy(arr).unsqueeze(0)
    return F.interpolate(x, size=(size, size), mode="bilinear", align_corners=False)


def load_sar_geotiff(model, path, size=None):
    return _load_modality_geotiff(model, path, "sar", size)


def load_msi_geotiff(model, path, size=None):
    return _load_modality_geotiff(model, path, "msi", size)


print("CLOSP GeoTIFF utilities ready.")

# --- Cell 20 ---
# 16. CLOSP real encoder wiring (preserved: only the official CLOSPModel encoder methods
# actually exposed by the loaded model are used - no invented interface).
def _closp_first_tensor(output):
    if isinstance(output, torch.Tensor):
        return output
    if isinstance(output, dict):
        for value in output.values():
            if isinstance(value, torch.Tensor):
                return value
    if isinstance(output, (tuple, list)):
        for value in output:
            if isinstance(value, torch.Tensor):
                return value
    if hasattr(output, "pooler_output") and isinstance(output.pooler_output, torch.Tensor):
        return output.pooler_output
    if hasattr(output, "last_hidden_state") and isinstance(output.last_hidden_state, torch.Tensor):
        return output.last_hidden_state.mean(dim=1)
    raise TypeError(f"Could not extract tensor from {type(output)}")


def _closp_find_encoder_method(model, names):
    for name in names:
        fn = getattr(model, name, None)
        if callable(fn):
            return name, fn
    return None, None


CLOSP_SAR_METHOD_NAMES = ["get_image_features", "encode_sar", "get_sar_features", "sar_features", "encode_image_sar"]
CLOSP_MSI_METHOD_NAMES = ["get_image_features", "encode_msi", "get_msi_features", "msi_features", "encode_image_msi"]
CLOSP_TEXT_METHOD_NAMES = ["get_text_features", "encode_text", "text_features"]


@torch.inference_mode()
def closp_encode_sar(model, x):
    name, fn = _closp_find_encoder_method(model, CLOSP_SAR_METHOD_NAMES)
    if fn is None:
        raise RuntimeError("No explicit SAR encoder method was found in the loaded CLOSP model.")
    device = next(model.parameters()).device
    output = fn(x.to(device))
    return F.normalize(_closp_first_tensor(output), dim=-1)


@torch.inference_mode()
def closp_encode_msi(model, x):
    name, fn = _closp_find_encoder_method(model, CLOSP_MSI_METHOD_NAMES)
    if fn is None:
        raise RuntimeError("No explicit MSI encoder method was found in the loaded CLOSP model.")
    device = next(model.parameters()).device
    output = fn(x.to(device))
    return F.normalize(_closp_first_tensor(output), dim=-1)


@torch.inference_mode()
def closp_encode_text(model, text):
    name, fn = _closp_find_encoder_method(model, CLOSP_TEXT_METHOD_NAMES)
    tokenize = getattr(model, "tokenize_text", None)
    if fn is None or not callable(tokenize):
        raise RuntimeError("The loaded CLOSP model exposes no text encoder (get_text_features + tokenize_text).")
    device = next(model.parameters()).device
    tok = tokenize(text)
    output = fn(tok["input_ids"].to(device), tok["attention_mask"].to(device))
    return F.normalize(_closp_first_tensor(output), dim=-1)


def run_closp_modality(model, path, modality):
    modality = modality.lower().strip()
    if modality == "sar":
        tensor = load_sar_geotiff(model, path)
        embedding = closp_encode_sar(model, tensor)
    elif modality in {"msi", "optical"}:
        modality = "msi"
        tensor = load_msi_geotiff(model, path)
        embedding = closp_encode_msi(model, tensor)
    else:
        raise ValueError("modality must be 'sar' or 'msi'")
    vector = embedding[0].detach().float().cpu().tolist()
    return modality, vector


print("CLOSP encoder functions ready.")

# --- Cell 22 ---
# 17. SpecialistModelManager: lazy loading, model-specific cleanup, GPU lock, states.
import asyncio
import time

VALID_STATES = {"NOT_LOADED", "LOADING", "READY", "INFERENCE", "OFFLOADING", "ERROR"}


def unload_prithvi_handler():
    unload_prithvi()


def unload_closp_handler():
    unload_closp()


def unload_earthdial_handler():
    # EarthDial's model lives in a separate process; its own /infer handler already
    # unloads after every call, and /admin/unload force-unloads on demand. There is no
    # in-process object to call .cpu() on here (deliberately - see the markdown note
    # about Accelerate dispatch above).
    earthdial_subprocess.unload()


MODEL_CLEANUP_HANDLERS = {
    "prithvi": unload_prithvi_handler,
    "closp": unload_closp_handler,
    "earthdial": unload_earthdial_handler,
}


class SpecialistModelManager:
    def __init__(self):
        self.state = {name: "NOT_LOADED" for name in MODEL_CLEANUP_HANDLERS}
        self.active_model = None
        self.last_used = {name: None for name in MODEL_CLEANUP_HANDLERS}
        self.lock = asyncio.Lock()
        self._idle_task = None

    def _set_state(self, specialist, state):
        assert state in VALID_STATES, f"invalid state {state}"
        self.state[specialist] = state

    def get_model(self, specialist):
        # Ensure the specialist's model is loaded in-process and return it.
        # Not used for earthdial (proxied via subprocess instead).
        self._set_state(specialist, "LOADING")
        try:
            if specialist == "prithvi":
                model = load_prithvi()
            elif specialist == "closp":
                model = load_closp()
            else:
                raise ValueError(f"get_model() does not apply to '{specialist}' (subprocess-backed)")
            self._set_state(specialist, "READY")
            self.active_model = specialist
            self.last_used[specialist] = time.time()
            return model
        except Exception:
            self._set_state(specialist, "ERROR")
            raise

    def unload_model(self, specialist):
        try:
            MODEL_CLEANUP_HANDLERS[specialist]()
        finally:
            self._set_state(specialist, "NOT_LOADED")
            if self.active_model == specialist:
                self.active_model = None

    def unload_all(self):
        for specialist in MODEL_CLEANUP_HANDLERS:
            try:
                self.unload_model(specialist)
            except Exception as exc:
                print(f"[manager] unload_all: failed to unload {specialist}: {exc}")

    def mark_inference(self, specialist):
        self._set_state(specialist, "INFERENCE")

    def get_status(self):
        earthdial_health = earthdial_subprocess.health()
        loaded_models = [
            name for name in ("prithvi", "closp")
            if self.state.get(name) in {"READY", "INFERENCE"}
        ]
        if earthdial_health.get("model_loaded"):
            loaded_models.append("earthdial")

        return {
            "active_model": self.active_model,
            "loaded_models": loaded_models,
            "state": {
                "prithvi": self.state["prithvi"],
                "closp": self.state["closp"],
                "earthdial": earthdial_health.get("state", "NOT_LOADED"),
            },
        }


MODEL_MANAGER = SpecialistModelManager()
GPU_LOCK = MODEL_MANAGER.lock
print("SpecialistModelManager ready. GPU_LOCK created.")

# --- Cell 23 ---
# 18. Request logging helper - prints the structured before/after block for every
# inference request, for both in-process (Prithvi/CLOSP) and subprocess-backed (EarthDial)
# specialists.
import uuid


class RequestLog:
    def __init__(self, specialist: str):
        self.specialist = specialist.upper()
        self.request_id = uuid.uuid4().hex[:12]

    def __enter__(self):
        print("=" * 60)
        print("SATQUERY WORKER REQUEST")
        print("=" * 60)
        print(f"Specialist: {self.specialist}")
        print(f"Request ID: {self.request_id}")
        print_gpu("before")
        return self

    def step(self, message: str):
        print(message)

    def __exit__(self, exc_type, exc, tb):
        print_gpu("after")
        if exc_type is not None:
            print(f"Request FAILED: {exc_type.__name__}: {exc}")
        print("Request complete.")
        print("=" * 60)
        return False


print("Request logging helper ready.")

# --- Cell 25 ---
# 19. FastAPI schemas.
from typing import Optional, Dict, Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class MultitemporalRequest(BaseModel):
    image_t1: str
    image_t2: str
    image_t3: Optional[str] = None
    image_t4: Optional[str] = None
    query: Optional[str] = ""
    metadata_t1: Optional[Dict[str, Any]] = None
    metadata_t2: Optional[Dict[str, Any]] = None
    metadata_t3: Optional[Dict[str, Any]] = None
    metadata_t4: Optional[Dict[str, Any]] = None
    analysis_mode: Optional[str] = None


class SarOpticalRequest(BaseModel):
    sar_image_url: Optional[str] = None
    optical_image_url: Optional[str] = None
    query: Optional[str] = None
    model_hint: Optional[str] = None


class AnalyzeImageRequest(BaseModel):
    image_url: str
    query: Optional[str] = ""
    question: Optional[str] = None
    max_new_tokens: Optional[int] = 256


print("Pydantic request schemas ready.")

# --- Cell 26 ---
# 20. Unified FastAPI app + /health, /models, /gpu.
SERVER_PORT = 9000
SERVER_HOST = "0.0.0.0"
LOCAL_BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"

app = FastAPI(title="SatQuery Unified Remote Worker", version="1.0.0")

AVAILABLE_MODELS = ["prithvi", "closp", "earthdial"]


@app.get("/health")
def health():
    """
    Canonical ATS Health Endpoint (Section 8 compliant).
    Reports live system health and specialist model readiness.
    """
    cuda_available = torch.cuda.is_available()
    status = MODEL_MANAGER.get_status()
    earthdial_health = earthdial_subprocess.health()

    def _model_status(name: str):
        if name == "prithvi":
            st = status["state"].get("prithvi", "NOT_LOADED")
            if st in {"READY", "INFERENCE"}:
                return "ready"
            elif st == "ERROR":
                return "error"
            elif st == "LOADING":
                return "loading"
            return "ready" if PRITHVI_MODEL is not None else "not_loaded"
        elif name == "closp":
            st = status["state"].get("closp", "NOT_LOADED")
            if st in {"READY", "INFERENCE"}:
                return "ready"
            elif st == "ERROR":
                return "error"
            elif st == "LOADING":
                return "loading"
            return "ready" if CLOSP_MODEL is not None else "not_loaded"
        elif name == "earthdial":
            if earthdial_health.get("model_loaded"):
                return "ready"
            elif earthdial_health.get("state") == "ERROR":
                return "error"
            elif earthdial_health.get("state") == "LOADING":
                return "loading"
            return "not_loaded"
        return "not_loaded"

    models_dict = {
        "prithvi-eo-2.0": _model_status("prithvi"),
        "closp": _model_status("closp"),
        "earthdial-4b-ms": _model_status("earthdial"),
    }

    payload = {
        "status": "ok",
        "worker": "satquery-unified",
        "cuda_available": cuda_available,
        "gpu": torch.cuda.get_device_name(0) if cuda_available else None,
        "active_model": status["active_model"],
        "loaded_models": status["loaded_models"],
        "available_models": AVAILABLE_MODELS,
        "models": models_dict,
    }
    return JSONResponse(status_code=200, content=payload)


@app.get("/models")
def models():
    status = MODEL_MANAGER.get_status()
    earthdial_health = earthdial_subprocess.health()

    def _device(name):
        if name == "prithvi":
            return str(next(PRITHVI_MODEL.parameters()).device) if PRITHVI_MODEL is not None else None
        if name == "closp":
            return str(next(CLOSP_MODEL.parameters()).device) if CLOSP_MODEL is not None else None
        if name == "earthdial":
            return earthdial_health.get("device") if earthdial_health.get("model_loaded") else None
        return None

    return {
        "prithvi": {"loaded": status["state"]["prithvi"] in {"READY", "INFERENCE"}, "device": _device("prithvi")},
        "closp": {"loaded": status["state"]["closp"] in {"READY", "INFERENCE"}, "device": _device("closp")},
        "earthdial": {"loaded": bool(earthdial_health.get("model_loaded")), "device": _device("earthdial")},
    }


@app.get("/gpu")
def gpu():
    summary = gpu_memory_summary()
    status = MODEL_MANAGER.get_status()
    return {
        "cuda_available": summary.get("cuda_available", False),
        "gpu_count": len(summary.get("devices", [])),
        "gpus": summary.get("devices", []),
        "active_model": status["active_model"],
    }


print("FastAPI app + /health, /models, /gpu ready.")

# --- Cell 27 ---
# 21. POST /tools/analyze_multitemporal (Prithvi) - same contract as the original worker.
from fastapi import HTTPException


@app.post("/tools/analyze_multitemporal")
async def analyze_multitemporal(request: MultitemporalRequest):
    image_urls = [request.image_t1, request.image_t2, request.image_t3, request.image_t4]
    if any(not url for url in image_urls):
        raise HTTPException(status_code=400, detail="Prithvi requires exactly 4 temporal image URLs.")

    local_files = []
    async with GPU_LOCK:
        with RequestLog("prithvi") as log:
            try:
                log.step(f"Model state before: {MODEL_MANAGER.state['prithvi']}")
                for index, url in enumerate(image_urls, start=1):
                    local_files.append(_download_worker_image(url, index))

                log.step("Loading PRITHVI...")
                try:
                    model = MODEL_MANAGER.get_model("prithvi")
                except Exception as load_exc:
                    raise HTTPException(
                        status_code=503,
                        detail={"error": "MODEL_LOAD_FAILED", "model": "prithvi",
                                "message": f"{type(load_exc).__name__}: {load_exc}", "request_id": log.request_id},
                    ) from load_exc
                log.step("PRITHVI loaded.")
                print_gpu("after loading")

                MODEL_MANAGER.mark_inference("prithvi")
                log.step("Running inference...")
                prithvi_result = run_prithvi_inference(model, local_files)
                change_result = analyze_temporal_change(prithvi_result)
                log.step("Inference complete.")

                change_percentage = float(change_result["change_percentage"])
                change_detected = change_percentage >= PRITHVI_CHANGE_AREA_MIN_PERCENT

                return {
                    "tool": "analyze_multitemporal",
                    "status": "success",
                    "model": PRITHVI_MODEL_NAME,
                    "mode": "real",
                    "result": {
                        "answer": None,
                        "change_detected": change_detected,
                        "confidence": None,
                        "change_percentage": round(change_percentage, 4),
                        "temporal_frames": PRITHVI_EXPECTED_FRAMES,
                        "analysis_method": "temporal_spectral_difference_heuristic",
                        "change_analysis": {
                            "threshold": change_result["threshold"],
                            "threshold_percentile": change_result["threshold_percentile"],
                            "changed_pixels": change_result["changed_pixels"],
                            "total_pixels": change_result["total_pixels"],
                            "minimum_change_area_percent": PRITHVI_CHANGE_AREA_MIN_PERCENT,
                        },
                        "model_output": {
                            "original_shape": list(prithvi_result["original"].shape),
                            "reconstruction_shape": list(prithvi_result["reconstruction"].shape),
                            "mask_shape": list(prithvi_result["mask"].shape),
                            "temporal_coordinates": prithvi_result["temporal_coords"].tolist(),
                            "location_coordinates": prithvi_result["location_coords"].tolist(),
                        },
                    },
                }
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail={"error": "INFERENCE_FAILED", "model": "prithvi",
                            "message": f"{type(exc).__name__}: {exc}", "request_id": log.request_id},
                ) from exc
            finally:
                log.step("Offloading PRITHVI...")
                try:
                    MODEL_MANAGER.unload_model("prithvi")
                except Exception as cleanup_exc:
                    print(f"WARNING: prithvi cleanup failed: {cleanup_exc}")
                for local_file in local_files:
                    try:
                        Path(local_file).unlink(missing_ok=True)
                    except Exception:
                        pass


print("POST /tools/analyze_multitemporal ready.")

# --- Cell 28 ---
# 22. POST /tools/analyze_sar_optical (CLOSP) - same contract as the original worker.
@app.post("/tools/analyze_sar_optical")
async def analyze_sar_optical(request: SarOpticalRequest):
    if not request.sar_image_url and not request.optical_image_url:
        raise HTTPException(status_code=400, detail="Provide sar_image_url and/or optical_image_url.")

    tmp_paths = []
    async with GPU_LOCK:
        with RequestLog("closp") as log:
            result = {
                "tool": "analyze_sar_optical",
                "status": "success",
                "model": CLOSP_MODEL_ID,
                "query": request.query,
                "answer": None,
                "analysis_method": "CLOSP_aligned_embeddings",
                "sar": None,
                "optical": None,
            }
            try:
                log.step(f"Model state before: {MODEL_MANAGER.state['closp']}")
                log.step("Loading CLOSP...")
                try:
                    model = MODEL_MANAGER.get_model("closp")
                except Exception as load_exc:
                    raise HTTPException(
                        status_code=503,
                        detail={"error": "MODEL_LOAD_FAILED", "model": "closp",
                                "message": f"{type(load_exc).__name__}: {load_exc}", "request_id": log.request_id},
                    ) from load_exc
                log.step("CLOSP loaded.")
                print_gpu("after loading")

                MODEL_MANAGER.mark_inference("closp")
                log.step("Running inference...")

                if request.sar_image_url:
                    sar_path = _download_url_closp(request.sar_image_url)
                    tmp_paths.append(sar_path)
                    _, sar_vector = run_closp_modality(model, sar_path, "sar")
                    result["sar"] = {"embedding_dimension": len(sar_vector), "embedding": sar_vector}

                if request.optical_image_url:
                    optical_path = _download_url_closp(request.optical_image_url)
                    tmp_paths.append(optical_path)
                    _, optical_vector = run_closp_modality(model, optical_path, "msi")
                    result["optical"] = {"embedding_dimension": len(optical_vector), "embedding": optical_vector}

                if result["sar"] and result["optical"]:
                    sar_t = torch.tensor(result["sar"]["embedding"]).unsqueeze(0)
                    opt_t = torch.tensor(result["optical"]["embedding"]).unsqueeze(0)
                    result["cross_modal_similarity"] = float(F.cosine_similarity(sar_t, opt_t).item())

                log.step("Inference complete.")
                return result
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail={"error": "INFERENCE_FAILED", "model": "closp",
                            "message": f"{type(exc).__name__}: {exc}", "request_id": log.request_id},
                ) from exc
            finally:
                log.step("Offloading CLOSP...")
                try:
                    MODEL_MANAGER.unload_model("closp")
                except Exception as cleanup_exc:
                    print(f"WARNING: closp cleanup failed: {cleanup_exc}")
                for p in tmp_paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass


def _download_url_closp(url: str, suffix=".tif"):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    content_length = r.headers.get("content-length")
    max_bytes = int(os.getenv("CLOSP_MAX_DOWNLOAD_BYTES", str(512 * 1024 * 1024)))
    if content_length and int(content_length) > max_bytes:
        raise ValueError("Remote image exceeds CLOSP_MAX_DOWNLOAD_BYTES.")
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    total = 0
    try:
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("Remote image exceeds CLOSP_MAX_DOWNLOAD_BYTES.")
                f.write(chunk)
        return path
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise


print("POST /tools/analyze_sar_optical ready.")

@app.post("/analyze")
async def analyze_alias(request: SarOpticalRequest):
    """Backward-compatible alias for /tools/analyze_sar_optical."""
    return analyze_sar_optical(request)

# Startup diagnostic: print all registered routes (Task 4)
print("\n--- REGISTERED WORKER ROUTES ---")
for route in app.routes:
    print(getattr(route, "methods", None), getattr(route, "path", None))
print("--------------------------------\n")

# --- Cell 29 ---
# 23. POST /tools/analyze_image (EarthDial, proxied to the isolated subprocess).
# The GPU_LOCK is held for the entire proxied HTTP round trip, so Prithvi/CLOSP cannot
# try to touch the GPU while EarthDial's subprocess is loaded, and vice versa.
@app.post("/tools/analyze_image")
async def analyze_image(request: AnalyzeImageRequest):
    local_path = None
    async with GPU_LOCK:
        with RequestLog("earthdial") as log:
            try:
                log.step("Downloading image...")
                local_path = _download_worker_image(request.image_url, 0)

                log.step("Loading EARTHDIAL (isolated subprocess)...")
                try:
                    earthdial_subprocess.ensure_started()
                except Exception as load_exc:
                    raise HTTPException(
                        status_code=503,
                        detail={"error": "MODEL_LOAD_FAILED", "model": "earthdial",
                                "message": f"{type(load_exc).__name__}: {load_exc}", "request_id": log.request_id},
                    ) from load_exc
                log.step("EARTHDIAL subprocess ready.")
                print_gpu("after loading")

                log.step("Running inference...")
                question = request.query or "Describe this image and identify the major objects and land-cover features."
                infer_result = earthdial_subprocess.infer(
                    image_path=local_path, question=question, max_new_tokens=request.max_new_tokens,
                )
                log.step("Inference complete.")

                return {
                    "tool": "analyze_image",
                    "status": "success",
                    "model": infer_result.get("model", "akshaydudhane/EarthDial_4B_MS"),
                    "mode": "real",
                    "result": {
                        "answer": infer_result.get("answer"),
                        "confidence": None,
                        "query": request.query,
                        "inference_seconds": infer_result.get("inference_seconds"),
                    },
                }
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail={"error": "INFERENCE_FAILED", "model": "earthdial",
                            "message": f"{type(exc).__name__}: {exc}", "request_id": log.request_id},
                ) from exc
            finally:
                log.step("Offloading EARTHDIAL...")
                try:
                    earthdial_subprocess.unload()
                except Exception as cleanup_exc:
                    print(f"WARNING: earthdial cleanup failed: {cleanup_exc}")
                if local_path:
                    try:
                        Path(local_path).unlink(missing_ok=True)
                    except Exception:
                        pass


print("POST /tools/analyze_image ready.")

# --- Cell 30 ---
# 24. POST /admin/unload - force-unload every specialist and free GPU memory.
@app.post("/admin/unload")
async def admin_unload(token: str = ""):
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token.")
    async with GPU_LOCK:
        print_gpu("before admin unload")
        MODEL_MANAGER.unload_all()
        print_gpu("after admin unload")
    return {"status": "ok", "loaded_models": MODEL_MANAGER.get_status()["loaded_models"]}


print("POST /admin/unload ready.")

# --- Cell 32 ---
# 25. Start FastAPI/Uvicorn on 0.0.0.0:9000 in a daemon thread (exactly one server).
import os
import signal
import socket
import subprocess
import sys
import threading

import uvicorn

# Kill any stale uvicorn / server processes on ports 9000, 8000, 8080
for cmd in [
    "pkill -f 'uvicorn'",
    "fuser -k 9000/tcp",
    "fuser -k 8000/tcp",
    "fuser -k 8080/tcp",
]:
    subprocess.run(cmd, shell=True, capture_output=True)

def _port_accepts_connections(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0

_existing_thread = globals().get("WORKER_SERVER_THREAD")

if _existing_thread is not None and _existing_thread.is_alive():
    print("FastAPI was already started by this notebook - reusing existing thread.")
else:
    WORKER_SERVER = uvicorn.Server(
        uvicorn.Config(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")
    )
    WORKER_SERVER_THREAD = threading.Thread(target=WORKER_SERVER.run, daemon=True, name="satquery-fastapi")
    WORKER_SERVER_THREAD.start()
    print(f"Starting SatQuery unified FastAPI on {SERVER_HOST}:{SERVER_PORT} ...")

# Print route diagnostic table (Section 1 compliant)
print("\n=== REGISTERED FASTAPI ROUTES ===")
print(f"{'METHOD':<8} {'PATH':<35} {'HANDLER':<25}")
print("-" * 70)
for r in app.routes:
    methods = ", ".join(sorted(getattr(r, 'methods', []) or []))
    path = getattr(r, 'path', '')
    endpoint = getattr(r, 'endpoint', None)
    handler_name = getattr(endpoint, '__name__', str(endpoint))
    if methods:
        print(f"{methods:<8} {path:<35} {handler_name:<25}")
print("-" * 70)
print(f"PID: {os.getpid()} | PORT: {SERVER_PORT} | COMMAND: uvicorn app:app --port {SERVER_PORT}")

# --- Cell 33 ---
# 26. Wait until the local server answers, then verify /health (no models loaded yet).
import time

local_session = requests.Session()
local_session.trust_env = False

_deadline = time.time() + 90
_last_error = None
_probe = None

while time.time() < _deadline:
    if not WORKER_SERVER_THREAD.is_alive():
        raise RuntimeError("The FastAPI/Uvicorn thread exited during startup. Do NOT start ngrok.")
    try:
        _probe = local_session.get(LOCAL_BASE_URL + "/health", timeout=3)
        break
    except requests.RequestException as exc:
        _last_error = exc
        time.sleep(1)

if _probe is None:
    raise RuntimeError(f"FastAPI did not answer on {LOCAL_BASE_URL} within 90 s. Last error: {_last_error}")

print(f"Uvicorn is answering on {LOCAL_BASE_URL} (HTTP {_probe.status_code}).")
print(_probe.json())

# --- Cell 34 ---
# 27. Start exactly ONE ngrok tunnel (official ngrok Python SDK).
import inspect

import ngrok

NGROK_UPSTREAM_ADDR = f"127.0.0.1:{SERVER_PORT}"
_existing_listener = globals().get("WORKER_NGROK_LISTENER")

if _existing_listener is not None:
    print("An ngrok listener already exists in this session - reusing it (no second tunnel).")
    listener = _existing_listener
else:
    _forward_kwargs = {"authtoken_from_env": True}
    if WORKER_NGROK_DOMAIN:
        _forward_kwargs["domain"] = WORKER_NGROK_DOMAIN
    try:
        listener = ngrok.forward(NGROK_UPSTREAM_ADDR, **_forward_kwargs)
        if inspect.isawaitable(listener):
            listener = listener
    except Exception as exc:
        raise RuntimeError(f"ngrok.forward failed: {type(exc).__name__}: {exc}") from exc
    WORKER_NGROK_LISTENER = listener

_url = getattr(listener, "url", None)
_url = _url() if callable(_url) else _url
if inspect.isawaitable(_url):
    _url = _url
WORKER_PUBLIC_URL = str(_url or "").strip().rstrip("/")

if not WORKER_PUBLIC_URL.startswith("http"):
    raise RuntimeError(f"ngrok started but did not return a usable public URL (got {_url!r}).")

print("WORKER_PUBLIC_URL:", WORKER_PUBLIC_URL)
print("Upstream (local):  ", f"http://{NGROK_UPSTREAM_ADDR}")

# --- Cell 35 ---
# 28. Verify the PUBLIC /health.
PUBLIC_HEALTH_URL = WORKER_PUBLIC_URL + "/health"
_PUBLIC_HEADERS = {"ngrok-skip-browser-warning": "true", "Accept": "application/json"}

_ok, _payload, _reason = False, None, "not checked"
for _attempt in range(1, 11):
    try:
        resp = requests.get(PUBLIC_HEALTH_URL, headers=_PUBLIC_HEADERS, timeout=20)
        _payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None
        if resp.status_code == 200 and isinstance(_payload, dict) and _payload.get("worker") == "satquery-unified":
            _ok = True
            break
        _reason = f"HTTP {resp.status_code}: {resp.text[:300]}"
    except requests.RequestException as exc:
        _reason = f"request failed: {type(exc).__name__}: {exc}"
    print(f"Public health attempt {_attempt}/10: {_reason}")
    time.sleep(3)

if not _ok:
    raise RuntimeError(f"Public health check FAILED: {_reason}")

print("Public health verified:", _payload)

# --- Cell 36 ---
# 29. Final worker-ready banner + SatQuery .env configuration.
print("=" * 60)
print("SATQUERY UNIFIED WORKER READY")
print("=" * 60)
print()
print(f"PUBLIC_URL={WORKER_PUBLIC_URL}")
print(f"HEALTH={WORKER_PUBLIC_URL}/health")
print(f"PRITHVI={WORKER_PUBLIC_URL}/tools/analyze_multitemporal")
print(f"CLOSP={WORKER_PUBLIC_URL}/tools/analyze_sar_optical")
print(f"EARTHDIAL={WORKER_PUBLIC_URL}/tools/analyze_image")
print(f"GPU={torch.cuda.get_device_name(0)}")
print("MODELS=lazy-loaded")
print("OFFLOADING=enabled")
print("CONCURRENCY=gpu-serialized")
print()
print("=" * 60)
print("SatQuery .env")
print("=" * 60)
print(f"REMOTE_WORKER_URL={WORKER_PUBLIC_URL}")
print()
print("# Compatibility (only needed if the existing backend still reads the three")
print("# separate variable names instead of REMOTE_WORKER_URL):")
print(f"PRITHVI_WORKER_URL={WORKER_PUBLIC_URL}")
print(f"CLOSP_WORKER_URL={WORKER_PUBLIC_URL}")
print(f"EARTHDIAL_WORKER_URL={WORKER_PUBLIC_URL}")
print("=" * 60)

# --- Cell 38 ---
# TEST 1: GET /health -> expect HTTP 200
r = local_session.get(LOCAL_BASE_URL + "/health", timeout=15)
print("TEST 1 - /health:", r.status_code)
print(r.json())
assert r.status_code == 200

# --- Cell 39 ---
# TEST 2: GET /models -> expect all three specialists listed
r = local_session.get(LOCAL_BASE_URL + "/models", timeout=15)
print("TEST 2 - /models:", r.status_code)
print(r.json())
assert r.status_code == 200
assert set(r.json().keys()) == {"prithvi", "closp", "earthdial"}

# --- Cell 40 ---
# TEST 3: GET /gpu -> expect GPU information
r = local_session.get(LOCAL_BASE_URL + "/gpu", timeout=15)
print("TEST 3 - /gpu:", r.status_code)
print(r.json())
assert r.status_code == 200

# --- Cell 41 ---
# TEST 4: Prithvi endpoint - verified official HLS GeoTIFF URLs
PRITHVI_TEST_URLS = {
    "image_t1": "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M/resolve/main/examples/Mexico_HLS.S30.T13REM.2018026T173609.v2.0_cropped.tif",
    "image_t2": "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M/resolve/main/examples/Mexico_HLS.S30.T13REM.2018106T172859.v2.0_cropped.tif",
    "image_t3": "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M/resolve/main/examples/Mexico_HLS.S30.T13REM.2018201T172901.v2.0_cropped.tif",
    "image_t4": "https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M/resolve/main/examples/Mexico_HLS.S30.T13REM.2018266T173029.v2.0_cropped.tif",
}

if all(PRITHVI_TEST_URLS.values()):
    r = local_session.post(
        LOCAL_BASE_URL + "/tools/analyze_multitemporal",
        json={**PRITHVI_TEST_URLS, "query": "Did this area change?"},
        timeout=600,
    )
    print("TEST 4 - Prithvi:", r.status_code)
    print(r.json())
    assert r.status_code == 200
    status_after = local_session.get(LOCAL_BASE_URL + "/models", timeout=15).json()
    print("Prithvi loaded after request (should be False - offloaded):", status_after["prithvi"]["loaded"])
else:
    print("TEST 4 skipped - set PRITHVI_TEST_URLS to 4 real temporal GeoTIFF URLs to run it.")

# --- Cell 42 ---
# TEST 5: CLOSP endpoint - verified real SAR/optical GeoTIFF URLs.
CLOSP_TEST_URLS = {
    "sar_image_url": "https://raw.githubusercontent.com/cloudtostreet/Sen1Floods11/master/sample/S1/Spain_7370579_S1Hand.tif",
    "optical_image_url": "https://raw.githubusercontent.com/cloudtostreet/Sen1Floods11/master/sample/S2/Spain_7370579_S2Hand.tif",
}

if any(CLOSP_TEST_URLS.values()):
    r = local_session.post(
        LOCAL_BASE_URL + "/tools/analyze_sar_optical",
        json={**CLOSP_TEST_URLS, "query": "Compare the SAR and optical observations."},
        timeout=300,
    )
    print("TEST 5 - CLOSP:", r.status_code)
    body = r.json()
    if isinstance(body, dict):
        for k in ("sar", "optical"):
            if body.get(k):
                body[k] = {**body[k], "embedding": f"<{len(body[k]['embedding'])} floats>"}
    print(body)
    assert r.status_code == 200
    status_after = local_session.get(LOCAL_BASE_URL + "/models", timeout=15).json()
    print("CLOSP loaded after request (should be False - offloaded):", status_after["closp"]["loaded"])
else:
    print("TEST 5 skipped - set CLOSP_TEST_URLS to real SAR/optical GeoTIFF URLs to run it.")

# --- Cell 43 ---
# TEST 6: EarthDial endpoint - set a real image/GeoTIFF URL.
EARTHDIAL_TEST_URL = "https://raw.githubusercontent.com/open-mmlab/mmcv/master/tests/data/color.jpg"

if EARTHDIAL_TEST_URL:
    r = local_session.post(
        LOCAL_BASE_URL + "/tools/analyze_image",
        json={"image_url": EARTHDIAL_TEST_URL,
              "query": "What are the main land-cover types visible in this image?"},
        timeout=600,
    )
    print("TEST 6 - EarthDial:", r.status_code)
    print(r.json())
    assert r.status_code == 200
    status_after = local_session.get(LOCAL_BASE_URL + "/models", timeout=15).json()
    print("EarthDial loaded after request (should be False - offloaded):", status_after["earthdial"]["loaded"])
else:
    print("TEST 6 skipped - set EARTHDIAL_TEST_URL to a real image/GeoTIFF URL to run it.")

# --- Cell 44 ---
# TEST 7: MODEL SWITCHING - Prithvi -> CLOSP -> EarthDial -> Prithvi, no restart.
if all(PRITHVI_TEST_URLS.values()) and any(CLOSP_TEST_URLS.values()) and EARTHDIAL_TEST_URL:
    print_gpu("switching test - start")

    r1 = local_session.post(LOCAL_BASE_URL + "/tools/analyze_multitemporal",
                             json={**PRITHVI_TEST_URLS, "query": "change?"}, timeout=600)
    print("Prithvi #1:", r1.status_code)
    print_gpu("after Prithvi #1")

    r2 = local_session.post(LOCAL_BASE_URL + "/tools/analyze_sar_optical",
                             json=CLOSP_TEST_URLS, timeout=300)
    print("CLOSP:", r2.status_code)
    print_gpu("after CLOSP")

    r3 = local_session.post(LOCAL_BASE_URL + "/tools/analyze_image",
                             json={"image_url": EARTHDIAL_TEST_URL, "query": "describe"}, timeout=600)
    print("EarthDial:", r3.status_code)
    print_gpu("after EarthDial")

    r4 = local_session.post(LOCAL_BASE_URL + "/tools/analyze_multitemporal",
                             json={**PRITHVI_TEST_URLS, "query": "change again?"}, timeout=600)
    print("Prithvi #2:", r4.status_code)
    print_gpu("after Prithvi #2")

    assert all(r.status_code == 200 for r in (r1, r2, r3, r4))
    print("TEST 7 PASSED: model switching works without restarting the worker.")
else:
    print("TEST 7 skipped - fill in all test URLs above (TEST 4/5/6) to run the full switching test.")

# --- Cell 45 ---
# TEST 8: PUBLIC NGROK TEST - exercise the public URL end to end.
r = requests.get(WORKER_PUBLIC_URL + "/health", headers=_PUBLIC_HEADERS, timeout=30)
print("TEST 8 - public /health:", r.status_code)
print(r.json())
assert r.status_code == 200

for path, body in [
    ("/tools/analyze_multitemporal", {}),
    ("/tools/analyze_sar_optical", {}),
    ("/tools/analyze_image", {}),
]:
    r = requests.post(WORKER_PUBLIC_URL + path, json=body, headers=_PUBLIC_HEADERS, timeout=30)
    print(f"public POST {path} (empty body) -> HTTP {r.status_code} (expect 400/422, route reachable)")
    assert r.status_code in (400, 422), f"{path} returned {r.status_code}, route may not be wired correctly"

print("TEST 8 PASSED: all three endpoints are reachable through the single public ngrok URL.")

# --- Cell 47 ---
# 30. Final status snapshot.
print("Worker:", WORKER_PUBLIC_URL)
print("Health:", requests.get(WORKER_PUBLIC_URL + "/health", headers=_PUBLIC_HEADERS, timeout=15).json())
print("Models:", local_session.get(LOCAL_BASE_URL + "/models", timeout=15).json())
print("GPU:", local_session.get(LOCAL_BASE_URL + "/gpu", timeout=15).json())
