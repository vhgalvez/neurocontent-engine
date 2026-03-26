# wsl\generar_subtitulos.py

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
JOBS_DIR = PROJECT_DIR / "jobs"

WHISPERX_PYTHON = os.getenv(
    "WHISPERX_PYTHON",
    str(Path.home() / "miniconda3" / "envs" / "whisperx" / "bin" / "python"),
)

WHISPER_MODEL = os.getenv("WHISPERX_MODEL", "medium")
LANGUAGE = os.getenv("WHISPERX_LANGUAGE", "es")

# Modo preferido
DEVICE = os.getenv("WHISPERX_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "float16")

# Fallback
FALLBACK_DEVICE = os.getenv("WHISPERX_FALLBACK_DEVICE", "cpu")
FALLBACK_COMPUTE_TYPE = os.getenv("WHISPERX_FALLBACK_COMPUTE_TYPE", "float32")

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


def iter_job_dirs():
    if not JOBS_DIR.exists():
        return []
    return sorted(path for path in JOBS_DIR.iterdir() if path.is_dir())


def build_cmd(
    python_bin: str,
    wav_path: Path,
    output_dir: Path,
    device: str,
    compute_type: str,
):
    return [
        python_bin,
        "-m",
        "whisperx",
        str(wav_path),
        "--model", WHISPER_MODEL,
        "--language", LANGUAGE,
        "--device", device,
        "--compute_type", compute_type,
        "--output_format", "srt",
        "--output_dir", str(output_dir),
    ]


def run_whisperx(cmd: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        return True, (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        return False, output
    except Exception as exc:
        return False, str(exc)


def main():
    python_path = Path(WHISPERX_PYTHON)

    if not python_path.exists():
        raise FileNotFoundError(
            f"No existe WHISPERX_PYTHON: {WHISPERX_PYTHON}\n"
            "Asegúrate de tener el entorno whisperx creado correctamente."
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

        print(f"[{job_id}] Intentando subtítulos con {DEVICE}/{COMPUTE_TYPE}")
        cmd = build_cmd(
            python_bin=str(python_path),
            wav_path=wav_path,
            output_dir=srt_path.parent,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
        )

        ok, output = run_whisperx(cmd)

        if not ok:
            print(f"[{job_id}] Falló en modo principal. Intentando fallback {FALLBACK_DEVICE}/{FALLBACK_COMPUTE_TYPE}")
            if output.strip():
                print(output[-3000:])

            fallback_cmd = build_cmd(
                python_bin=str(python_path),
                wav_path=wav_path,
                output_dir=srt_path.parent,
                device=FALLBACK_DEVICE,
                compute_type=FALLBACK_COMPUTE_TYPE,
            )
            ok, fallback_output = run_whisperx(fallback_cmd)

            if not ok:
                if fallback_output.strip():
                    print(fallback_output[-3000:])
                update_status(
                    status_path,
                    subtitles_generated=False,
                    last_step="subtitles_error",
                )
                raise RuntimeError(f"[{job_id}] WhisperX falló en modo principal y fallback.")

        generated_name = srt_path.parent / f"{wav_path.stem}.srt"
        if generated_name.exists() and generated_name != srt_path:
            generated_name.replace(srt_path)

        update_status(
            status_path,
            subtitles_generated=srt_path.exists(),
            last_step="subtitles_generated",
        )
        print(f"[{job_id}] OK -> {srt_path}")

    print("Subtítulos completados")


if __name__ == "__main__":
    main()