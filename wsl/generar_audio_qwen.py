import argparse
import json
import os
import random
import sys
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from config import configure_runtime, get_runtime_paths  # noqa: E402
from director import update_status  # noqa: E402
from job_paths import build_job_paths, ensure_job_structure  # noqa: E402
from voice_registry import (  # noqa: E402
    assign_voice_to_job,
    register_voice,
    resolve_job_voice_assignment,
    safe_read_json,
    update_job_artifact,
    validate_voice_index,
)

os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

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
        "identity": "Voz femenina madura de 35 a 45 años, seria, profesional y creible.",
        "style": "Ritmo medio, diccion clara, tono podcast profesional y estable.",
    },
    "mujer_documental_neutra": {
        "identity": "Voz femenina adulta, neutra, profesional y serena.",
        "style": "Ritmo medio-lento, lectura documental clara y natural.",
    },
    "hombre_narrador_sobrio": {
        "identity": "Voz masculina adulta, sobria, madura y segura.",
        "style": "Ritmo medio, diccion clara, tono serio pero cercano.",
    },
}


def log(message: str) -> None:
    print(message, flush=True)


def resolve_model_path(base_path: str) -> str:
    base = Path(base_path)
    if not base.exists():
        raise RuntimeError(f"No existe la ruta base del modelo: {base}")
    if (base / "config.json").exists():
        return str(base)
    snapshots_dir = base / "snapshots"
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
        return "cpu", torch.float32
    if device_mode == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("QWEN_TTS_DEVICE=cuda pero CUDA no esta disponible")
        return "cuda:0", torch.bfloat16
    return ("cuda:0", torch.bfloat16) if torch.cuda.is_available() else ("cpu", torch.float32)


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def load_model(model_path: str, device_mode: str, use_flash_attn: bool):
    resolved_model_path = resolve_model_path(model_path)
    device_map, dtype = get_device_and_dtype(device_mode)
    kwargs = {
        "device_map": device_map,
        "dtype": dtype,
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }
    if use_flash_attn and str(device_map).startswith("cuda"):
        kwargs["attn_implementation"] = "flash_attention_2"
    model = Qwen3TTSModel.from_pretrained(resolved_model_path, **kwargs)
    if getattr(model.model, "tts_model_type", None) != "voice_design":
        raise RuntimeError("El modelo cargado no es VoiceDesign.")
    return model, resolved_model_path


def resolve_generate_voice_design_method(model) -> callable:
    method = getattr(model, "generate_voice_design", None)
    if not callable(method):
        raise RuntimeError("La libreria qwen_tts instalada no expone generate_voice_design().")
    return method


def iter_job_ids(job_ids: list[str] | None) -> list[str]:
    runtime = get_runtime_paths()
    if job_ids:
        return job_ids
    if not runtime.jobs_root.exists():
        return []
    return sorted(path.name for path in runtime.jobs_root.iterdir() if path.is_dir())


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def read_job_script_text(job_paths) -> str:
    script_path = job_paths.script if job_paths.script.exists() else job_paths.legacy_script_candidates[0]
    payload = safe_read_json(script_path, default={}) or {}
    return normalize_text(payload.get("guion_narrado", ""))


def build_voice_instruction(preset_name: str, seed: int, description: str = "", identity: str = "", style: str = "") -> tuple[str, str, int]:
    preset = VOICE_PRESETS.get(preset_name)
    if not preset:
        valid = ", ".join(sorted(VOICE_PRESETS))
        raise RuntimeError(f"Preset de voz no valido: {preset_name}. Disponibles: {valid}")
    final_identity = normalize_text(identity or preset["identity"])
    final_style = normalize_text(style or preset["style"])
    final_description = normalize_text(description)
    instruct = " ".join(
        part
        for part in [
            final_identity,
            final_style,
            final_description,
            "Mantener identidad vocal consistente, estable y natural.",
        ]
        if part
    ).strip()
    return preset_name, instruct, seed


def resolve_or_register_voice(job_paths, explicit_voice_id: str | None, resolved_model_path: str, default_preset: str, default_seed: int, language: str):
    runtime = get_runtime_paths()
    assigned = resolve_job_voice_assignment(runtime, job_paths, explicit_voice_id=explicit_voice_id)
    if assigned:
        record = assigned["record"]
        return record, assigned["selection_mode"]

    legacy_config = safe_read_json(job_paths.legacy_voice_config, default={}) or {}
    preset = legacy_config.get("voice_preset", default_preset)
    seed = int(legacy_config.get("seed", default_seed))
    description = normalize_text(legacy_config.get("voice_description", ""))
    identity = normalize_text(legacy_config.get("identity", ""))
    style = normalize_text(legacy_config.get("style", ""))
    preset_name, instruct, resolved_seed = build_voice_instruction(
        preset_name=preset,
        seed=seed,
        description=description,
        identity=identity,
        style=style,
    )
    record = register_voice(
        runtime,
        scope="job",
        job_id=job_paths.job_id,
        voice_name=legacy_config.get("voice_name") or f"job_{job_paths.job_id}_voice",
        voice_description=description or f"VoiceDesign auto-registrada para job {job_paths.job_id}.",
        model_name=resolved_model_path,
        language=language,
        seed=resolved_seed,
        voice_instruct=instruct,
        voice_preset=preset_name,
        engine="voice_design",
        notes="Auto-registrada desde el flujo VoiceDesign por compatibilidad.",
    )
    assign_voice_to_job(job_paths, record, selection_mode="job_auto_registered")
    return record, "job_auto_registered"


def generate_audio(model, text: str, instruct: str, language: str):
    generator = resolve_generate_voice_design_method(model)
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


def process_job(model, resolved_model_path: str, job_id: str, overwrite: bool, default_preset: str, default_seed: int, language: str, explicit_voice_id: str | None) -> None:
    job_paths = ensure_job_structure(build_job_paths(job_id, get_runtime_paths()))
    if job_paths.audio.exists() and not overwrite:
        assigned = resolve_job_voice_assignment(get_runtime_paths(), job_paths, explicit_voice_id=explicit_voice_id)
        record = assigned["record"] if assigned else {}
        update_status(
            job_paths.status,
            audio_generated=True,
            last_step="audio_skipped_existing",
            voice_id=record.get("voice_id", ""),
            voice_scope=record.get("scope", ""),
            voice_source=(assigned.get("selection_mode", "") if assigned else ""),
            voice_name=record.get("voice_name", ""),
            voice_selection_mode=assigned.get("selection_mode", "") if assigned else "",
            voice_model_name=record.get("model_name", ""),
            voice_reference_file=record.get("reference_file", "") or "",
            audio_file=get_runtime_paths().to_dataset_relative(job_paths.audio),
        )
        return

    text = read_job_script_text(job_paths)
    if not text:
        update_status(job_paths.status, audio_generated=False, last_step="audio_missing_script")
        return

    record, selection_mode = resolve_or_register_voice(
        job_paths=job_paths,
        explicit_voice_id=explicit_voice_id,
        resolved_model_path=resolved_model_path,
        default_preset=default_preset,
        default_seed=default_seed,
        language=language,
    )
    preset_name, instruct, resolved_seed = build_voice_instruction(
        preset_name=record.get("voice_preset") or default_preset,
        seed=int(record.get("seed", default_seed)),
        description=record.get("voice_description", ""),
    )

    set_global_seed(resolved_seed)
    wav, sample_rate = generate_audio(model=model, text=text, instruct=instruct, language=language)
    write_wav(job_paths.audio, wav, sample_rate)
    generated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat()
    update_job_artifact(
        job_paths,
        artifact_type="audio",
        file_path=get_runtime_paths().to_dataset_relative(job_paths.audio),
        generated_at=generated_at,
    )
    update_status(
        job_paths.status,
        audio_generated=True,
        last_step="audio_generated_voice_design",
        voice_id=record.get("voice_id", ""),
        voice_scope=record.get("scope", ""),
        voice_source=selection_mode,
        voice_name=record.get("voice_name", ""),
        voice_selection_mode=selection_mode,
        voice_model_name=record.get("model_name", ""),
        voice_reference_file=record.get("reference_file", "") or "",
        audio_file=get_runtime_paths().to_dataset_relative(job_paths.audio),
        audio_generated_at=generated_at,
    )
    log(f"[{job_paths.job_id}] Audio generado en {job_paths.audio} con preset={preset_name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera audio por jobs usando VoiceDesign.")
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument("--job-id", action="append", dest="job_ids", help="Procesa un job especifico. Repetible.")
    parser.add_argument("--voice-id", help="Selecciona una voz ya registrada.")
    parser.add_argument("--text", help="Genera un clip directo sin leer jobs.")
    parser.add_argument("--output", help="Ruta de salida cuando se usa --text.")
    parser.add_argument("--preset", default=DEFAULT_VOICE_PRESET, help="Preset por defecto.")
    parser.add_argument("--seed", type=int, default=DEFAULT_VOICE_SEED, help="Seed por defecto.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Idioma para Qwen3-TTS.")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH, help="Ruta del modelo VoiceDesign.")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["auto", "cpu", "cuda"], help="Device.")
    parser.add_argument("--overwrite", action="store_true", default=DEFAULT_OVERWRITE, help="Sobrescribe audio.")
    parser.add_argument("--test-short", action="store_true", default=DEFAULT_TEST_SHORT, help="Prueba corta.")
    parser.add_argument("--test-text", default=DEFAULT_TEST_TEXT, help="Texto para --test-short.")
    parser.add_argument("--use-flash-attn", action="store_true", default=DEFAULT_USE_FLASH_ATTN)
    return parser.parse_args()


def run_direct_text(model, text: str, output: Path, preset: str, seed: int, language: str) -> None:
    _, instruct, resolved_seed = build_voice_instruction(preset_name=preset, seed=seed)
    set_global_seed(resolved_seed)
    wav, sample_rate = generate_audio(model=model, text=normalize_text(text), instruct=instruct, language=language)
    write_wav(output, wav, sample_rate)
    log(f"[audio] Clip directo generado en {output}")


def main() -> None:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)
    validate_voice_index(get_runtime_paths())

    try:
        model, resolved_model_path = load_model(
            model_path=args.model_path,
            device_mode=args.device,
            use_flash_attn=args.use_flash_attn,
        )

        if args.test_short:
            output = get_runtime_paths().jobs_root / "test_short.wav"
            run_direct_text(model=model, text=args.test_text, output=output, preset=args.preset, seed=args.seed, language=args.language)
            return

        if args.text:
            output = Path(args.output) if args.output else PROJECT_DIR / "outputs" / "voice_design_preview.wav"
            run_direct_text(model=model, text=args.text, output=output, preset=args.preset, seed=args.seed, language=args.language)
            return

        job_ids = iter_job_ids(args.job_ids)
        if not job_ids:
            log("[audio] No hay jobs para procesar")
            return

        log(f"[audio] Jobs detectados: {job_ids}")
        for job_id in job_ids:
            try:
                process_job(
                    model=model,
                    resolved_model_path=resolved_model_path,
                    job_id=job_id,
                    overwrite=args.overwrite,
                    default_preset=args.preset,
                    default_seed=args.seed,
                    language=args.language,
                    explicit_voice_id=args.voice_id,
                )
            except Exception as exc:
                job_paths = ensure_job_structure(build_job_paths(job_id, get_runtime_paths()))
                log(f"[{job_id}] Error generando audio: {exc}")
                traceback.print_exc()
                update_status(job_paths.status, audio_generated=False, last_step="audio_error_voice_design")

    except Exception as exc:
        log(f"[audio] Fallo general: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
