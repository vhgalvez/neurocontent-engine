import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

PROJECT_DIR = Path(__file__).resolve().parents[1]
JOBS_DIR = PROJECT_DIR / "jobs"

# This repository stops at narration audio generation.
# The downstream visual repository should consume jobs/<id>/audio/narration.wav
# together with visual_manifest.json and subtitles for timing-aware editing.

BASE_MODEL_PATH = os.getenv(
    "QWEN_TTS_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)
VOICE_INSTRUCT = os.getenv(
    "QWEN_TTS_VOICE_INSTRUCT",
    (
        "Voz masculina sobria, segura, natural y persuasiva. "
        "Ritmo medio, diccion clara, tono serio pero cercano. "
        "Estilo mentor invisible."
    ),
)
LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Spanish")
OVERWRITE = os.getenv("QWEN_TTS_OVERWRITE", "false").lower() == "true"
DEVICE_MODE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()
TEST_SHORT_TEXT = os.getenv("QWEN_TTS_TEST_SHORT", "false").lower() == "true"
USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN", "false").lower() == "true"


def safe_read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def safe_write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_job_status(status_path: Path) -> dict:
    current = safe_read_json(status_path, default={}) or {}
    defaults = {
        "brief_created": False,
        "script_generated": False,
        "audio_generated": False,
        "subtitles_generated": False,
        "visual_manifest_generated": False,
        "export_ready": False,
        "last_step": "created",
        "updated_at": "",
    }
    defaults.update(current)
    defaults["export_ready"] = bool(
        defaults["brief_created"]
        and defaults["script_generated"]
        and defaults["audio_generated"]
        and defaults["subtitles_generated"]
        and defaults["visual_manifest_generated"]
    )
    return defaults


def update_status(status_path: Path, **changes) -> dict:
    status = load_job_status(status_path)
    status.update(changes)
    status["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status["export_ready"] = bool(
        status["brief_created"]
        and status["script_generated"]
        and status["audio_generated"]
        and status["subtitles_generated"]
        and status["visual_manifest_generated"]
    )
    safe_write_json(status_path, status)
    return status


def resolve_model_path(base_path: str) -> str:
    if "/" in base_path and not base_path.startswith("/"):
        print(f"Usando model id HF: {base_path}")
        return base_path

    base = Path(base_path)
    if not base.exists():
        raise RuntimeError(f"No existe la ruta base del modelo: {base}")

    if (base / "config.json").exists():
        print(f"Usando modelo directo: {base}")
        return str(base)

    snapshots_dir = base / "snapshots"
    if not snapshots_dir.exists():
        raise RuntimeError(f"No existe la carpeta snapshots en: {base}")

    snapshots = sorted(
        [path for path in snapshots_dir.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for snapshot in snapshots:
        if (snapshot / "config.json").exists():
            print(f"Snapshot detectado: {snapshot}")
            return str(snapshot)

    raise RuntimeError(f"No se encontro snapshot valido con config.json en: {snapshots_dir}")


def get_device_and_dtype():
    if DEVICE_MODE == "cpu":
        print("Usando CPU por configuracion")
        return "cpu", torch.float32

    if DEVICE_MODE == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("QWEN_TTS_DEVICE=cuda pero CUDA no esta disponible")
        print("Usando GPU por configuracion")
        return "cuda:0", torch.float16

    if torch.cuda.is_available():
        print("Usando GPU en modo auto")
        return "cuda:0", torch.float16

    print("Usando CPU en modo auto")
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
        "dtype": dtype,
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }
    if USE_FLASH_ATTN and str(device_map).startswith("cuda"):
        kwargs["attn_implementation"] = "flash_attention_2"

    print(f"Cargando modelo desde: {model_path}")
    print(f"device_map={device_map}, dtype={dtype}, flash_attn={USE_FLASH_ATTN}")
    return Qwen3TTSModel.from_pretrained(model_path, **kwargs)


def iter_job_dirs():
    if not JOBS_DIR.exists():
        return []
    return sorted(path for path in JOBS_DIR.iterdir() if path.is_dir())


def get_script_text(job_dir: Path) -> str:
    script_path = job_dir / "script.json"
    script_data = safe_read_json(script_path, default={}) or {}
    return " ".join(str(script_data.get("guion_narrado", "")).split()).strip()


def generate_one(model, text: str):
    return model.generate_voice_design(
        text=text,
        language=LANGUAGE,
        instruct=VOICE_INSTRUCT,
    )


def main():
    job_dirs = iter_job_dirs()
    if not job_dirs:
        print("No hay jobs para procesar en jobs/")
        return

    model = load_model()

    if TEST_SHORT_TEXT:
        wavs, sample_rate = generate_one(model, "Probando sistema de audio.")
        test_file = PROJECT_DIR / "jobs" / "test_short.wav"
        sf.write(str(test_file), wavs[0], sample_rate)
        print(f"Test corto completado en {test_file}")
        return

    for job_dir in job_dirs:
        job_id = job_dir.name
        status_path = job_dir / "status.json"
        output_wav = job_dir / "audio" / "narration.wav"

        if output_wav.exists() and not OVERWRITE:
            print(f"[{job_id}] narration.wav ya existe, se omite")
            update_status(status_path, audio_generated=True, last_step="audio_skipped")
            continue

        text = get_script_text(job_dir)
        if not text:
            print(f"[{job_id}] script.json sin guion_narrado, se omite")
            update_status(status_path, audio_generated=False, last_step="audio_missing_script")
            continue

        print(f"[{job_id}] Generando audio")
        try:
            wavs, sample_rate = generate_one(model, text)
            output_wav.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_wav), wavs[0], sample_rate)
            update_status(status_path, audio_generated=True, last_step="audio_generated")
        except Exception:
            print(f"[{job_id}] Error generando audio")
            traceback.print_exc()
            update_status(status_path, audio_generated=False, last_step="audio_error")

    print("Audio completado")


if __name__ == "__main__":
    main()
