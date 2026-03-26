#!/usr/bin/env bash
# wsl\run_audio.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_WHISPERX="$HOME/miniconda3/envs/whisperx/bin/whisperx"
WHISPERX_BIN="${WHISPERX_BIN:-$DEFAULT_WHISPERX}"

cd "$PROJECT_DIR"

echo "Proyecto: $PROJECT_DIR"
echo "WhisperX bin: $WHISPERX_BIN"

if [ ! -x "$WHISPERX_BIN" ]; then
    echo "ERROR: no existe WhisperX en $WHISPERX_BIN"
    echo "Primero crea el entorno:"
    echo "  conda create -n whisperx python=3.10 -y"
    echo "  conda activate whisperx"
    echo "  python -m pip install --upgrade pip setuptools wheel"
    echo "  python -m pip install whisperx"
    exit 1
fi

echo "Generando subtitulos por job"
WHISPERX_BIN="$WHISPERX_BIN" python3 wsl/generar_subtitulos.py