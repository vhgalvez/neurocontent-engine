# wsl\generar_audio_qwen.py

import json
import os
import traceback
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

PROJECT_DIR = Path(__file__).resolve().parents[1]
INPUT_JSON = PROJECT_DIR / "outputs" / "scripts.json"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "audio"

# Puede ser:
# - la raíz del cache HF del modelo
# - o un snapshot concreto
BASE_MODEL_PATH = os.getenv(
    "QWEN_TTS_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)

VOICE_INSTRUCT = os.getenv(
    "QWEN_TTS_VOICE_INSTRUCT",
    (
        "Voz masculina sobria, segura, natural y persuasiva. "
        "Ritmo medio, dicción clara, tono serio pero cercano. "
        "Estilo mentor invisible."
    ),
)

LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Spanish")
OVERWRITE = os.getenv("QWEN_TTS_OVERWRITE", "false").lower() == "true"

# auto | cuda | cpu
DEVICE_MODE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_model_path(base_path: str) -> str:
    """
    Resuelve automáticamente el snapshot correcto si la ruta base
    apunta al directorio raíz del cache de HuggingFace.
    """
    base = Path(base_path)

    if not base.exists():
        raise RuntimeError(f"No existe la ruta base del modelo: {base}")

    # Caso 1: ya apunta a un snapshot/directorio válido
    if (base / "config.json").exists():
        print(f"✔ Usando modelo directo: {base}")
        return str(base)

    # Caso 2: apunta al root del modelo en el cache HF
    snapshots_dir = base / "snapshots"
    if not snapshots_dir.exists():
        raise RuntimeError(f"No existe la carpeta snapshots en: {base}")

    snapshots = sorted(
        [p for p in snapshots_dir.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for snap in snapshots:
        if (snap / "config.json").exists():
            print(f"✔ Snapshot detectado: {snap}")
            return str(snap)

    raise RuntimeError(f"No se encontró ningún snapshot válido con config.json en: {snapshots_dir}")


def load_items():
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"No existe el archivo: {INPUT_JSON}")

    with INPUT_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("scripts.json no contiene una lista válida")

    return data


def get_device_and_dtype():
    """
    Selección robusta de dispositivo:
    - QWEN_TTS_DEVICE=cpu   -> fuerza CPU
    - QWEN_TTS_DEVICE=cuda  -> fuerza GPU
    - auto                  -> usa GPU si torch la ve
    """
    if DEVICE_MODE == "cpu":
        print("⚠ Usando CPU (forzado por QWEN_TTS_DEVICE=cpu)")
        return "cpu", torch.float32

    if DEVICE_MODE == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("QWEN_TTS_DEVICE=cuda pero torch.cuda.is_available() es False")
        print("🚀 Usando GPU (forzado por QWEN_TTS_DEVICE=cuda)")
        return "cuda:0", torch.float16

    # auto
    if torch.cuda.is_available():
        print("🚀 Usando GPU (auto)")
        return "cuda:0", torch.float16

    print("⚠ Usando CPU (auto fallback)")
    return "cpu", torch.float32


def load_model():
    model_path = resolve_model_path(BASE_MODEL_PATH)
    device_map, dtype = get_device_and_dtype()

    kwargs = {
        "device_map": device_map,
        "dtype": dtype,
        "trust_remote_code": True,
    }

    print(f"📦 Cargando modelo desde: {model_path}")
    print(f"📦 device_map={device_map}, dtype={dtype}")

    try:
        model = Qwen3TTSModel.from_pretrained(model_path, **kwargs)
    except Exception:
        print("❌ Error cargando el modelo:")
        traceback.print_exc()
        raise

    return model


def sanitize_text(text: str) -> str:
    return " ".join(str(text).split()).strip()


def build_fallback_narracion(script: dict) -> str:
    partes = [
        script.get("hook", ""),
        script.get("problema", ""),
        script.get("explicacion", ""),
        *script.get("solucion", []),
        script.get("cierre", ""),
        script.get("cta", ""),
    ]
    return sanitize_text(". ".join([str(p) for p in partes if str(p).strip()]))


def get_script_text(script: dict) -> str:
    narracion = sanitize_text(script.get("narracion", ""))
    if narracion:
        return narracion
    return build_fallback_narracion(script)


def main():
    items = load_items()
    model = load_model()

    for item in items:
        if item.get("estado") != "done":
            continue

        item_id = str(item.get("id", "")).strip()
        script = item.get("script", {})

        if not item_id:
            print("⚠ Saltando item sin id")
            continue

        text = get_script_text(script)

        if not text:
            print(f"[{item_id}] No hay narración, se omite")
            continue

        output_wav = OUTPUT_DIR / f"{item_id}.wav"

        if output_wav.exists() and not OVERWRITE:
            print(f"[{item_id}] Ya existe {output_wav.name}, se omite")
            continue

        print(f"[{item_id}] Generando audio...")
        print(f"[{item_id}] Texto: {text[:140]}{'...' if len(text) > 140 else ''}")

        try:
            wavs, sr = model.generate_voice_design(
                text=text,
                language=LANGUAGE,
                instruct=VOICE_INSTRUCT,
            )
        except Exception:
            print(f"❌ Error generando audio para item {item_id}:")
            traceback.print_exc()
            continue

        try:
            sf.write(str(output_wav), wavs[0], sr)
        except Exception:
            print(f"❌ Error guardando WAV para item {item_id}:")
            traceback.print_exc()
            continue

        print(f"[{item_id}] OK -> {output_wav}")

    print("🎧 Audio completado.")


if __name__ == "__main__":
    main()