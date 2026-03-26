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

os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

PROJECT_DIR = Path(__file__).resolve().parents[1]
JOBS_DIR = PROJECT_DIR / "jobs"
DEFAULT_BASE_MODEL_PATH = os.getenv(
    "QWEN_TTS_BASE_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base",
)
DEFAULT_REFERENCE_ROOT = os.getenv(
    "QWEN_TTS_REFERENCE_ROOT",
    str(PROJECT_DIR / "assets" / "voices"),
)
DEFAULT_LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Spanish")
DEFAULT_REFERENCE_LANGUAGE = os.getenv("QWEN_TTS_REFERENCE_LANGUAGE", DEFAULT_LANGUAGE)
DEFAULT_DEVICE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()
DEFAULT_OVERWRITE = os.getenv("QWEN_TTS_OVERWRITE", "false").lower() == "true"
DEFAULT_USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN", "false").lower() == "true"
DEFAULT_X_VECTOR_ONLY = os.getenv("QWEN_TTS_X_VECTOR_ONLY_MODE", "false").lower() == "true"
DEFAULT_VOICE_NAME = os.getenv("QWEN_TTS_REFERENCE_NAME", "voz_principal")
DEFAULT_SEED = int(os.getenv("QWEN_TTS_SEED", "424242"))


def log(message: str) -> None:
    print(message, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def safe_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


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
        "voice_model_path": "",
        "voice_flow": "",
        "voice_reference_path": "",
        "voice_clone_prompt_path": "",
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
        raise RuntimeError(f"No existe snapshots en: {base}")
    snapshots = sorted(
        (path for path in snapshots_dir.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for snapshot in snapshots:
        if (snapshot / "config.json").exists():
            return str(snapshot)
    raise RuntimeError(f"No se encontro snapshot valido con config.json en {snapshots_dir}")


def get_device_and_dtype(device_mode: str) -> tuple[str, torch.dtype]:
    if device_mode == "cpu":
        return "cpu", torch.float32
    if device_mode == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("QWEN_TTS_DEVICE=cuda pero CUDA no esta disponible")
        return "cuda:0", torch.bfloat16
    if torch.cuda.is_available():
        return "cuda:0", torch.bfloat16
    return "cpu", torch.float32


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

    log(f"[clone] Modelo Base: {resolved_model_path}")
    log(f"[clone] device_map={device_map} dtype={dtype} flash_attn={use_flash_attn}")
    model = Qwen3TTSModel.from_pretrained(resolved_model_path, **kwargs)
    if getattr(model.model, "tts_model_type", None) != "base":
        raise RuntimeError(
            "El modelo cargado no es Base. "
            f"tts_model_type={getattr(model.model, 'tts_model_type', 'desconocido')}"
        )
    return model, resolved_model_path


def resolve_callable(model, names: list[str], label: str) -> callable:
    for name in names:
        candidate = getattr(model, name, None)
        if callable(candidate):
            log(f"[clone] Metodo {label}: {name}")
            return candidate
    raise RuntimeError(f"No se encontro un metodo compatible para {label}: {', '.join(names)}")


def voice_dir_for_name(reference_root: Path, voice_name: str) -> Path:
    return reference_root / voice_name


def serialize_prompt_items(items: list[VoiceClonePromptItem]) -> list[dict]:
    serialized = []
    for item in items:
        serialized.append(
            {
                "ref_code": item.ref_code.detach().cpu().tolist() if item.ref_code is not None else None,
                "ref_spk_embedding": item.ref_spk_embedding.detach().cpu().tolist(),
                "x_vector_only_mode": bool(item.x_vector_only_mode),
                "icl_mode": bool(item.icl_mode),
                "ref_text": item.ref_text,
            }
        )
    return serialized


def deserialize_prompt_items(data: list[dict]) -> list[VoiceClonePromptItem]:
    items: list[VoiceClonePromptItem] = []
    for row in data:
        ref_code = row.get("ref_code")
        ref_spk_embedding = row.get("ref_spk_embedding")
        if ref_spk_embedding is None:
            raise RuntimeError("voice_clone_prompt serializado invalido: falta ref_spk_embedding")
        items.append(
            VoiceClonePromptItem(
                ref_code=torch.tensor(ref_code, dtype=torch.long) if ref_code is not None else None,
                ref_spk_embedding=torch.tensor(ref_spk_embedding, dtype=torch.float32),
                x_vector_only_mode=bool(row.get("x_vector_only_mode", False)),
                icl_mode=bool(row.get("icl_mode", False)),
                ref_text=row.get("ref_text"),
            )
        )
    return items


def save_prompt_json(path: Path, prompt_items: list[VoiceClonePromptItem], metadata: dict) -> None:
    safe_write_json(
        path,
        {
            "format": "qwen3_voice_clone_prompt_items",
            "items": serialize_prompt_items(prompt_items),
            "metadata": metadata,
        },
    )


def load_prompt_json(path: Path) -> list[VoiceClonePromptItem]:
    payload = safe_read_json(path, default=None)
    if not payload:
        raise RuntimeError(f"No se pudo leer voice_clone_prompt desde {path}")
    if payload.get("format") != "qwen3_voice_clone_prompt_items":
        raise RuntimeError(f"Formato de prompt no soportado en {path}")
    return deserialize_prompt_items(payload.get("items", []))


def read_job_text(job_id: str) -> str:
    script_path = JOBS_DIR / job_id / "script.json"
    script_data = safe_read_json(script_path, default={}) or {}
    return normalize_text(script_data.get("guion_narrado", ""))


def read_job_voice_config(job_id: str) -> dict:
    return safe_read_json(JOBS_DIR / job_id / "voice.json", default={}) or {}


def resolve_job_reference_config(job_id: str, args: argparse.Namespace) -> dict:
    job_config = read_job_voice_config(job_id)
    voice_name = normalize_text(job_config.get("voice_name", args.voice_name or DEFAULT_VOICE_NAME)).replace(" ", "_")
    reference_root = Path(args.reference_root)
    voice_dir = reference_root / voice_name if voice_name else None

    reference_wav = job_config.get("reference_wav")
    if not reference_wav and voice_dir:
        reference_wav = str(voice_dir / "reference.wav")

    reference_text = job_config.get("reference_text")
    if not reference_text and voice_dir and (voice_dir / "reference.txt").exists():
        reference_text = safe_read_text(voice_dir / "reference.txt")

    prompt_json = job_config.get("voice_clone_prompt_path")
    if not prompt_json and voice_dir and (voice_dir / "voice_clone_prompt.json").exists():
        prompt_json = str(voice_dir / "voice_clone_prompt.json")

    return {
        "voice_name": voice_name,
        "reference_wav": reference_wav,
        "reference_text": reference_text,
        "voice_clone_prompt_path": prompt_json,
        "x_vector_only_mode": bool(job_config.get("x_vector_only_mode", args.x_vector_only_mode)),
        "reference_language": job_config.get("reference_language", args.reference_language),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera audio consistente con Qwen3-TTS Base usando voice clone prompt."
    )
    parser.add_argument("--job-id", help="Job a procesar leyendo jobs/<job_id>/script.json.")
    parser.add_argument("--text", help="Texto directo para sintetizar sin usar job.")
    parser.add_argument("--output", help="Ruta de salida para --text. Para jobs se usa jobs/<id>/audio/narration.wav.")
    parser.add_argument("--voice-name", default=DEFAULT_VOICE_NAME, help="Nombre de voz bajo assets/voices.")
    parser.add_argument("--reference-root", default=DEFAULT_REFERENCE_ROOT, help="Raiz de assets/voices.")
    parser.add_argument("--reference-wav", help="Ruta explicita al wav de referencia.")
    parser.add_argument("--reference-text", help="Texto exacto del wav de referencia.")
    parser.add_argument("--voice-clone-prompt", help="JSON previamente serializado.")
    parser.add_argument("--save-prompt", action="store_true", help="Guarda el prompt serializado si se crea.")
    parser.add_argument("--prompt-output", help="Ruta explicita para guardar el prompt serializado.")
    parser.add_argument("--x-vector-only-mode", action="store_true", default=DEFAULT_X_VECTOR_ONLY, help="Clona solo por speaker embedding.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Idioma del texto final.")
    parser.add_argument("--reference-language", default=DEFAULT_REFERENCE_LANGUAGE, help="Idioma del audio de referencia.")
    parser.add_argument("--model-path", default=DEFAULT_BASE_MODEL_PATH, help="Ruta del modelo Base.")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["auto", "cpu", "cuda"], help="Device.")
    parser.add_argument("--overwrite", action="store_true", default=DEFAULT_OVERWRITE, help="Sobrescribe narration.wav.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed global.")
    parser.add_argument(
        "--use-flash-attn",
        action="store_true",
        default=DEFAULT_USE_FLASH_ATTN,
        help="Usa flash_attention_2 si esta disponible.",
    )
    return parser.parse_args()


def build_or_load_prompt(
    model,
    create_prompt_method,
    reference_root: Path,
    voice_name: str,
    reference_wav: Path,
    reference_text: str | None,
    x_vector_only_mode: bool,
    prompt_input_path: Path | None,
    prompt_output_path: Path | None,
    save_prompt: bool,
) -> tuple[list[VoiceClonePromptItem], str | None]:
    if prompt_input_path:
        log(f"[clone] Cargando voice_clone_prompt desde {prompt_input_path}")
        return load_prompt_json(prompt_input_path), str(prompt_input_path)

    if not reference_wav.exists():
        raise RuntimeError(f"No existe reference.wav: {reference_wav}")

    if not x_vector_only_mode and not normalize_text(reference_text or ""):
        raise RuntimeError("reference_text es obligatorio cuando x_vector_only_mode=false")

    prompt_items = create_prompt_method(
        ref_audio=str(reference_wav),
        ref_text=reference_text,
        x_vector_only_mode=x_vector_only_mode,
    )
    if not prompt_items:
        raise RuntimeError("create_voice_clone_prompt() no devolvio items")

    saved_path = None
    if save_prompt:
        if prompt_output_path is None:
            prompt_output_path = voice_dir_for_name(reference_root, voice_name) / "voice_clone_prompt.json"
        save_prompt_json(
            prompt_output_path,
            prompt_items,
            metadata={
                "voice_name": voice_name,
                "reference_wav": str(reference_wav),
                "reference_text": reference_text,
                "x_vector_only_mode": x_vector_only_mode,
                "saved_at": now_iso(),
            },
        )
        saved_path = str(prompt_output_path)
        log(f"[clone] voice_clone_prompt guardado en {prompt_output_path}")

    return prompt_items, saved_path


def main() -> None:
    args = parse_args()

    try:
        if not args.job_id and not args.text:
            raise RuntimeError("Debes indicar --job-id o --text")

        set_global_seed(args.seed)
        model, resolved_model_path = load_model(
            model_path=args.model_path,
            device_mode=args.device,
            use_flash_attn=args.use_flash_attn,
        )
        create_prompt_method = resolve_callable(
            model,
            ["create_voice_clone_prompt"],
            "create_voice_clone_prompt",
        )
        generate_clone_method = resolve_callable(
            model,
            ["generate_voice_clone"],
            "generate_voice_clone",
        )

        if args.job_id:
            text = read_job_text(args.job_id)
            if not text:
                raise RuntimeError(f"jobs/{args.job_id}/script.json no contiene guion_narrado")
            job_voice = resolve_job_reference_config(args.job_id, args)
            voice_name = job_voice["voice_name"]
            reference_wav = Path(args.reference_wav or job_voice["reference_wav"])
            reference_text = args.reference_text or job_voice["reference_text"]
            prompt_input = Path(args.voice_clone_prompt or job_voice["voice_clone_prompt_path"]) if (args.voice_clone_prompt or job_voice["voice_clone_prompt_path"]) else None
            x_vector_only_mode = bool(job_voice["x_vector_only_mode"])
            output_path = JOBS_DIR / args.job_id / "audio" / "narration.wav"
            if output_path.exists() and not args.overwrite:
                raise RuntimeError(f"Ya existe {output_path}. Usa --overwrite para regenerarlo.")
            prompt_output_path = Path(args.prompt_output) if args.prompt_output else None
        else:
            text = normalize_text(args.text)
            if not text:
                raise RuntimeError("El texto no puede estar vacio")
            voice_name = normalize_text(args.voice_name).replace(" ", "_")
            reference_wav = Path(args.reference_wav or (Path(args.reference_root) / voice_name / "reference.wav"))
            if args.reference_text:
                reference_text = args.reference_text
            else:
                default_reference_text_path = Path(args.reference_root) / voice_name / "reference.txt"
                reference_text = safe_read_text(default_reference_text_path) if default_reference_text_path.exists() else None
            prompt_input = Path(args.voice_clone_prompt) if args.voice_clone_prompt else None
            x_vector_only_mode = args.x_vector_only_mode
            output_path = Path(args.output) if args.output else PROJECT_DIR / "outputs" / "voice_clone_preview.wav"
            prompt_output_path = Path(args.prompt_output) if args.prompt_output else None

        prompt_items, saved_prompt_path = build_or_load_prompt(
            model=model,
            create_prompt_method=create_prompt_method,
            reference_root=Path(args.reference_root),
            voice_name=voice_name,
            reference_wav=reference_wav,
            reference_text=reference_text,
            x_vector_only_mode=x_vector_only_mode,
            prompt_input_path=prompt_input,
            prompt_output_path=prompt_output_path,
            save_prompt=args.save_prompt,
        )

        log(f"[clone] Generando audio final para voice_name={voice_name}")
        wavs, sample_rate = generate_clone_method(
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

        if args.job_id:
            update_status(
                JOBS_DIR / args.job_id / "status.json",
                audio_generated=True,
                last_step="audio_generated_voice_clone",
                voice_flow="voice_clone",
                voice_model_path=resolved_model_path,
                voice_reference_path=str(reference_wav),
                voice_clone_prompt_path=saved_prompt_path or (str(prompt_input) if prompt_input else ""),
            )

    except Exception as exc:
        if args.job_id:
            update_status(
                JOBS_DIR / args.job_id / "status.json",
                audio_generated=False,
                last_step="audio_error_voice_clone",
            )
        log(f"[clone] Error: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
