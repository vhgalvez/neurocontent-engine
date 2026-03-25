#!/usr/bin/env bash
set -euo pipefail

# wsl\run_wsl_pipeline.sh


PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QWEN_PYTHON="$HOME/Qwen3-TTS/venv/bin/python"

cd "$PROJECT_DIR"

mkdir -p outputs/audio
mkdir -p outputs/subtitles

echo "=== CONFIG ==="
echo "Proyecto: $PROJECT_DIR"
echo "Python Qwen: $QWEN_PYTHON"
echo ""

echo "=== Generando audio con Qwen3-TTS ==="
"$QWEN_PYTHON" wsl/generar_audio_qwen.py

echo ""
echo "=== Generando subtítulos con WhisperX ==="
python3 wsl/generar_subtitulos.py

echo ""
echo "=== Pipeline WSL2 completado ==="
