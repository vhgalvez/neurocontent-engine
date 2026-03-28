
# AUDIO GUIDE

> **Nota:** Este archivo está obsoleto. La documentación y el flujo real del sistema están en los siguientes archivos:

- [README.md](../README.md)
- [voice_registry.py](../voice_registry.py)
- [job_paths.py](../job_paths.py)
- [wsl/generar_audio_qwen.py](generar_audio_qwen.py)
- [wsl/generate_audio_from_prompt.py](generate_audio_from_prompt.py)
- [wsl/design_voice.py](design_voice.py)

## Resumen operativo actual

- La raíz principal de jobs es `VIDEO_JOBS_ROOT`, con fallback a `/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs`.
- Los artefactos nuevos usan naming con `job_id`.
- La voz se resuelve con precedencia: `--voice-id` → voz asignada al job → `VIDEO_DEFAULT_VOICE_ID` → fallback de compatibilidad.
- La trazabilidad de voz y audio queda en `job.json`, `status.json` y `voices/voices_index.json`.
- El audio nuevo del job se escribe en `jobs/<job_id>/audio/<job_id>_narration.wav`.
- El script nuevo vive en `jobs/<job_id>/source/<job_id>_script.json`.
- La voz se registra con `voice_id` estable en `video-dataset/voices/`.
- `job.json` registra la voz asignada y `status.json` expone el resumen operativo.

Para instrucciones de uso y migración, consulta siempre [README.md](../README.md).
