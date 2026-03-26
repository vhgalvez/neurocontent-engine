#!/usr/bin/env bash
# wsl\run_subs.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHISPERX_ENV_BIN="$HOME/miniconda3/envs/whisperx/bin"
WHISPERX_PYTHON="${WHISPERX_PYTHON:-$WHISPERX_ENV_BIN/python}"

cd "$PROJECT_DIR"

echo "Proyecto: $PROJECT_DIR"
echo "WhisperX python: $WHISPERX_PYTHON"

if [ ! -x "$WHISPERX_PYTHON" ]; then
  echo "ERROR: no existe Python del entorno whisperx en $WHISPERX_PYTHON"
  echo "Prueba:"
  echo "  conda activate whisperx"
  echo "  python -m pip install --no-cache-dir whisperx"
  exit 1
fi

echo "Generando subtítulos por job"
WHISPERX_PYTHON="$WHISPERX_PYTHON" python3 wsl/generar_subtitulos.py