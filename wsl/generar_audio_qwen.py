# wsl\generar_audio_qwen.py
import json
import os
import random
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

PROJECT_DIR = Path(__file__).resolve().parents[1]
JOBS_DIR = PROJECT_DIR / "jobs"

BASE_MODEL_PATH = os.getenv(
    "QWEN_TTS_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice/snapshots/0c0e3051f131929182e2c023b9537f8b1c68adfe",
)

LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Spanish")
OVERWRITE = os.getenv("QWEN_TTS_OVERWRITE", "false").lower() == "true"
DEVICE_MODE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()
TEST_SHORT_TEXT = os.getenv("QWEN_TTS_TEST_SHORT", "false").lower() == "true"
USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN", "false").lower() == "true"

VOICE_PRESET = os.getenv("QWEN_TTS_VOICE_PRESET", "mujer_podcast_seria_35_45")
VOICE_SEED = int(os.getenv("QWEN_TTS_SEED", "424242"))

VOICE_PRESETS = {
    "mujer_podcast_seria_35_45": {
        "identity": (
            "Voz femenina madura de aproximadamente 35 a 45 años. "
            "Seria, profesional, estable, natural y creíble. "
            "Timbre medio-grave, elegante, con presencia y autoridad tranquila. "
            "No juvenil, no caricaturesca, no exagerada. "
            "Debe sonar como una narradora de podcast profesional."
        ),
        "style": (
            "Ritmo medio, pausado y entendible. "
            "Dicción muy clara. "
            "Entonación natural, sobria y fluida. "
            "Estilo podcast profesional. "
            "Cercana pero seria. "
            "Sin dramatización excesiva. "
            "Sin sonar robótica."
        ),
    },
    "mujer_documental_neutra": {
        "identity": (
            "Voz femenina adulta, madura, neutra y profesional. "
            "Timbre equilibrado, claro y natural. "
            "Serena, confiable y sobria."
        ),
        "style": (
            "Ritmo medio-lento, vocalización clara, tono documental. "
            "Lectura precisa, calmada y natural."
        ),
    },
    "hombre_narrador_sobrio": {
        "identity": (
            "Voz masculina adulta, madura, sobria y segura. "
            "Tono profesional, grave moderado, natural y persuasivo."
        ),
        "style": (
            "Ritmo medio, dicción clara, tono serio pero cercano. "
            "Estilo narrador de podcast o documental."
        ),
    },
}


def log(msg: str):
    print(msg, flush=True)


def safe_read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def safe_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
        "voice_preset": "",
        "voice_seed": None,
        "voice_model_path": "",
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
    base = Path(base_path)

    if not base.exists():
        raise RuntimeError(f"No existe la ruta base del modelo: {base}")

    if (base / "config.json").exists():
        log(f"Usando modelo directo: {base}")
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
            log(f"Snapshot detectado: {snapshot}")
            return str(snapshot)

    raise RuntimeError(f"No se encontró snapshot válido con config.json en: {snapshots_dir}")


def get_device_and_dtype():
    if DEVICE_MODE == "cpu":
        log("Usando CPU por configuración")
        return "cpu", torch.float32

    if DEVICE_MODE == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("QWEN_TTS_DEVICE=cuda pero CUDA no está disponible")
        log("Usando GPU por configuración")
        return "cuda:0", torch.float16

    if torch.cuda.is_available():
        log("Usando GPU en modo auto")
        return "cuda:0", torch.float16

    log("Usando CPU en modo auto")
    return "cpu", torch.float32


def set_global_seed(seed: int):
    log(f"Aplicando seed: {seed}")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

    try:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except Exception:
        pass


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

    log(f"Cargando modelo desde: {model_path}")
    log(f"device_map={device_map}, dtype={dtype}, flash_attn={USE_FLASH_ATTN}")

    model = Qwen3TTSModel.from_pretrained(model_path, **kwargs)
    log("Modelo cargado correctamente")
    return model, model_path


def iter_job_dirs():
    if not JOBS_DIR.exists():
        return []
    return sorted(path for path in JOBS_DIR.iterdir() if path.is_dir())


def get_script_text(job_dir: Path) -> str:
    script_path = job_dir / "script.json"
    script_data = safe_read_json(script_path, default={}) or {}
    return " ".join(str(script_data.get("guion_narrado", "")).split()).strip()


def get_job_voice_config(job_dir: Path) -> dict:
    voice_path = job_dir / "voice.json"
    return safe_read_json(voice_path, default={}) or {}


def build_voice_instruction(job_voice_config: dict) -> tuple[str, str, int]:
    preset_name = job_voice_config.get("voice_preset", VOICE_PRESET)
    preset = VOICE_PRESETS.get(preset_name)

    if not preset:
        raise RuntimeError(
            f"Preset de voz no válido: {preset_name}. "
            f"Disponibles: {', '.join(sorted(VOICE_PRESETS.keys()))}"
        )

    identity = job_voice_config.get("identity", preset["identity"]).strip()
    style = job_voice_config.get("style", preset["style"]).strip()
    seed = int(job_voice_config.get("seed", VOICE_SEED))

    instruct = (
        f"{identity} "
        f"{style} "
        "Mantener identidad vocal consistente, estable y natural en toda la narración."
    )
    return preset_name, instruct, seed


def generate_one(model, text: str, instruct: str):
    log("Entrando a generate_voice_design()")
    wavs, sample_rate = model.generate_voice_design(
        text=text,
        language=LANGUAGE,
        instruct=instruct,
    )
    log("generate_voice_design() completado")
    return wavs, sample_rate


def main():
    try:
        job_dirs = iter_job_dirs()
        if not job_dirs:
            log("No hay jobs para procesar en jobs/")
            return

        log(f"Jobs detectados: {[p.name for p in job_dirs]}")
        model, resolved_model_path = load_model()

        if TEST_SHORT_TEXT:
            preset = VOICE_PRESETS.get(VOICE_PRESET, VOICE_PRESETS["mujer_podcast_seria_35_45"])
            instruct = f"{preset['identity']} {preset['style']} Mantener identidad vocal consistente."
            set_global_seed(VOICE_SEED)
            wavs, sample_rate = generate_one(model, "Probando sistema de audio.", instruct)
            test_file = PROJECT_DIR / "jobs" / "test_short.wav"
            sf.write(str(test_file), wavs[0], sample_rate)
            log(f"Test corto completado en {test_file}")
            return

        for job_dir in job_dirs:
            job_id = job_dir.name
            status_path = job_dir / "status.json"
            output_wav = job_dir / "audio" / "narration.wav"

            if output_wav.exists() and not OVERWRITE:
                log(f"[{job_id}] narration.wav ya existe, se omite")
                update_status(
                    status_path,
                    audio_generated=True,
                    last_step="audio_skipped",
                    voice_model_path=resolved_model_path,
                )
                continue

            text = get_script_text(job_dir)
            if not text:
                log(f"[{job_id}] script.json sin guion_narrado, se omite")
                update_status(status_path, audio_generated=False, last_step="audio_missing_script")
                continue

            log(f"[{job_id}] Generando audio")
            try:
                job_voice_config = get_job_voice_config(job_dir)
                preset_name, instruct, seed = build_voice_instruction(job_voice_config)

                log(f"[{job_id}] preset={preset_name}")
                log(f"[{job_id}] seed={seed}")
                log(f"[{job_id}] longitud texto={len(text)}")

                set_global_seed(seed)

                wavs, sample_rate = generate_one(model, text, instruct)
                output_wav.parent.mkdir(parents=True, exist_ok=True)
                sf.write(str(output_wav), wavs[0], sample_rate)

                update_status(
                    status_path,
                    audio_generated=True,
                    last_step="audio_generated",
                    voice_preset=preset_name,
                    voice_seed=seed,
                    voice_model_path=resolved_model_path,
                )

            except Exception:
                log(f"[{job_id}] Error generando audio")
                traceback.print_exc()
                update_status(status_path, audio_generated=False, last_step="audio_error")

        log("Audio completado")

    except Exception:
        log("Fallo general en el módulo de audio")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()