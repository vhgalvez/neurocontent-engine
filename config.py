# config.py

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"

DATA_FILE = DATA_DIR / "ideas.csv"
OUTPUT_FILE = OUTPUTS_DIR / "scripts.json"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"

OPTIONS = {
    "num_ctx": 1536,
    "num_predict": 420,
    "temperature": 0.75,
    "top_p": 0.9,
}

REQUEST_TIMEOUT_SECONDS = 180