# AUDIO GUIDE

Este documento legacy ya no es la fuente de verdad del flujo de audio.

El comportamiento real actual está en:

- `README.md`
- `wsl/generar_audio_qwen.py`
- `wsl/generate_audio_from_prompt.py`
- `wsl/design_voice.py`
- `voice_registry.py`
- `job_paths.py`

Resumen operativo real:

- la raíz principal de jobs es `VIDEO_JOBS_ROOT`, con fallback a `/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs`
- los artefactos nuevos usan naming con `job_id`
- la voz se resuelve con precedencia explícita: `--voice-id` -> voz asignada al job -> `VIDEO_DEFAULT_VOICE_ID` -> fallback de compatibilidad
- la trazabilidad de voz y audio queda en `job.json`, `status.json` y `voices/voices_index.json`

Si necesitas instrucciones de uso, usa `README.md`. Si necesitas verificar comportamiento, revisa el código indicado arriba.
