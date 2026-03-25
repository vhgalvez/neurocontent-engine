# wsl\generar_audio_qwen.py

import json
import os
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


PROJECT_DIR = Path(__file__).resolve().parents[1]
INPUT_JSON = PROJECT_DIR / "outputs" / "scripts.json"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "audio"

# 🔥 Ruta base (puede ser root o snapshot)
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

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# 🔥 NUEVO: resolver snapshot automáticamente
def resolve_model_path(base_path: str) -> str:
    base = Path(base_path)

    # Si ya es snapshot válido
    if (base / "config.json").exists():
        print(f"✔ Usando modelo directo: {base}")
        return str(base)

    snapshots_dir = base / "snapshots"

    if not snapshots_dir.exists():
        raise RuntimeError(f"No existe snapshots en {base}")

    snapshots = sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)

    for snap in snapshots:
        if (snap / "config.json").exists():
            print(f"✔ Snapshot detectado: {snap}")
            return str(snap)

    raise RuntimeError("No se encontró snapshot válido con config.json")


def load_items():
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"No existe el archivo: {INPUT_JSON}")

    with INPUT_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("scripts.json no contiene una lista válida")

    return data


def get_device_and_dtype():
    if torch.cuda.is_available():
        print("🚀 Usando GPU")
        return "cuda:0", torch.bfloat16
    print("⚠ Usando CPU")
    return "cpu", torch.float32


def load_model():
    model_path = resolve_model_path(BASE_MODEL_PATH)

    device_map, dtype = get_device_and_dtype()

    kwargs = {
        "device_map": device_map,
        "dtype": dtype,
        "trust_remote_code": True,  # 🔥 CLAVE
    }

    if str(device_map).startswith("cuda"):
        kwargs["attn_implementation"] = "flash_attention_2"

    print(f"📦 Cargando modelo desde: {model_path}")

    try:
        model = Qwen3TTSModel.from_pretrained(model_path, **kwargs)
    except Exception as e:
        print("⚠ Fallo con flash_attention, reintentando...")
        kwargs.pop("attn_implementation", None)
        model = Qwen3TTSModel.from_pretrained(model_path, **kwargs)

    return model


def sanitize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def main():
    items = load_items()
    model = load_model()

    for item in items:
        if item.get("estado") != "done":
            continue

        item_id = str(item.get("id", "")).strip()
        script = item.get("script", {})

        # 🔥 IMPORTANTE: fallback si no existe narracion
        text = sanitize_text(
            script.get("narracion")
            or f"{script.get('hook','')}. {script.get('problema','')}. {script.get('explicacion','')}. {' '.join(script.get('solucion',[]))}. {script.get('cierre','')}. {script.get('cta','')}"
        )

        if not item_id:
            print("Saltando item sin id")
            continue

        if not text:
            print(f"[{item_id}] No hay narración, se omite")
            continue

        output_wav = OUTPUT_DIR / f"{item_id}.wav"

        if output_wav.exists() and not OVERWRITE:
            print(f"[{item_id}] Ya existe, se omite")
            continue

        print(f"[{item_id}] Generando audio...")

        wavs, sr = model.generate_voice_design(
            text=text,
            language=LANGUAGE,
            instruct=VOICE_INSTRUCT,
        )

        sf.write(str(output_wav), wavs[0], sr)

        print(f"[{item_id}] OK -> {output_wav}")

    print("🎧 Audio completado.")


if __name__ == "__main__":
    main()