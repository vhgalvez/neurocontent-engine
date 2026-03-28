import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from job_paths import JobPaths, RuntimePaths, first_existing_path

DEFAULT_GLOBAL_VOICE_ID_ENV = "VIDEO_DEFAULT_VOICE_ID"


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


def load_voice_index(runtime: RuntimePaths) -> dict[str, Any]:
    payload = safe_read_json(runtime.voices_index_file, default=None)
    if payload:
        payload.setdefault("registry_version", "1.0")
        payload.setdefault("voices", [])
        return payload
    return {"registry_version": "1.0", "voices": []}


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
            return file_record or record

    record_path = _voice_record_path(runtime, voice_id)
    return safe_read_json(record_path, default=None)


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

    stored = {
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
        "voice_clone_prompt_path": record.get("voice_clone_prompt_path"),
        "voice_preset": record.get("voice_preset", ""),
        "engine": record.get("engine", ""),
        "status": record.get("status", "active"),
        "notes": record.get("notes", ""),
        "created_at": record.get("created_at") or now_iso(),
        "updated_at": now_iso(),
    }

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
    job_id: str | None = None,
    voice_clone_prompt_path: str | None = None,
    voice_preset: str = "",
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
            "voice_clone_prompt_path": voice_clone_prompt_path,
            "voice_preset": voice_preset,
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
        return current

    return {
        "job_id": job_paths.job_id,
        "job_schema_version": "2.0",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "voice": {},
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
        "selection_mode": selection_mode,
        "voice_name": voice_record.get("voice_name"),
        "voice_description": voice_record.get("voice_description"),
        "model_name": voice_record.get("model_name"),
        "language": voice_record.get("language"),
        "seed": voice_record.get("seed"),
        "voice_instruct": voice_record.get("voice_instruct"),
        "reference_file": voice_record.get("reference_file"),
        "voice_clone_prompt_path": voice_record.get("voice_clone_prompt_path"),
        "engine": voice_record.get("engine"),
        "status": voice_record.get("status"),
        "notes": notes,
        "assigned_at": now_iso(),
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
