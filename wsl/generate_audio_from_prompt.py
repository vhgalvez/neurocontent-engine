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
from qwen_tts import Qwen3TTSModel, VoiceClonePromptItem

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from config import configure_runtime, get_runtime_paths  # noqa: E402
from director import update_status  # noqa: E402
from job_paths import build_job_paths, ensure_job_structure  # noqa: E402
from voice_registry import assign_voice_to_job, normalize_voice_record, register_voice, resolve_job_voice_assignment, safe_read_json, update_job_artifact, update_job_audio_synthesis, validate_voice_index  # noqa: E402

DEFAULT_BASE_MODEL_PATH = os.getenv(
    "QWEN_TTS_BASE_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base",
)
DEFAULT_LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Spanish")
DEFAULT_REFERENCE_LANGUAGE = os.getenv("QWEN_TTS_REFERENCE_LANGUAGE", DEFAULT_LANGUAGE)
DEFAULT_DEVICE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()
DEFAULT_OVERWRITE = os.getenv("QWEN_TTS_OVERWRITE", "false").lower() == "true"
DEFAULT_USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN", "false").lower() == "true"
DEFAULT_X_VECTOR_ONLY = os.getenv("QWEN_TTS_X_VECTOR_ONLY_MODE", "false").lower() == "true"
DEFAULT_SEED = int(os.getenv("QWEN_TTS_SEED", "424242"))


def log(message: str) -> None:
    print(message, flush=True)


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def resolve_model_path(base_path: str) -> str:
    base = Path(base_path)
    if (base / "config.json").exists():
        return str(base)
    snapshots = sorted((base / "snapshots").iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
    for snapshot in snapshots:
        if (snapshot / "config.json").exists():
            return str(snapshot)
    raise RuntimeError(f"No se encontro snapshot valido con config.json en {base}")


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
    if getattr(model.model, "tts_model_type", None) != "base":
        raise RuntimeError("El modelo cargado no es Base.")
    return model, resolved_model_path


def serialize_prompt_items(items: list[VoiceClonePromptItem]) -> list[dict]:
    return [
        {
            "ref_code": item.ref_code.detach().cpu().tolist() if item.ref_code is not None else None,
            "ref_spk_embedding": item.ref_spk_embedding.detach().cpu().tolist(),
            "x_vector_only_mode": bool(item.x_vector_only_mode),
            "icl_mode": bool(item.icl_mode),
            "ref_text": item.ref_text,
        }
        for item in items
    ]


def deserialize_prompt_items(data: list[dict]) -> list[VoiceClonePromptItem]:
    items: list[VoiceClonePromptItem] = []
    for row in data:
        items.append(
            VoiceClonePromptItem(
                ref_code=torch.tensor(row["ref_code"], dtype=torch.long) if row.get("ref_code") is not None else None,
                ref_spk_embedding=torch.tensor(row["ref_spk_embedding"], dtype=torch.float32),
                x_vector_only_mode=bool(row.get("x_vector_only_mode", False)),
                icl_mode=bool(row.get("icl_mode", False)),
                ref_text=row.get("ref_text"),
            )
        )
    return items


def save_prompt_json(path: Path, prompt_items: list[VoiceClonePromptItem], metadata: dict) -> None:
    safe_write_json(path, {"format": "qwen3_voice_clone_prompt_items", "items": serialize_prompt_items(prompt_items), "metadata": metadata})


def load_prompt_json(path: Path) -> list[VoiceClonePromptItem]:
    payload = safe_read_json(path, default=None)
    if not payload or payload.get("format") != "qwen3_voice_clone_prompt_items":
        raise RuntimeError(f"Formato de prompt no soportado en {path}")
    return deserialize_prompt_items(payload.get("items", []))


def read_job_text(job_paths) -> str:
    script_path = job_paths.script if job_paths.script.exists() else job_paths.legacy_script_candidates[0]
    script_data = safe_read_json(script_path, default={}) or {}
    return normalize_text(script_data.get("guion_narrado", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera audio consistente con Qwen3-TTS Base.")
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument("--job-id", help="Job a procesar.")
    parser.add_argument("--voice-id", help="Selecciona una voz ya registrada.")
    parser.add_argument("--text", help="Texto directo para sintetizar sin usar job.")
    parser.add_argument("--output", help="Ruta de salida para --text.")
    parser.add_argument("--reference-wav", help="Ruta explicita al wav de referencia.")
    parser.add_argument("--reference-text", help="Texto exacto del wav de referencia.")
    parser.add_argument("--voice-clone-prompt", help="JSON previamente serializado.")
    parser.add_argument("--save-prompt", action="store_true", help="Guarda el prompt serializado.")
    parser.add_argument("--prompt-output", help="Ruta explicita para guardar el prompt serializado.")
    parser.add_argument("--voice-name", default="voz_principal")
    parser.add_argument("--scope", choices=["global", "job"], default="global")
    parser.add_argument("--x-vector-only-mode", action="store_true", default=DEFAULT_X_VECTOR_ONLY)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--reference-language", default=DEFAULT_REFERENCE_LANGUAGE)
    parser.add_argument("--model-path", default=DEFAULT_BASE_MODEL_PATH)
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["auto", "cpu", "cuda"])
    parser.add_argument("--overwrite", action="store_true", default=DEFAULT_OVERWRITE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--use-flash-attn", action="store_true", default=DEFAULT_USE_FLASH_ATTN)
    return parser.parse_args()


def build_or_load_prompt(model, reference_wav: Path, reference_text: str | None, x_vector_only_mode: bool, prompt_input: Path | None, prompt_output: Path | None, save_prompt: bool):
    if prompt_input:
        return load_prompt_json(prompt_input), str(prompt_input)

    create_prompt = getattr(model, "create_voice_clone_prompt", None)
    if not callable(create_prompt):
        raise RuntimeError("La libreria qwen_tts no expone create_voice_clone_prompt()")
    if not reference_wav.exists():
        raise RuntimeError(f"No existe reference.wav: {reference_wav}")
    if not x_vector_only_mode and not normalize_text(reference_text or ""):
        raise RuntimeError("reference_text es obligatorio cuando x_vector_only_mode=false")

    prompt_items = create_prompt(ref_audio=str(reference_wav), ref_text=reference_text, x_vector_only_mode=x_vector_only_mode)
    saved_path = None
    if save_prompt:
        if prompt_output is None:
            prompt_output = reference_wav.parent / "voice_clone_prompt.json"
        save_prompt_json(prompt_output, prompt_items, {"reference_wav": str(reference_wav), "reference_text": reference_text})
        saved_path = str(prompt_output)
    return prompt_items, saved_path


def resolve_voice(job_paths, args: argparse.Namespace, resolved_model_path: str):
    runtime = get_runtime_paths()
    if args.job_id:
        assigned = resolve_job_voice_assignment(runtime, job_paths, explicit_voice_id=args.voice_id)
        record = assigned["record"] if assigned else None
        if record:
            return normalize_voice_record(record), assigned["selection_mode"]

    if args.reference_wav:
        record = register_voice(
            runtime,
            scope=args.scope if not args.job_id else "job",
            job_id=job_paths.job_id if args.job_id else None,
            voice_name=normalize_text(args.voice_name).replace(" ", "_"),
            voice_description="Voice clone manual.",
            model_name=resolved_model_path,
            language=args.reference_language,
            seed=args.seed,
            voice_instruct="",
            reference_file=str(Path(args.reference_wav)),
            reference_text_file=None,
            voice_mode="reference_conditioned",
            tts_strategy_default="reference_conditioned",
            supports_reference_conditioning=True,
            supports_clone_prompt=False,
            engine="voice_clone",
            voice_id=args.voice_id,
            notes="Registrada desde generate_audio_from_prompt.",
        )
        if args.job_id:
            assign_voice_to_job(job_paths, record, selection_mode="manual")
        return normalize_voice_record(record), "manual"

    raise RuntimeError("No hay una voz resoluble. Usa --voice-id o --reference-wav.")


def main() -> None:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)
    validate_voice_index(get_runtime_paths())

    try:
        if not args.job_id and not args.text:
            raise RuntimeError("Debes indicar --job-id o --text")

        set_global_seed(args.seed)
        model, resolved_model_path = load_model(args.model_path, args.device, args.use_flash_attn)
        generate_clone = getattr(model, "generate_voice_clone", None)
        if not callable(generate_clone):
            raise RuntimeError("La libreria qwen_tts no expone generate_voice_clone()")

        if args.job_id:
            job_paths = ensure_job_structure(build_job_paths(args.job_id, get_runtime_paths()))
            text = read_job_text(job_paths)
            if not text:
                raise RuntimeError(f"{job_paths.script} no contiene guion_narrado")
            output_path = job_paths.audio
            if output_path.exists() and not args.overwrite:
                raise RuntimeError(f"Ya existe {output_path}. Usa --overwrite para regenerarlo.")
        else:
            job_paths = None
            text = normalize_text(args.text)
            output_path = Path(args.output) if args.output else PROJECT_DIR / "outputs" / "voice_clone_preview.wav"

        record, selection_mode = resolve_voice(job_paths, args, resolved_model_path)
        reference_wav = Path(args.reference_wav or record.get("reference_file") or "")
        reference_text = args.reference_text
        prompt_input = Path(args.voice_clone_prompt) if args.voice_clone_prompt else (
            Path(record["voice_clone_prompt_path"]) if record.get("voice_clone_prompt_path") else None
        )
        prompt_output = Path(args.prompt_output) if args.prompt_output else None

        prompt_items, saved_prompt_path = build_or_load_prompt(
            model=model,
            reference_wav=reference_wav,
            reference_text=reference_text,
            x_vector_only_mode=args.x_vector_only_mode,
            prompt_input=prompt_input,
            prompt_output=prompt_output,
            save_prompt=args.save_prompt,
        )

        wavs, sample_rate = generate_clone(
            text=text,
            language=args.language,
            voice_clone_prompt=prompt_items,
            non_streaming_mode=True,
        )
        if not wavs:
            raise RuntimeError("generate_voice_clone() no devolvio audio")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), wavs[0], sample_rate)
        log(f"[clone] Audio final guardado en {output_path}")
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        if record:
            updated_record = register_voice(
                get_runtime_paths(),
                scope=record["scope"],
                job_id=record.get("job_id"),
                voice_name=record["voice_name"],
                voice_description=record["voice_description"],
                model_name=record["model_name"],
                language=record["language"],
                seed=record.get("seed"),
                voice_instruct=record.get("voice_instruct", ""),
                reference_file=str(reference_wav),
                reference_text_file=None,
                voice_clone_prompt_path=saved_prompt_path or record.get("voice_clone_prompt_path"),
                voice_mode="clone_prompt" if (saved_prompt_path or record.get("voice_clone_prompt_path")) else "reference_conditioned",
                tts_strategy_default="clone_prompt" if (saved_prompt_path or record.get("voice_clone_prompt_path")) else "reference_conditioned",
                supports_reference_conditioning=True,
                supports_clone_prompt=bool(saved_prompt_path or record.get("voice_clone_prompt_path")),
                engine="voice_clone",
                voice_id=record["voice_id"],
                notes=record.get("notes", ""),
            )
            if job_paths:
                assign_voice_to_job(job_paths, updated_record, selection_mode=selection_mode)
                update_job_artifact(
                    job_paths,
                    artifact_type="audio",
                    file_path=get_runtime_paths().to_dataset_relative(job_paths.audio),
                    generated_at=generated_at,
                )
                update_job_audio_synthesis(
                    job_paths,
                    voice_record=updated_record,
                    selection_mode=selection_mode,
                    strategy_requested="clone_prompt" if updated_record.get("voice_clone_prompt_path") else "reference_conditioned",
                    strategy_used="clone_prompt" if updated_record.get("voice_clone_prompt_path") else "reference_conditioned",
                    fallback_used=False,
                    fallback_reason="",
                    engine_used="voice_clone",
                    reference_conditioning_used=not bool(updated_record.get("voice_clone_prompt_path")),
                    clone_prompt_used=bool(updated_record.get("voice_clone_prompt_path")),
                    voice_preset_used="",
                    generated_at=generated_at,
                )
                update_status(
                    job_paths.status,
                    audio_generated=True,
                    last_step="audio_generated_voice_clone",
                    voice_id=updated_record["voice_id"],
                    voice_scope=updated_record["scope"],
                    voice_source=selection_mode,
                    voice_name=updated_record["voice_name"],
                    voice_selection_mode=selection_mode,
                    voice_model_name=updated_record["model_name"],
                    voice_reference_file=updated_record.get("reference_file", "") or "",
                    voice_mode=updated_record.get("voice_mode", ""),
                    tts_strategy_requested="clone_prompt" if updated_record.get("voice_clone_prompt_path") else "reference_conditioned",
                    tts_strategy_used="clone_prompt" if updated_record.get("voice_clone_prompt_path") else "reference_conditioned",
                    tts_fallback_used=False,
                    tts_fallback_reason="",
                    audio_file=get_runtime_paths().to_dataset_relative(job_paths.audio),
                    audio_generated_at=generated_at,
                )

    except Exception as exc:
        if args.job_id:
            job_paths = ensure_job_structure(build_job_paths(args.job_id, get_runtime_paths()))
            update_status(job_paths.status, audio_generated=False, last_step="audio_error_voice_clone")
        log(f"[clone] Error: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
