import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from job_paths import JobPaths, RuntimePaths, first_existing_path

DEFAULT_GLOBAL_VOICE_ID_ENV = "VIDEO_DEFAULT_VOICE_ID"
DEFAULT_VOICE_MODE = "design_only"
DEFAULT_TTS_STRATEGY = "description_seed_preset"
VOICE_MODES = {"design_only", "reference_conditioned", "clone_prompt"}
TTS_STRATEGIES = {
    "description_seed_preset",
    "reference_conditioned",
    "clone_prompt",
    "legacy_preset_fallback",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _normalize_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "si"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return bool(value)


def resolve_voice_mode(record: dict[str, Any] | None) -> str:
    payload = record or {}
    candidate = str(payload.get("voice_mode", "")).strip().lower()
    if candidate in VOICE_MODES:
        return candidate
    if payload.get("voice_clone_prompt_path"):
        return "clone_prompt"
    if payload.get("engine") == "voice_clone":
        return "reference_conditioned"
    return DEFAULT_VOICE_MODE


def resolve_tts_strategy_default(record: dict[str, Any] | None) -> str:
    payload = record or {}
    candidate = str(payload.get("tts_strategy_default", "")).strip().lower()
    if candidate in TTS_STRATEGIES:
        return candidate
    voice_mode = resolve_voice_mode(payload)
    if voice_mode == "clone_prompt":
        return "clone_prompt"
    if voice_mode == "reference_conditioned":
        return "reference_conditioned"
    return DEFAULT_TTS_STRATEGY


def normalize_voice_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    normalized["voice_mode"] = resolve_voice_mode(normalized)
    normalized["tts_strategy_default"] = resolve_tts_strategy_default(normalized)
    normalized["reference_text_file"] = normalized.get("reference_text_file")
    normalized["supports_reference_conditioning"] = _normalize_bool(
        normalized.get("supports_reference_conditioning"),
        default=normalized["voice_mode"] in {"reference_conditioned", "clone_prompt"},
    )
    normalized["supports_clone_prompt"] = _normalize_bool(
        normalized.get("supports_clone_prompt"),
        default=normalized["voice_mode"] == "clone_prompt" or bool(normalized.get("voice_clone_prompt_path")),
    )
    normalized["voice_preset"] = str(normalized.get("voice_preset", "") or "").strip()
    normalized["engine"] = str(normalized.get("engine", "") or "").strip()
    return normalized


def load_voice_index(runtime: RuntimePaths) -> dict[str, Any]:
    payload = safe_read_json(runtime.voices_index_file, default=None)
    if payload:
        payload.setdefault("registry_version", "1.0")
        payload.setdefault("voices", [])
        payload.setdefault("updated_at", "")
        payload["voices"] = [normalize_voice_record(record) for record in payload["voices"]]
        return payload
    return {"registry_version": "1.0", "voices": [], "updated_at": ""}


def save_voice_index(runtime: RuntimePaths, payload: dict[str, Any]) -> None:
    payload["updated_at"] = now_iso()
    safe_write_json(runtime.voices_index_file, payload)


def _voice_record_path(runtime: RuntimePaths, voice_id: str) -> Path:
    return runtime.voices_root / voice_id / "voice.json"


def get_voice(runtime: RuntimePaths, voice_id: str) -> dict[str, Any] | None:
    for record in load_voice_index(runtime)["voices"]:
        if record.get("voice_id") == voice_id:
            record_path = _voice_record_path(runtime, voice_id)
            file_record = safe_read_json(record_path, default=None)
            return normalize_voice_record(file_record or record)

    record_path = _voice_record_path(runtime, voice_id)
    payload = safe_read_json(record_path, default=None)
    return normalize_voice_record(payload) if payload else None


def _next_voice_id(runtime: RuntimePaths, prefix: str) -> str:
    suffixes: list[int] = []
    for record in load_voice_index(runtime)["voices"]:
        voice_id = str(record.get("voice_id", ""))
        if voice_id.startswith(prefix):
            suffix = voice_id[len(prefix):]
            if suffix.isdigit():
                suffixes.append(int(suffix))
    return f"{prefix}{max(suffixes, default=0) + 1:04d}"


def generate_voice_id(runtime: RuntimePaths, scope: str, job_id: str | None = None) -> str:
    if scope == "global":
        return _next_voice_id(runtime, "voice_global_")
    if scope == "job":
        if not job_id:
            raise ValueError("job_id es obligatorio para voces scope=job.")
        return _next_voice_id(runtime, f"voice_job_{job_id}_")
    raise ValueError(f"Scope de voz no soportado: {scope}")


def upsert_voice(runtime: RuntimePaths, record: dict[str, Any]) -> dict[str, Any]:
    voice_id = str(record["voice_id"]).strip()
    if not voice_id:
        raise ValueError("voice_id es obligatorio.")

    stored = normalize_voice_record({
        "voice_id": voice_id,
        "scope": record.get("scope", "global"),
        "job_id": record.get("job_id"),
        "voice_name": record.get("voice_name", voice_id),
        "voice_description": record.get("voice_description", ""),
        "model_name": record.get("model_name", ""),
        "language": record.get("language", ""),
        "seed": record.get("seed"),
        "voice_instruct": record.get("voice_instruct", ""),
        "reference_file": record.get("reference_file"),
        "reference_text_file": record.get("reference_text_file"),
        "voice_clone_prompt_path": record.get("voice_clone_prompt_path"),
        "voice_preset": record.get("voice_preset", ""),
        "voice_mode": record.get("voice_mode"),
        "tts_strategy_default": record.get("tts_strategy_default"),
        "supports_reference_conditioning": record.get("supports_reference_conditioning"),
        "supports_clone_prompt": record.get("supports_clone_prompt"),
        "engine": record.get("engine", ""),
        "status": record.get("status", "active"),
        "notes": record.get("notes", ""),
        "created_at": record.get("created_at") or now_iso(),
        "updated_at": now_iso(),
    })

    voice_dir = runtime.voices_root / voice_id
    voice_dir.mkdir(parents=True, exist_ok=True)
    safe_write_json(voice_dir / "voice.json", stored)

    index_payload = load_voice_index(runtime)
    voices = [row for row in index_payload["voices"] if row.get("voice_id") != voice_id]
    voices.append(stored)
    voices.sort(key=lambda row: str(row.get("voice_id", "")))
    index_payload["voices"] = voices
    save_voice_index(runtime, index_payload)
    return stored


def register_voice(
    runtime: RuntimePaths,
    *,
    scope: str,
    voice_name: str,
    voice_description: str,
    model_name: str,
    language: str,
    seed: int | None,
    voice_instruct: str,
    reference_file: str | None = None,
    reference_text_file: str | None = None,
    job_id: str | None = None,
    voice_clone_prompt_path: str | None = None,
    voice_preset: str = "",
    voice_mode: str | None = None,
    tts_strategy_default: str | None = None,
    supports_reference_conditioning: bool | None = None,
    supports_clone_prompt: bool | None = None,
    engine: str = "",
    status: str = "active",
    notes: str = "",
    voice_id: str | None = None,
) -> dict[str, Any]:
    final_voice_id = voice_id or generate_voice_id(runtime, scope=scope, job_id=job_id)
    existing = get_voice(runtime, final_voice_id)

    return upsert_voice(
        runtime,
        {
            "voice_id": final_voice_id,
            "scope": scope,
            "job_id": job_id,
            "voice_name": voice_name,
            "voice_description": voice_description,
            "model_name": model_name,
            "language": language,
            "seed": seed,
            "voice_instruct": voice_instruct,
            "reference_file": reference_file,
            "reference_text_file": reference_text_file,
            "voice_clone_prompt_path": voice_clone_prompt_path,
            "voice_preset": voice_preset,
            "voice_mode": voice_mode,
            "tts_strategy_default": tts_strategy_default,
            "supports_reference_conditioning": supports_reference_conditioning,
            "supports_clone_prompt": supports_clone_prompt,
            "engine": engine,
            "status": status,
            "notes": notes,
            "created_at": existing.get("created_at") if existing else None,
        },
    )


def load_job_document(job_paths: JobPaths) -> dict[str, Any]:
    current = safe_read_json(job_paths.job_file, default=None)
    if current:
        current.setdefault("job_id", job_paths.job_id)
        current.setdefault("job_schema_version", "2.0")
        current.setdefault("voice", {})
        current.setdefault("artifacts", {})
        current.setdefault("audio_synthesis", {})
        return current

    return {
        "job_id": job_paths.job_id,
        "job_schema_version": "2.0",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "voice": {},
        "artifacts": {},
        "audio_synthesis": {},
    }


def save_job_document(job_paths: JobPaths, document: dict[str, Any]) -> dict[str, Any]:
    document["updated_at"] = now_iso()
    safe_write_json(job_paths.job_file, document)
    return document


def assign_voice_to_job(
    job_paths: JobPaths,
    voice_record: dict[str, Any],
    *,
    selection_mode: str,
    notes: str = "",
) -> dict[str, Any]:
    document = load_job_document(job_paths)
    document["voice"] = {
        "voice_id": voice_record.get("voice_id"),
        "scope": voice_record.get("scope"),
        "job_id": voice_record.get("job_id"),
        "voice_mode": voice_record.get("voice_mode"),
        "tts_strategy_default": voice_record.get("tts_strategy_default"),
        "voice_source": selection_mode,
        "selection_mode": selection_mode,
        "voice_name": voice_record.get("voice_name"),
        "voice_description": voice_record.get("voice_description"),
        "model_name": voice_record.get("model_name"),
        "language": voice_record.get("language"),
        "seed": voice_record.get("seed"),
        "voice_instruct": voice_record.get("voice_instruct"),
        "reference_file": voice_record.get("reference_file"),
        "reference_text_file": voice_record.get("reference_text_file"),
        "voice_clone_prompt_path": voice_record.get("voice_clone_prompt_path"),
        "supports_reference_conditioning": voice_record.get("supports_reference_conditioning"),
        "supports_clone_prompt": voice_record.get("supports_clone_prompt"),
        "voice_preset": voice_record.get("voice_preset", ""),
        "engine": voice_record.get("engine"),
        "status": voice_record.get("status"),
        "notes": notes,
        "assigned_at": now_iso(),
    }
    return save_job_document(job_paths, document)


def update_job_audio_synthesis(
    job_paths: JobPaths,
    *,
    voice_record: dict[str, Any],
    selection_mode: str,
    strategy_requested: str,
    strategy_used: str,
    fallback_used: bool,
    fallback_reason: str = "",
    engine_used: str = "",
    reference_conditioning_used: bool = False,
    clone_prompt_used: bool = False,
    voice_preset_used: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    document = load_job_document(job_paths)
    document["audio_synthesis"] = {
        "voice_id": voice_record.get("voice_id"),
        "voice_scope": voice_record.get("scope"),
        "voice_source": selection_mode,
        "voice_mode": voice_record.get("voice_mode"),
        "tts_strategy_requested": strategy_requested,
        "tts_strategy_used": strategy_used,
        "tts_fallback_used": bool(fallback_used),
        "tts_fallback_reason": fallback_reason,
        "engine_used": engine_used or voice_record.get("engine", ""),
        "reference_conditioning_used": bool(reference_conditioning_used),
        "clone_prompt_used": bool(clone_prompt_used),
        "voice_preset_used": voice_preset_used,
        "generated_at": generated_at or now_iso(),
    }
    return save_job_document(job_paths, document)


def update_job_artifact(
    job_paths: JobPaths,
    *,
    artifact_type: str,
    file_path: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    document = load_job_document(job_paths)
    artifacts = document.setdefault("artifacts", {})
    artifacts[artifact_type] = {
        "file": file_path,
        "generated_at": generated_at or now_iso(),
    }
    return save_job_document(job_paths, document)


def resolve_job_voice_assignment(
    runtime: RuntimePaths,
    job_paths: JobPaths,
    *,
    explicit_voice_id: str | None = None,
) -> dict[str, Any] | None:
    if explicit_voice_id:
        record = get_voice(runtime, explicit_voice_id)
        if not record:
            raise RuntimeError(f"No existe voice_id={explicit_voice_id} en el registry.")
        return {"record": record, "selection_mode": "manual"}

    job_document = load_job_document(job_paths)
    job_voice = job_document.get("voice") or {}
    voice_id = str(job_voice.get("voice_id", "")).strip()
    if voice_id:
        record = get_voice(runtime, voice_id)
        if record:
            return {
                "record": record,
                "selection_mode": job_voice.get("selection_mode", "job_assignment"),
            }

    default_global_voice_id = os.getenv(DEFAULT_GLOBAL_VOICE_ID_ENV, "").strip()
    if default_global_voice_id:
        record = get_voice(runtime, default_global_voice_id)
        if not record:
            raise RuntimeError(
                f"{DEFAULT_GLOBAL_VOICE_ID_ENV} apunta a una voz inexistente: {default_global_voice_id}"
            )
        return {"record": record, "selection_mode": "global_default"}

    return None


def resolve_job_input_path(primary: Path, legacy_candidates: list[Path]) -> Path:
    return first_existing_path(primary, legacy_candidates)


def validate_voice_record(record: dict[str, Any]) -> None:
    normalized = normalize_voice_record(record)
    required_keys = {
        "voice_id",
        "scope",
        "voice_name",
        "voice_description",
        "model_name",
        "language",
        "voice_instruct",
        "status",
        "created_at",
        "updated_at",
    }
    missing = [key for key in sorted(required_keys) if key not in normalized]
    if missing:
        raise ValueError(f"Voice record invalido. Faltan claves: {', '.join(missing)}")
    if normalized["scope"] not in {"global", "job"}:
        raise ValueError(f"Scope de voz invalido: {normalized['scope']}")
    if normalized["voice_mode"] not in VOICE_MODES:
        raise ValueError(f"voice_mode invalido: {normalized['voice_mode']}")
    if normalized["tts_strategy_default"] not in TTS_STRATEGIES:
        raise ValueError(f"tts_strategy_default invalido: {normalized['tts_strategy_default']}")


def validate_voice_index(runtime: RuntimePaths) -> None:
    payload = load_voice_index(runtime)
    if payload.get("registry_version") != "1.0":
        raise ValueError(f"registry_version no soportado: {payload.get('registry_version')}")
    seen_ids: set[str] = set()
    for record in payload.get("voices", []):
        validate_voice_record(record)
        voice_id = str(record["voice_id"])
        if voice_id in seen_ids:
            raise ValueError(f"voice_id duplicado en registry: {voice_id}")
        seen_ids.add(voice_id)
