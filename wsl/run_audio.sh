#!/usr/bin/env bash
# wsl/run_audio.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QWEN_PYTHON="${QWEN_PYTHON:-$HOME/Qwen3-TTS/venv/bin/python}"
VOICE_ENV_FILE="${VOICE_ENV_FILE:-$PROJECT_DIR/wsl/voices.env}"

cd "$PROJECT_DIR"

if [ -f "$VOICE_ENV_FILE" ]; then
    echo "Cargando configuración de voces desde: $VOICE_ENV_FILE"
    # shellcheck disable=SC1090
    source "$VOICE_ENV_FILE"
fi

export QWEN_TTS_MODEL_PATH="${QWEN_TTS_MODEL_PATH:-/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/0c0e3051f131929182e2c023b9537f8b1c68adfe}"
export QWEN_TTS_VOICE_PRESET="${QWEN_TTS_VOICE_PRESET:-mujer_podcast_seria_35_45}"
export QWEN_TTS_SEED="${QWEN_TTS_SEED:-424242}"
export QWEN_TTS_LANGUAGE="${QWEN_TTS_LANGUAGE:-Spanish}"
export QWEN_TTS_OVERWRITE="${QWEN_TTS_OVERWRITE:-false}"
export QWEN_TTS_DEVICE="${QWEN_TTS_DEVICE:-auto}"
export QWEN_TTS_TEST_SHORT="${QWEN_TTS_TEST_SHORT:-false}"
export QWEN_TTS_USE_FLASH_ATTN="${QWEN_TTS_USE_FLASH_ATTN:-false}"
export PYTHONUNBUFFERED=1

echo "Proyecto: $PROJECT_DIR"
echo "Python Qwen: $QWEN_PYTHON"
echo "Modelo: $QWEN_TTS_MODEL_PATH"
echo "Preset voz: $QWEN_TTS_VOICE_PRESET"
echo "Seed voz: $QWEN_TTS_SEED"
echo "Idioma: $QWEN_TTS_LANGUAGE"
echo "Overwrite: $QWEN_TTS_OVERWRITE"
echo "Device: $QWEN_TTS_DEVICE"
echo "Test corto: $QWEN_TTS_TEST_SHORT"
echo "Flash Attn: $QWEN_TTS_USE_FLASH_ATTN"

if [ ! -x "$QWEN_PYTHON" ]; then
    echo "ERROR: no existe Python de Qwen en $QWEN_PYTHON"
    echo "Revisa el venv de Qwen3-TTS o exporta QWEN_PYTHON manualmente."
    exit 1
fi

set +e
"$QWEN_PYTHON" -u wsl/generar_audio_qwen.py
EXIT_CODE=$?
set -e

echo "Proceso Python terminado con código: $EXIT_CODE"
exit "$EXIT_CODE"