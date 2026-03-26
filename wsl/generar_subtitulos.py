#!/usr/bin/env python3
# wsl/generar_subtitulos.py

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
JOBS_DIR = PROJECT_DIR / "jobs"

# Python real donde WhisperX YA funciona
WHISPERX_PYTHON = os.getenv(
    "WHISPERX_PYTHON",
    "/home/victory/miniconda3/bin/python",
)

WHISPER_MODEL = os.getenv("WHISPERX_MODEL", "small")
LANGUAGE = os.getenv("WHISPERX_LANGUAGE", "es")

# Configuración estable que YA te funcionó
DEVICE = os.getenv("WHISPERX_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "int8")
NO_ALIGN = os.getenv("WHISPERX_NO_ALIGN", "true").lower() == "true"

# Fallback real
FALLBACK_DEVICE = os.getenv("WHISPERX_FALLBACK_DEVICE", "cpu")
FALLBACK_COMPUTE_TYPE = os.getenv("WHISPERX_FALLBACK_COMPUTE_TYPE", "int8")

OVERWRITE = os.getenv("WHISPERX_OVERWRITE", "false").lower() == "true"
STRICT = os.getenv("WHISPERX_STRICT", "false").lower() == "true"
PREFLIGHT = os.getenv("WHISPERX_PREFLIGHT", "true").lower() == "true"
LOG_TAIL_CHARS = int(os.getenv("WHISPERX_LOG_TAIL_CHARS", "6000"))
TIMEOUT_SECONDS = int(os.getenv("WHISPERX_TIMEOUT_SECONDS", "0"))  # 0 = sin timeout


def safe_read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return default


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
    no_align: bool,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "whisperx",
        str(wav_path),
        "--model",
        WHISPER_MODEL,
        "--language",
        LANGUAGE,
        "--device",
        device,
        "--compute_type",
        compute_type,
        "--output_format",
        "srt",
        "--output_dir",
        str(output_dir),
    ]

    if no_align:
        cmd.append("--no_align")

    return cmd


def short_output(text: str, max_chars: int = LOG_TAIL_CHARS) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def run_cmd(cmd: list[str], log_path: Path | None = None) -> tuple[bool, int, str]:
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=None if TIMEOUT_SECONDS <= 0 else TIMEOUT_SECONDS,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        if log_path is not None:
            log_path.write_text(output, encoding="utf-8")
        return True, result.returncode, output
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        output = f"TIMEOUT after {TIMEOUT_SECONDS}s\n{output}"
        if log_path is not None:
            log_path.write_text(output, encoding="utf-8")
        return False, 124, output
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        if log_path is not None:
            log_path.write_text(output, encoding="utf-8")
        return False, exc.returncode, output
    except Exception as exc:
        output = str(exc)
        if log_path is not None:
            log_path.write_text(output, encoding="utf-8")
        return False, 1, output


def preflight_runtime(python_path: Path) -> None:
    print("Preflight: comprobando entorno WhisperX...")

    torch_cmd = [
        str(python_path),
        "-c",
        (
            "import torch; "
            "print('torch=' + torch.__version__); "
            "print('cuda=' + str(torch.cuda.is_available()))"
        ),
    ]
    ok, code, output = run_cmd(torch_cmd)
    if not ok:
        raise RuntimeError(
            "Falló el preflight de torch.\n"
            f"Python: {python_path}\n"
            f"Exit code: {code}\n"
            f"Salida:\n{short_output(output)}"
        )

    print(short_output(output, 2000))

    help_cmd = [str(python_path), "-m", "whisperx", "--help"]
    ok, code, output = run_cmd(help_cmd)
    if not ok:
        raise RuntimeError(
            "Falló el preflight de whisperx CLI.\n"
            f"Python: {python_path}\n"
            f"Exit code: {code}\n"
            f"Salida:\n{short_output(output)}"
        )

    print("Preflight OK")


def normalize_generated_srt(output_dir: Path, wav_path: Path, target_srt_path: Path) -> bool:
    generated_name = output_dir / f"{wav_path.stem}.srt"

    if target_srt_path.exists():
        return True

    if generated_name.exists() and generated_name != target_srt_path:
        generated_name.replace(target_srt_path)
        return True

    return target_srt_path.exists()


def process_job(job_dir: Path, python_path: Path) -> bool:
    job_id = job_dir.name
    status_path = job_dir / "status.json"
    wav_path = job_dir / "audio" / "narration.wav"
    srt_path = job_dir / "subtitles" / "narration.srt"
    log_dir = job_dir / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    srt_path.parent.mkdir(parents=True, exist_ok=True)

    if not wav_path.exists():
        print(f"[{job_id}] narration.wav no existe, se omite")
        update_status(
            status_path,
            subtitles_generated=False,
            last_step="subs_missing_audio",
        )
        return False

    if srt_path.exists() and not OVERWRITE:
        print(f"[{job_id}] narration.srt ya existe, se omite")
        update_status(
            status_path,
            subtitles_generated=True,
            last_step="subs_skipped",
        )
        return True

    main_log = log_dir / "whisperx_main.log"
    fallback_log = log_dir / "whisperx_fallback.log"

    main_cmd = build_cmd(
        python_bin=str(python_path),
        wav_path=wav_path,
        output_dir=srt_path.parent,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        no_align=NO_ALIGN,
    )

    print(f"[{job_id}] Principal -> {DEVICE}/{COMPUTE_TYPE} no_align={NO_ALIGN}")
    ok, code, output = run_cmd(main_cmd, log_path=main_log)

    if ok:
        exists = normalize_generated_srt(srt_path.parent, wav_path, srt_path)
        update_status(
            status_path,
            subtitles_generated=exists,
            last_step="subtitles_generated",
        )
        if exists:
            print(f"[{job_id}] OK (principal) -> {srt_path}")
            return True

        print(f"[{job_id}] El comando terminó OK pero no apareció el SRT esperado")
        print(f"[{job_id}] Revisa log: {main_log}")
        update_status(
            status_path,
            subtitles_generated=False,
            last_step="subtitles_missing_output",
        )
        return False

    print(f"[{job_id}] Falló principal (exit={code}). Fallback -> {FALLBACK_DEVICE}/{FALLBACK_COMPUTE_TYPE}")
    print(f"[{job_id}] Log principal: {main_log}")
    tail = short_output(output)
    if tail:
        print(tail)

    fallback_cmd = build_cmd(
        python_bin=str(python_path),
        wav_path=wav_path,
        output_dir=srt_path.parent,
        device=FALLBACK_DEVICE,
        compute_type=FALLBACK_COMPUTE_TYPE,
        no_align=True,
    )
    ok, code, output = run_cmd(fallback_cmd, log_path=fallback_log)

    if ok:
        exists = normalize_generated_srt(srt_path.parent, wav_path, srt_path)
        update_status(
            status_path,
            subtitles_generated=exists,
            last_step="subtitles_generated_fallback",
        )
        if exists:
            print(f"[{job_id}] OK (fallback) -> {srt_path}")
            return True

        print(f"[{job_id}] El fallback terminó OK pero no apareció el SRT esperado")
        print(f"[{job_id}] Revisa log: {fallback_log}")
        update_status(
            status_path,
            subtitles_generated=False,
            last_step="subtitles_missing_output_fallback",
        )
        return False

    print(f"[{job_id}] Falló fallback (exit={code})")
    print(f"[{job_id}] Log fallback: {fallback_log}")
    tail = short_output(output)
    if tail:
        print(tail)

    update_status(
        status_path,
        subtitles_generated=False,
        last_step="subtitles_error",
    )

    if STRICT:
        raise RuntimeError(f"[{job_id}] WhisperX falló en principal y fallback")

    return False


def main() -> int:
    python_path = Path(WHISPERX_PYTHON)

    if not python_path.exists():
        raise FileNotFoundError(
            f"No existe WHISPERX_PYTHON: {WHISPERX_PYTHON}\n"
            "Asegúrate de tener WhisperX instalado correctamente."
        )

    if PREFLIGHT:
        preflight_runtime(python_path)

    job_dirs = iter_job_dirs()
    if not job_dirs:
        print("No hay jobs para procesar en jobs/")
        return 0

    total = len(job_dirs)
    ok_count = 0
    error_count = 0

    for job_dir in job_dirs:
        try:
            ok = process_job(job_dir, python_path)
            if ok:
                ok_count += 1
            else:
                error_count += 1
        except Exception as exc:
            error_count += 1
            print(f"[{job_dir.name}] ERROR no controlado: {exc}")
            update_status(
                job_dir / "status.json",
                subtitles_generated=False,
                last_step="subtitles_exception",
            )
            if STRICT:
                raise

    print(f"Subtítulos completados (total={total}, ok={ok_count}, errores={error_count})")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())