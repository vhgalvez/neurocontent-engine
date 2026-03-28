# AUDIO GUIDE v2

Este archivo quedó obsoleto tras el refactor de dataset externo y registry de voces.

La documentación vigente está en:

- `README.md`
- `voice_registry.py`
- `job_paths.py`
- `wsl/generar_audio_qwen.py`
- `wsl/generate_audio_from_prompt.py`
- `wsl/design_voice.py`

Puntos reales del sistema actual:

- no se escribe audio nuevo en `repo/jobs/<job_id>/audio/narration.wav`
- el audio nuevo del job se escribe en `jobs/<job_id>/audio/<job_id>_narration.wav`
- el script nuevo vive en `jobs/<job_id>/source/<job_id>_script.json`
- la voz se registra con `voice_id` estable en `video-dataset/voices/`
- `job.json` registra la voz asignada y `status.json` expone el resumen operativo

Usa `README.md` para instrucciones de uso y migración.
