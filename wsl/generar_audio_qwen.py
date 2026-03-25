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

# Puedes sobreescribir esta ruta con una variable de entorno:
# export QWEN_TTS_MODEL_PATH="/ruta/al/modelo"
MODEL_PATH = os.getenv(
    "QWEN_TTS_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)

VOICE_INSTRUCT = os.getenv(
    "QWEN_TTS_VOICE_INSTRUCT",
    (
        "Voz masculina sobria, segura, natural y persuasiva. "
        "Ritmo medio, dicción clara, tono serio pero cercano. "
        "Estilo mentor invisible, sin exagerar ni sonar teatral."
    ),
)

LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Spanish")
OVERWRITE = os.getenv("QWEN_TTS_OVERWRITE", "false").lower() == "true"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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
        return "cuda:0", torch.bfloat16
    return "cpu", torch.float32


def load_model():
    device_map, dtype = get_device_and_dtype()

    kwargs = {
        "device_map": device_map,
        "dtype": dtype,
    }

    # El README oficial usa flash_attention_2 en GPU cuando está disponible. :contentReference[oaicite:1]{index=1}
    if str(device_map).startswith("cuda"):
        kwargs["attn_implementation"] = "flash_attention_2"

    try:
        model = Qwen3TTSModel.from_pretrained(MODEL_PATH, **kwargs)
    except Exception:
        kwargs.pop("attn_implementation", None)
        model = Qwen3TTSModel.from_pretrained(MODEL_PATH, **kwargs)

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
        text = sanitize_text(script.get("narracion", ""))

        if not item_id:
            print("Saltando item sin id")
            continue

        if not text:
            print(f"[{item_id}] No hay narración, se omite")
            continue

        output_wav = OUTPUT_DIR / f"{item_id}.wav"

        if output_wav.exists() and not OVERWRITE:
            print(f"[{item_id}] Ya existe {output_wav.name}, se omite")
            continue

        print(f"[{item_id}] Generando audio...")

        wavs, sr = model.generate_voice_design(
            text=text,
            language=LANGUAGE,
            instruct=VOICE_INSTRUCT,
        )

        sf.write(str(output_wav), wavs[0], sr)
        print(f"[{item_id}] OK -> {output_wav}")

    print("Audio completado.")


if __name__ == "__main__":
    main()