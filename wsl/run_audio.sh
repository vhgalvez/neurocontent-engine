#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QWEN_PYTHON="${QWEN_PYTHON:-$HOME/Qwen3-TTS/venv/bin/python}"

cd "$PROJECT_DIR"

echo "Proyecto: $PROJECT_DIR"
echo "Python Qwen: $QWEN_PYTHON"
echo "Generando audio por job"

"$QWEN_PYTHON" wsl/generar_audio_qwen.py
