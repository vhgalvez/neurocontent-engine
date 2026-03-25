# wsl\generar_audio_qwen.py

from qwen_tts import Qwen3TTSModel
import torch
import soundfile as sf
from pathlib import Path
import traceback
import json
import os

# Menos ruido de runtimes auxiliares
os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


PROJECT_DIR = Path(__file__).resolve().parents[1]
INPUT_JSON = PROJECT_DIR / "outputs" / "scripts.json"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "audio"

# Puedes pasar:
# - un model id HF: "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
# - un directorio local descargado con huggingface-cli --local-dir
# - o la raíz del cache HF / snapshot, y el script intentará resolver el snapshot
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

# true | false
TEST_SHORT_TEXT = os.getenv("QWEN_TTS_TEST_SHORT", "false").lower() == "true"

# true | false
USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN",
                           "false").lower() == "true"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_model_path(base_path: str) -> str:
    """
    Acepta:
    - model id HF => se devuelve tal cual
    - directorio local con config.json => se devuelve tal cual
    - raíz del cache HF => resuelve el snapshot más reciente con config.json
    """
    # Si parece model id HF, no tocarlo
    if "/" in base_path and not base_path.startswith("/"):
        print(f"✔ Usando model id HF: {base_path}")
        return base_path

    base = Path(base_path)

    if not base.exists():
        raise RuntimeError(f"No existe la ruta base del modelo: {base}")

    if (base / "config.json").exists():
        print(f"✔ Usando modelo directo: {base}")
        return str(base)

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

    raise RuntimeError(
        f"No se encontró snapshot válido con config.json en: {snapshots_dir}")


def load_items():
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"No existe el archivo: {INPUT_JSON}")

    with INPUT_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("scripts.json no contiene una lista válida")

    return data


def get_device_and_dtype():
    if DEVICE_MODE == "cpu":
        print("⚠ Usando CPU (forzado por QWEN_TTS_DEVICE=cpu)")
        return "cpu", torch.float32

    if DEVICE_MODE == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(
                "QWEN_TTS_DEVICE=cuda pero torch.cuda.is_available() es False")
        print("🚀 Usando GPU (forzado por QWEN_TTS_DEVICE=cuda)")
        return "cuda:0", torch.float16

    if torch.cuda.is_available():
        print("🚀 Usando GPU (auto)")
        return "cuda:0", torch.float16

    print("⚠ Usando CPU (auto fallback)")
    return "cpu", torch.float32


def load_model():
    model_path = resolve_model_path(BASE_MODEL_PATH)
    device_map, dtype = get_device_and_dtype()

    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass

    kwargs = {
        "device_map": device_map,
        "dtype": dtype,  # docs y runtime actual prefieren dtype
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }

    # FlashAttention 2 es recomendado por el repo para reducir VRAM,
    # pero lo dejamos opt-in para no romper el entorno si no está instalado.
    if USE_FLASH_ATTN and str(device_map).startswith("cuda"):
        kwargs["attn_implementation"] = "flash_attention_2"

    print(f"📦 Cargando modelo desde: {model_path}")
    print(
        f"📦 device_map={device_map}, dtype={dtype}, flash_attn={USE_FLASH_ATTN}")

    try:
        model = Qwen3TTSModel.from_pretrained(model_path, **kwargs)
        # NO usar model.eval(): este wrapper puede no exponer ese método
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


def generate_one(model, text: str):
    return model.generate_voice_design(
        text=text,
        language=LANGUAGE,
        instruct=VOICE_INSTRUCT,
    )


def main():
    items = load_items()
    model = load_model()

    if TEST_SHORT_TEXT:
        print("🧪 Modo test corto activado")
        short_text = "Probando sistema de audio."
        wavs, sr = generate_one(model, short_text)
        test_wav = OUTPUT_DIR / "test_short.wav"
        sf.write(str(test_wav), wavs[0], sr)
        print(f"🧪 Test OK -> {test_wav}")
        return

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
            wavs, sr = generate_one(model, text)
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
