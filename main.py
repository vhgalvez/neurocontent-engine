import csv
from typing import Any, Dict, List

from config import DATA_FILE, JOBS_DIR, OVERWRITE_MANIFEST, OVERWRITE_SCRIPT
from director import (
    OllamaError,
    build_index_row,
    build_visual_manifest,
    get_job_paths,
    pad_job_id,
    safe_read_json,
    safe_write_json,
    sync_status_with_files,
    update_status,
    validate_script_data,
    write_index,
    generate_script,
)

REQUIRED_COLUMNS = {
    "id",
    "estado",
    "nicho",
    "subnicho",
    "idioma",
    "plataforma",
    "formato",
    "duracion_seg",
    "objetivo",
    "avatar",
    "audiencia",
    "dolor_principal",
    "deseo_principal",
    "miedo_principal",
    "angulo",
    "tipo_hook",
    "historia_base",
    "idea_central",
    "tesis",
    "enemigo",
    "error_comun",
    "transformacion_prometida",
    "tono",
    "emocion_principal",
    "emocion_secundaria",
    "nivel_intensidad",
    "cta_tipo",
    "cta_texto",
    "prohibido",
    "keywords",
    "referencias",
    "notas_direccion",
    "ritmo",
    "estilo_narracion",
    "tipo_cierre",
    "nivel_agresividad_copy",
    "objetivo_retencion",
}


def _clean_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value.strip() if isinstance(value, str) else value
        for key, value in row.items()
    }


def _validate_headers(fieldnames: List[str] | None) -> None:
    if not fieldnames:
        raise ValueError(f"El archivo CSV está vacío o no tiene cabeceras: {DATA_FILE}")

    missing = sorted(REQUIRED_COLUMNS - set(fieldnames))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Faltan columnas obligatorias en {DATA_FILE}: {missing_text}")


def load_briefs() -> List[Dict[str, Any]]:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"No existe el archivo de briefs: {DATA_FILE}. "
            "Crea data\\ideas.csv antes de ejecutar python main.py."
        )

    briefs: List[Dict[str, Any]] = []

    with DATA_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        _validate_headers(reader.fieldnames)

        for row in reader:
            clean_row = _clean_row(row)
            briefs.append(clean_row)

    return briefs


def load_pending_briefs() -> List[Dict[str, Any]]:
    return [brief for brief in load_briefs() if brief.get("estado", "").lower() == "pending"]


def _load_or_generate_script(brief: Dict[str, Any], paths: Dict[str, Any]) -> Dict[str, Any]:
    if paths["script"].exists() and not OVERWRITE_SCRIPT:
        update_status(paths["status"], script_generated=True, last_step="script_reused")
        existing_script = safe_read_json(paths["script"], default={}) or {}
        if not existing_script:
            raise ValueError(f"script.json vacio o invalido para job {paths['job_dir'].name}")
        validate_script_data(existing_script)
        return existing_script

    script = generate_script(brief)
    safe_write_json(paths["script"], script)
    update_status(paths["status"], script_generated=True, last_step="script_generated")
    return script


def _load_or_generate_manifest(
    brief: Dict[str, Any],
    script: Dict[str, Any],
    paths: Dict[str, Any],
    job_id: str,
) -> Dict[str, Any]:
    if paths["manifest"].exists() and not OVERWRITE_MANIFEST:
        update_status(paths["status"], visual_manifest_generated=True, last_step="manifest_reused")
        existing_manifest = safe_read_json(paths["manifest"], default={}) or {}
        if not existing_manifest:
            raise ValueError(f"visual_manifest.json vacio o invalido para job {job_id}")
        return existing_manifest

    manifest = build_visual_manifest(
        brief=brief,
        script=script,
        job_id=job_id,
        audio_path=paths["audio"],
        subtitles_path=paths["subtitles"],
    )
    safe_write_json(paths["manifest"], manifest)
    update_status(
        paths["status"],
        visual_manifest_generated=True,
        last_step="visual_manifest_generated",
    )
    return manifest


def process_brief(brief: Dict[str, Any]) -> Dict[str, Any]:
    job_id = pad_job_id(brief.get("id"))
    paths = get_job_paths(job_id)

    # The CSV remains the editorial source of truth, so brief.json is refreshed from it.
    safe_write_json(paths["brief"], brief)
    update_status(paths["status"], brief_created=True, last_step="brief_synced_from_csv")

    script = _load_or_generate_script(brief, paths)
    _load_or_generate_manifest(brief, script, paths, job_id)

    status = sync_status_with_files(paths)
    return build_index_row(brief, status, job_id)


def build_error_index_row(brief: Dict[str, Any], message: str) -> Dict[str, Any]:
    job_id = pad_job_id(brief.get("id"))
    paths = get_job_paths(job_id)

    safe_write_json(paths["brief"], brief)
    status = update_status(
        paths["status"],
        brief_created=True,
        script_generated=paths["script"].exists(),
        visual_manifest_generated=paths["manifest"].exists(),
        last_step=f"error: {message}",
    )
    return build_index_row(brief, status, job_id)


def build_derived_index(all_briefs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    index_rows: List[Dict[str, Any]] = []

    for brief in all_briefs:
        job_id = pad_job_id(brief.get("id"))
        paths = {
            "job_dir": JOBS_DIR / job_id,
            "brief": JOBS_DIR / job_id / "brief.json",
            "script": JOBS_DIR / job_id / "script.json",
            "status": JOBS_DIR / job_id / "status.json",
            "manifest": JOBS_DIR / job_id / "visual_manifest.json",
            "audio": JOBS_DIR / job_id / "audio" / "narration.wav",
            "subtitles": JOBS_DIR / job_id / "subtitles" / "narration.srt",
        }
        has_job_material = any(
            path.exists()
            for key, path in paths.items()
            if key != "job_dir"
        )

        if not has_job_material and brief.get("estado", "").lower() != "pending":
            continue

        if brief.get("estado", "").lower() == "pending" and not paths["brief"].exists():
            continue

        status = sync_status_with_files(paths)
        index_rows.append(build_index_row(brief, status, job_id))

    return index_rows


def main() -> None:
    print("Cargando briefs pendientes...")
    all_briefs = load_briefs()
    briefs = [brief for brief in all_briefs if brief.get("estado", "").lower() == "pending"]

    if not briefs:
        print("No hay briefs pendientes. Reconstruyendo solo data/index.csv como indice derivado.")
        write_index(build_derived_index(all_briefs))
        return

    for position, brief in enumerate(briefs, start=1):
        title = brief.get("idea_central", f"brief_{position}")
        print(f"[{position}/{len(briefs)}] Procesando: {title}")

        try:
            process_brief(brief)
        except OllamaError as exc:
            print(f"ERROR Ollama: {exc}")
            build_error_index_row(brief, str(exc))
        except Exception as exc:
            print(f"ERROR inesperado: {exc}")
            build_error_index_row(brief, f"Error inesperado: {exc}")

    write_index(build_derived_index(all_briefs))
    print("Pipeline editorial completado.")


if __name__ == "__main__":
    main()
