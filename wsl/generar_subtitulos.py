# wsl\generar_subtitulos.py

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
JOBS_DIR = PROJECT_DIR / "jobs"

# This repository stops at subtitle generation.
# The downstream visual repository should consume jobs/<id>/subtitles/narration.srt
# as the caption and timing reference aligned with the generated narration audio.

WHISPERX_BIN = os.getenv(
    "WHISPERX_BIN",
    str(Path.home() / "miniconda3" / "envs" / "whisperx" / "bin" / "whisperx"),
)
WHISPER_MODEL = os.getenv("WHISPERX_MODEL", "medium")
LANGUAGE = os.getenv("WHISPERX_LANGUAGE", "es")
DEVICE = os.getenv("WHISPERX_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "float16")
OVERWRITE = os.getenv("WHISPERX_OVERWRITE", "false").lower() == "true"


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
    status["updated_at"] = datetime.now(
        timezone.utc).replace(microsecond=0).isoformat()
    status["export_ready"] = bool(
        status["brief_created"]
        and status["script_generated"]
        and status["audio_generated"]
        and status["subtitles_generated"]
        and status["visual_manifest_generated"]
    )
    safe_write_json(status_path, status)
    return status


def iter_job_dirs():
    if not JOBS_DIR.exists():
        return []
    return sorted(path for path in JOBS_DIR.iterdir() if path.is_dir())


def main():
    whisperx_path = Path(WHISPERX_BIN)

    if not whisperx_path.exists():
        raise FileNotFoundError(
            f"No existe WHISPERX_BIN: {WHISPERX_BIN}\n"
            "Crea el entorno conda 'whisperx' o exporta una ruta valida, por ejemplo:\n"
            "export WHISPERX_BIN=/home/victory/miniconda3/envs/whisperx/bin/whisperx"
        )

    job_dirs = iter_job_dirs()
    if not job_dirs:
        print("No hay jobs para procesar en jobs/")
        return

    for job_dir in job_dirs:
        job_id = job_dir.name
        status_path = job_dir / "status.json"
        wav_path = job_dir / "audio" / "narration.wav"
        srt_path = job_dir / "subtitles" / "narration.srt"

        if not wav_path.exists():
            print(f"[{job_id}] narration.wav no existe, se omite")
            update_status(
                status_path,
                subtitles_generated=False,
                last_step="subs_missing_audio",
            )
            continue

        if srt_path.exists() and not OVERWRITE:
            print(f"[{job_id}] narration.srt ya existe, se omite")
            update_status(
                status_path,
                subtitles_generated=True,
                last_step="subs_skipped",
            )
            continue

        srt_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(whisperx_path),
            str(wav_path),
            "--model", WHISPER_MODEL,
            "--language", LANGUAGE,
            "--device", DEVICE,
            "--compute_type", COMPUTE_TYPE,
            "--output_format", "srt",
            "--output_dir", str(srt_path.parent),
        ]

        print(f"[{job_id}] Generando subtitulos")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            update_status(
                status_path,
                subtitles_generated=False,
                last_step="subtitles_error",
            )
            raise

        generated_name = srt_path.parent / f"{wav_path.stem}.srt"
        if generated_name.exists() and generated_name != srt_path:
            generated_name.replace(srt_path)

        update_status(
            status_path,
            subtitles_generated=srt_path.exists(),
            last_step="subtitles_generated",
        )

    print("Subtitulos completados")


if __name__ == "__main__":
    main()
