# config.py

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JOBS_DIR = BASE_DIR / "jobs"
WSL_DIR = BASE_DIR / "wsl"

DATA_FILE = DATA_DIR / "ideas.csv"
INDEX_FILE = DATA_DIR / "index.csv"

JOB_ID_WIDTH = 6

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = "qwen3:8b"

OPTIONS = {
    "num_ctx": 4096,
    "num_predict": 900,
    "temperature": 0.82,
    "top_p": 0.92,
    "repeat_penalty": 1.08,
}

REQUEST_TIMEOUT_SECONDS = 180
OLLAMA_MAX_RETRIES = int(os.getenv("NC_OLLAMA_MAX_RETRIES", "3"))

OVERWRITE_ALL = os.getenv("NC_OVERWRITE_ALL", "false").lower() == "true"
OVERWRITE_SCRIPT = os.getenv("NC_OVERWRITE_SCRIPT", "false").lower() == "true" or OVERWRITE_ALL
OVERWRITE_MANIFEST = os.getenv("NC_OVERWRITE_MANIFEST", "false").lower() == "true" or OVERWRITE_ALL