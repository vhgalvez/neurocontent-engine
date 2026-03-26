# wsl\generar_audio_qwen.py
import argparse
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

DEFAULT_MODEL_PATH = os.getenv(
    "QWEN_TTS_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)
DEFAULT_LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Spanish")
DEFAULT_OVERWRITE = os.getenv("QWEN_TTS_OVERWRITE", "false").lower() == "true"
DEFAULT_DEVICE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()
DEFAULT_TEST_SHORT = os.getenv("QWEN_TTS_TEST_SHORT", "false").lower() == "true"
DEFAULT_USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN", "false").lower() == "true"
DEFAULT_VOICE_PRESET = os.getenv("QWEN_TTS_VOICE_PRESET", "mujer_podcast_seria_35_45")
DEFAULT_VOICE_SEED = int(os.getenv("QWEN_TTS_SEED", "424242"))
DEFAULT_TEST_TEXT = os.getenv("QWEN_TTS_TEST_TEXT", "Probando sistema de audio con Qwen3 TTS.")

VOICE_PRESETS = {
    "mujer_podcast_seria_35_45": {
        "identity": (
            "Voz femenina madura de aproximadamente 35 a 45 años. "
            "Seria, profesional, estable, natural y creible. "
            "Timbre medio-grave, elegante, con presencia y autoridad tranquila. "
            "No juvenil, no caricaturesca, no exagerada. "
            "Debe sonar como una narradora de podcast profesional."
        ),
        "style": (
            "Ritmo medio, pausado y entendible. "
            "Diccion muy clara. "
            "Entonacion natural, sobria y fluida. "
            "Estilo podcast profesional. "
            "Cercana pero seria. "
            "Sin dramatizacion excesiva. "
            "Sin sonar robotica."
        ),
    },
    "mujer_documental_neutra": {
        "identity": (
            "Voz femenina adulta, madura, neutra y profesional. "
            "Timbre equilibrado, claro y natural. "
            "Serena, confiable y sobria."
        ),
        "style": (
            "Ritmo medio-lento, vocalizacion clara, tono documental. "
            "Lectura precisa, calmada y natural."
        ),
    },
    "hombre_narrador_sobrio": {
        "identity": (
            "Voz masculina adulta, madura, sobria y segura. "
            "Tono profesional, grave moderado, natural y persuasivo."
        ),
        "style": (
            "Ritmo medio, diccion clara, tono serio pero cercano. "
            "Estilo narrador de podcast o documental."
        ),
    },
}


def log(message: str) -> None:
    print(message, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def safe_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


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
        "voice_flow": "",
        "voice_description": "",
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
    status["updated_at"] = now_iso()
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
        return str(base)

    snapshots_dir = base / "snapshots"
    if not snapshots_dir.exists():
        raise RuntimeError(f"No existe la carpeta snapshots en: {base}")

    snapshots = sorted(
        (path for path in snapshots_dir.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for snapshot in snapshots:
        if (snapshot / "config.json").exists():
            return str(snapshot)

    raise RuntimeError(f"No se encontro snapshot valido con config.json en: {snapshots_dir}")


def get_device_and_dtype(device_mode: str) -> tuple[str, torch.dtype]:
    if device_mode == "cpu":
        log("[audio] Device forzado: CPU")
        return "cpu", torch.float32

    if device_mode == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("QWEN_TTS_DEVICE=cuda pero CUDA no esta disponible")
        log("[audio] Device forzado: GPU")
        return "cuda:0", torch.bfloat16

    if torch.cuda.is_available():
        log("[audio] Device auto: GPU")
        return "cuda:0", torch.bfloat16

    log("[audio] Device auto: CPU")
    return "cpu", torch.float32


def set_global_seed(seed: int) -> None:
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


def load_model(model_path: str, device_mode: str, use_flash_attn: bool):
    resolved_model_path = resolve_model_path(model_path)
    device_map, dtype = get_device_and_dtype(device_mode)

    if str(device_map).startswith("cuda") and torch.cuda.is_available():
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
    if use_flash_attn and str(device_map).startswith("cuda"):
        kwargs["attn_implementation"] = "flash_attention_2"

    log(f"[audio] Modelo VoiceDesign: {resolved_model_path}")
    log(f"[audio] device_map={device_map} dtype={dtype} flash_attn={use_flash_attn}")
    model = Qwen3TTSModel.from_pretrained(resolved_model_path, **kwargs)
    if getattr(model.model, "tts_model_type", None) != "voice_design":
        raise RuntimeError(
            "El modelo cargado no es VoiceDesign. "
            f"tts_model_type={getattr(model.model, 'tts_model_type', 'desconocido')}"
        )
    return model, resolved_model_path


def resolve_generate_voice_design_method(model) -> callable:
    method = getattr(model, "generate_voice_design", None)
    if not callable(method):
        raise RuntimeError(
            "La libreria qwen_tts instalada no expone generate_voice_design(). "
            "No se puede ejecutar el flujo oficial VoiceDesign."
        )
    return method


def iter_job_dirs(job_ids: list[str] | None) -> list[Path]:
    if job_ids:
        return [JOBS_DIR / job_id for job_id in job_ids]
    if not JOBS_DIR.exists():
        return []
    return sorted(path for path in JOBS_DIR.iterdir() if path.is_dir())


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def get_script_text(job_dir: Path) -> str:
    script_path = job_dir / "script.json"
    script_data = safe_read_json(script_path, default={}) or {}
    return normalize_text(script_data.get("guion_narrado", ""))


def get_job_voice_config(job_dir: Path) -> dict:
    voice_path = job_dir / "voice.json"
    return safe_read_json(voice_path, default={}) or {}


def build_voice_instruction(
    job_voice_config: dict,
    default_preset: str,
    default_seed: int,
) -> tuple[str, str, int, str]:
    preset_name = job_voice_config.get("voice_preset", default_preset)
    preset = VOICE_PRESETS.get(preset_name)
    if not preset:
        valid = ", ".join(sorted(VOICE_PRESETS))
        raise RuntimeError(f"Preset de voz no valido: {preset_name}. Disponibles: {valid}")

    identity = normalize_text(job_voice_config.get("identity", preset["identity"]))
    style = normalize_text(job_voice_config.get("style", preset["style"]))
    description = normalize_text(job_voice_config.get("voice_description", ""))
    seed = int(job_voice_config.get("seed", default_seed))

    parts = [identity, style, description, "Mantener identidad vocal consistente, estable y natural."]
    instruct = " ".join(part for part in parts if part).strip()
    return preset_name, instruct, seed, description


def generate_audio(
    model,
    text: str,
    instruct: str,
    language: str,
):
    generator = resolve_generate_voice_design_method(model)
    log("[audio] Ejecutando generate_voice_design()")
    wavs, sample_rate = generator(
        text=text,
        instruct=instruct,
        language=language,
        non_streaming_mode=True,
    )
    if not wavs:
        raise RuntimeError("generate_voice_design() no devolvio audio")
    return wavs[0], sample_rate


def write_wav(path: Path, wav: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), wav, sample_rate)


def process_job(
    model,
    resolved_model_path: str,
    job_dir: Path,
    overwrite: bool,
    default_preset: str,
    default_seed: int,
    language: str,
) -> None:
    job_id = job_dir.name
    status_path = job_dir / "status.json"
    output_wav = job_dir / "audio" / "narration.wav"

    if not job_dir.exists():
        raise RuntimeError(f"El job no existe: {job_dir}")

    if output_wav.exists() and not overwrite:
        log(f"[{job_id}] narration.wav ya existe; se omite por overwrite=false")
        update_status(
            status_path,
            audio_generated=True,
            last_step="audio_skipped_existing",
            voice_flow="voice_design",
            voice_model_path=resolved_model_path,
        )
        return

    text = get_script_text(job_dir)
    if not text:
        log(f"[{job_id}] script.json no contiene guion_narrado")
        update_status(status_path, audio_generated=False, last_step="audio_missing_script")
        return

    job_voice_config = get_job_voice_config(job_dir)
    preset_name, instruct, seed, description = build_voice_instruction(
        job_voice_config=job_voice_config,
        default_preset=default_preset,
        default_seed=default_seed,
    )

    log(f"[{job_id}] preset={preset_name}")
    log(f"[{job_id}] seed={seed}")
    log(f"[{job_id}] caracteres={len(text)}")

    set_global_seed(seed)
    wav, sample_rate = generate_audio(
        model=model,
        text=text,
        instruct=instruct,
        language=language,
    )
    write_wav(output_wav, wav, sample_rate)
    update_status(
        status_path,
        audio_generated=True,
        last_step="audio_generated_voice_design",
        voice_flow="voice_design",
        voice_preset=preset_name,
        voice_seed=seed,
        voice_model_path=resolved_model_path,
        voice_description=description,
    )
    log(f"[{job_id}] Audio generado en {output_wav}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera audio por jobs usando el flujo oficial VoiceDesign de Qwen3-TTS."
    )
    parser.add_argument("--job-id", action="append", dest="job_ids", help="Procesa un job especifico. Repetible.")
    parser.add_argument("--text", help="Genera un clip directo sin leer jobs/script.json.")
    parser.add_argument("--output", help="Ruta de salida cuando se usa --text.")
    parser.add_argument("--preset", default=DEFAULT_VOICE_PRESET, help="Preset global de voz.")
    parser.add_argument("--seed", type=int, default=DEFAULT_VOICE_SEED, help="Seed global.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Idioma para Qwen3-TTS.")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH, help="Ruta del modelo VoiceDesign.")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["auto", "cpu", "cuda"], help="Device.")
    parser.add_argument("--overwrite", action="store_true", default=DEFAULT_OVERWRITE, help="Sobrescribe narration.wav.")
    parser.add_argument(
        "--test-short",
        action="store_true",
        default=DEFAULT_TEST_SHORT,
        help="Ejecuta una prueba corta y guarda jobs/test_short.wav.",
    )
    parser.add_argument("--test-text", default=DEFAULT_TEST_TEXT, help="Texto para --test-short.")
    parser.add_argument(
        "--use-flash-attn",
        action="store_true",
        default=DEFAULT_USE_FLASH_ATTN,
        help="Usa flash_attention_2 si esta disponible.",
    )
    return parser.parse_args()


def run_direct_text(
    model,
    text: str,
    output: Path,
    preset: str,
    seed: int,
    language: str,
) -> None:
    preset_name, instruct, resolved_seed, _ = build_voice_instruction(
        job_voice_config={"voice_preset": preset, "seed": seed},
        default_preset=preset,
        default_seed=seed,
    )
    set_global_seed(resolved_seed)
    wav, sample_rate = generate_audio(
        model=model,
        text=normalize_text(text),
        instruct=instruct,
        language=language,
    )
    write_wav(output, wav, sample_rate)
    log(f"[audio] Clip directo generado en {output} con preset={preset_name} seed={resolved_seed}")


def main() -> None:
    args = parse_args()

    try:
        model, resolved_model_path = load_model(
            model_path=args.model_path,
            device_mode=args.device,
            use_flash_attn=args.use_flash_attn,
        )

        if args.test_short:
            output = PROJECT_DIR / "jobs" / "test_short.wav"
            run_direct_text(
                model=model,
                text=args.test_text,
                output=output,
                preset=args.preset,
                seed=args.seed,
                language=args.language,
            )
            return

        if args.text:
            output = Path(args.output) if args.output else PROJECT_DIR / "outputs" / "voice_design_preview.wav"
            run_direct_text(
                model=model,
                text=args.text,
                output=output,
                preset=args.preset,
                seed=args.seed,
                language=args.language,
            )
            return

        job_dirs = iter_job_dirs(args.job_ids)
        if not job_dirs:
            log("[audio] No hay jobs para procesar")
            return

        log(f"[audio] Jobs detectados: {[path.name for path in job_dirs]}")
        for job_dir in job_dirs:
            try:
                process_job(
                    model=model,
                    resolved_model_path=resolved_model_path,
                    job_dir=job_dir,
                    overwrite=args.overwrite,
                    default_preset=args.preset,
                    default_seed=args.seed,
                    language=args.language,
                )
            except Exception as exc:
                log(f"[{job_dir.name}] Error generando audio: {exc}")
                traceback.print_exc()
                update_status(job_dir / "status.json", audio_generated=False, last_step="audio_error_voice_design")

        log("[audio] Flujo VoiceDesign completado")

    except Exception as exc:
        log(f"[audio] Fallo general: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
