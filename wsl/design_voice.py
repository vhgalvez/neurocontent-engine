"""Ejemplos de uso:

bash wsl/run_design_voice.sh \
  --voice-name voz_finanzas \
  --description "Voz femenina madura, sobria y profesional." \
  --reference-text "Hola, esta es una referencia corta." \
  --overwrite

python wsl/design_voice.py \
  --voice-name voz_finanzas \
  --description "Voz femenina madura, sobria y profesional." \
  --reference-text "Hola, esta es una referencia corta." \
  --device cuda \
  --overwrite
"""

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
from qwen_tts import Qwen3TTSModel

os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = os.getenv(
    "QWEN_TTS_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)
DEFAULT_REFERENCE_ROOT = os.getenv(
    "QWEN_TTS_REFERENCE_ROOT",
    str(PROJECT_DIR / "assets" / "voices"),
)
DEFAULT_VOICE_NAME = os.getenv("QWEN_TTS_REFERENCE_NAME", "voz_principal")
DEFAULT_DESCRIPTION = os.getenv(
    "QWEN_TTS_VOICE_DESCRIPTION",
    "Voz femenina madura, seria, clara y profesional para narracion tipo podcast.",
)
DEFAULT_REFERENCE_TEXT = os.getenv(
    "QWEN_TTS_REFERENCE_TEXT",
    "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores.",
)
DEFAULT_LANGUAGE = os.getenv("QWEN_TTS_REFERENCE_LANGUAGE", os.getenv("QWEN_TTS_LANGUAGE", "Spanish"))
DEFAULT_DEVICE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()
DEFAULT_SEED = int(os.getenv("QWEN_TTS_SEED", "424242"))
DEFAULT_USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN", "false").lower() == "true"


def log(message: str) -> None:
    print(message, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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

    log(f"[design_voice] Modelo VoiceDesign: {resolved_model_path}")
    log(f"[design_voice] device_map={device_map} dtype={dtype} flash_attn={use_flash_attn}")
    model = Qwen3TTSModel.from_pretrained(resolved_model_path, **kwargs)
    if getattr(model.model, "tts_model_type", None) != "voice_design":
        raise RuntimeError(
            "El modelo cargado no es VoiceDesign. "
            f"tts_model_type={getattr(model.model, 'tts_model_type', 'desconocido')}"
        )
    return model, resolved_model_path


def resolve_generate_voice_design_method(model) -> callable:
    method = getattr(model, "generate_voice_design", None)
    if not callable(method):
        raise RuntimeError("La libreria qwen_tts no expone generate_voice_design()")
    return method


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Disena una voz con Qwen3-TTS VoiceDesign y genera reference.wav."
    )
    parser.add_argument("--voice-name", default=DEFAULT_VOICE_NAME, help="Nombre de carpeta bajo assets/voices.")
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION, help="Descripcion natural de la voz.")
    parser.add_argument("--reference-text", default=DEFAULT_REFERENCE_TEXT, help="Texto corto para generar la referencia.")
    parser.add_argument("--reference-root", default=DEFAULT_REFERENCE_ROOT, help="Raiz de assets/voices.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Idioma de la voz.")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH, help="Ruta del modelo VoiceDesign.")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["auto", "cpu", "cuda"], help="Device.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed para estabilidad.")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribe reference.wav si existe.")
    parser.add_argument(
        "--use-flash-attn",
        action="store_true",
        default=DEFAULT_USE_FLASH_ATTN,
        help="Usa flash_attention_2 si esta disponible.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        voice_name = normalize_text(args.voice_name).replace(" ", "_")
        if not voice_name:
            raise RuntimeError("voice_name no puede estar vacio")

        description = normalize_text(args.description)
        reference_text = normalize_text(args.reference_text)
        if not description:
            raise RuntimeError("description no puede estar vacia")
        if not reference_text:
            raise RuntimeError("reference_text no puede estar vacio")

        target_dir = Path(args.reference_root) / voice_name
        reference_wav = target_dir / "reference.wav"
        reference_text_path = target_dir / "reference.txt"
        metadata_path = target_dir / "voice.json"

        if reference_wav.exists() and not args.overwrite:
            raise RuntimeError(
                f"Ya existe {reference_wav}. Usa --overwrite si quieres regenerar la referencia."
            )

        set_global_seed(args.seed)
        model, resolved_model_path = load_model(
            model_path=args.model_path,
            device_mode=args.device,
            use_flash_attn=args.use_flash_attn,
        )
        generator = resolve_generate_voice_design_method(model)

        log(f"[design_voice] Generando referencia para voice_name={voice_name}")
        wavs, sample_rate = generator(
            text=reference_text,
            instruct=description,
            language=args.language,
            non_streaming_mode=True,
        )
        if not wavs:
            raise RuntimeError("generate_voice_design() no devolvio audio")

        target_dir.mkdir(parents=True, exist_ok=True)
        sf.write(str(reference_wav), wavs[0], sample_rate)
        safe_write_text(reference_text_path, reference_text + "\n")
        safe_write_json(
            metadata_path,
            {
                "voice_name": voice_name,
                "description": description,
                "reference_text": reference_text,
                "reference_wav": str(reference_wav),
                "language": args.language,
                "seed": args.seed,
                "model_path": resolved_model_path,
                "model_type": "voice_design",
                "generated_at": now_iso(),
            },
        )

        log(f"[design_voice] Referencia guardada en {reference_wav}")
        log(f"[design_voice] Texto de referencia guardado en {reference_text_path}")
        log(f"[design_voice] Metadata guardada en {metadata_path}")

    except Exception as exc:
        log(f"[design_voice] Error: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
