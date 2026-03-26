#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHISPERX_PYTHON="${WHISPERX_PYTHON:-python3}"
WHISPERX_BIN="${WHISPERX_BIN:-$HOME/whisperx-venv/bin/whisperx}"

cd "$PROJECT_DIR"

echo "Proyecto: $PROJECT_DIR"
echo "WhisperX bin: $WHISPERX_BIN"
echo "Generando subtitulos por job"

WHISPERX_BIN="$WHISPERX_BIN" "$WHISPERX_PYTHON" wsl/generar_subtitulos.py
