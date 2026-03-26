# wsl\generar_subtitulos.py

import os
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
AUDIO_DIR = PROJECT_DIR / "outputs" / "audio"
SUB_DIR = PROJECT_DIR / "outputs" / "subtitles"

WHISPERX_BIN = os.getenv("WHISPERX_BIN", str(Path.home() / "whisperx-venv" / "bin" / "whisperx"))
WHISPER_MODEL = os.getenv("WHISPERX_MODEL", "medium")
LANGUAGE = os.getenv("WHISPERX_LANGUAGE", "es")
DEVICE = os.getenv("WHISPERX_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "float16")
OVERWRITE = os.getenv("WHISPERX_OVERWRITE", "false").lower() == "true"

SUB_DIR.mkdir(parents=True, exist_ok=True)


def main():
    if not Path(WHISPERX_BIN).exists():
        raise FileNotFoundError(f"No existe WHISPERX_BIN: {WHISPERX_BIN}")

    wav_files = sorted(AUDIO_DIR.glob("*.wav"))

    if not wav_files:
        print("No hay archivos WAV en outputs/audio")
        return

    for wav in wav_files:
        expected_srt = SUB_DIR / f"{wav.stem}.srt"

        if expected_srt.exists() and not OVERWRITE:
            print(f"Ya existe {expected_srt.name}, se omite")
            continue

        print(f"Generando subtítulos para: {wav.name}")

        cmd = [
            WHISPERX_BIN,
            str(wav),
            "--model", WHISPER_MODEL,
            "--language", LANGUAGE,
            "--device", DEVICE,
            "--compute_type", COMPUTE_TYPE,
            "--output_format", "srt",
            "--output_dir", str(SUB_DIR),
        ]

        subprocess.run(cmd, check=True)

    print(f"Subtítulos generados en: {SUB_DIR}")


if __name__ == "__main__":
    main()