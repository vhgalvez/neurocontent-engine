# wsl\generar_subtitulos.py

import os
import shutil
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
AUDIO_DIR = PROJECT_DIR / "outputs" / "audio"
SUB_DIR = PROJECT_DIR / "outputs" / "subtitles"

WHISPER_MODEL = os.getenv("WHISPERX_MODEL", "medium")
LANGUAGE = os.getenv("WHISPERX_LANGUAGE", "es")
OVERWRITE = os.getenv("WHISPERX_OVERWRITE", "false").lower() == "true"

SUB_DIR.mkdir(parents=True, exist_ok=True)


def get_whisperx_command() -> list[str]:
    whisperx_bin = shutil.which("whisperx")
    if whisperx_bin:
        return [whisperx_bin]
    return ["python3", "-m", "whisperx"]


def main():
    wav_files = sorted(AUDIO_DIR.glob("*.wav"))

    if not wav_files:
        print("No hay archivos WAV en outputs/audio")
        return

    base_cmd = get_whisperx_command()

    for wav in wav_files:
        expected_srt = SUB_DIR / f"{wav.stem}.srt"

        if expected_srt.exists() and not OVERWRITE:
            print(f"Ya existe {expected_srt.name}, se omite")
            continue

        print(f"Generando subtítulos para: {wav.name}")

        cmd = base_cmd + [
            str(wav),
            "--model", WHISPER_MODEL,
            "--language", LANGUAGE,
            "--output_format", "srt",
            "--output_dir", str(SUB_DIR),
        ]

        subprocess.run(cmd, check=True)

    print(f"Subtítulos generados en: {SUB_DIR}")


if __name__ == "__main__":
    main()