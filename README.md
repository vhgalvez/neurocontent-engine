# NeuroContent Engine

`neurocontent-engine` es un pipeline editorial y de preproducción para short-form content. El repositorio genera y mantiene artefactos por job, pero la raíz principal de esos artefactos ya no vive dentro del repo: vive en el dataset externo.

## Dataset y resolución de rutas

Resolución de prioridad:

1. argumentos CLI
2. variables de entorno
3. fallback por defecto:
   `/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset`

Variables soportadas:

- `VIDEO_DATASET_ROOT`
- `VIDEO_JOBS_ROOT`
- `VIDEO_DEFAULT_VOICE_ID`

Defaults efectivos:

- dataset root: `/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset`
- jobs root: `/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs`

El repo mantiene compatibilidad razonable de lectura con `jobs/<job_id>/` dentro del propio proyecto, pero la escritura nueva apunta al dataset externo.

## Nueva estructura de jobs


```bash
./create_video_jobs.sh
```


```text
video-dataset/
├── jobs/
│   └── 000001/
│       ├── job.json
│       ├── status.json
│       ├── source/
│       │   ├── 000001_brief.json
│       │   ├── 000001_script.json
│       │   ├── 000001_visual_manifest.json
│       │   └── 000001_rendered_comfy_workflow.json
│       ├── audio/
│       │   └── 000001_narration.wav
│       ├── subtitles/
│       │   └── 000001_narration.srt
│       └── logs/
│           ├── 000001_phase_editorial.log
│           ├── 000001_phase_audio.log
│           └── 000001_phase_subtitles.log
└── voices/
    ├── voice_global_0001/
    │   ├── voice.json
    │   ├── reference.wav
    │   ├── reference.txt
    │   └── voice_clone_prompt.json
    └── voices_index.json
```

## Naming por `job_id`

Todos los artefactos nuevos del job usan el mismo `job_id` en el nombre:

- `jobs/000001/source/000001_brief.json`
- `jobs/000001/source/000001_script.json`
- `jobs/000001/source/000001_visual_manifest.json`
- `jobs/000001/source/000001_rendered_comfy_workflow.json`
- `jobs/000001/audio/000001_narration.wav`
- `jobs/000001/subtitles/000001_narration.srt`
- `jobs/000001/logs/000001_phase_editorial.log`

`job.json` y `status.json` mantienen nombre fijo porque son el contrato estable del directorio del job.

## Voz: arquitectura nueva

La identidad vocal ahora se trata como un recurso registrable y trazable.

Cada voz tiene:

- `voice_id`
- `scope`
- `job_id` si aplica
- `voice_name`
- `voice_description`
- `model_name`
- `language`
- `seed`
- `voice_instruct`
- `reference_file`
- `voice_clone_prompt_path`
- `status`
- `notes`
- `created_at`
- `updated_at`

### Scopes soportados

`global`

- una voz reutilizable entre jobs
- ejemplo: `voice_global_0001`

`job`

- una voz específica para un job
- ejemplo: `voice_job_000001_0001`

## Precedencia real de voz

El código resuelve la voz en este orden:

1. `--voice-id` explícito
2. voz ya asignada en `jobs/<job_id>/job.json`
3. `VIDEO_DEFAULT_VOICE_ID` como voz global por defecto
4. fallback de compatibilidad:
   en VoiceDesign se auto-registra una voz `job` desde preset/seed legacy si no existe ninguna asignación previa

Ese origen queda registrado como `voice_source` y también como `voice_selection_mode`.

## Registry de voces

Ubicación principal:

- `video-dataset/voices/voices_index.json`
- `video-dataset/voices/<voice_id>/voice.json`

`job.json` guarda qué voz quedó asignada al job:

```json
{
  "voice": {
    "voice_id": "voice_global_0001",
    "scope": "global",
    "selection_mode": "manual",
    "voice_name": "marca_personal_es",
    "voice_description": "Voz principal estable para la marca.",
    "model_name": "/mnt/d/.../Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "language": "Spanish",
    "seed": 424242,
    "reference_file": "/mnt/c/.../video-dataset/voices/voice_global_0001/reference.wav"
  }
}
```

`status.json` replica los campos clave de trazabilidad para ver rápidamente qué voz se usó sin abrir todo el registry.
También guarda:

- `voice_source`
- `audio_file`
- `audio_generated_at`

## Flujos vocales soportados

### Flujo 1: voz global estable

1. crear una voz global una sola vez
2. registrar esa voz con `voice_global_0001`
3. asignarla a jobs por `voice_id`
4. reutilizar siempre la misma identidad

Ejemplo:

```bash
bash wsl/run_design_voice.sh --scope global --voice-name marca_personal_es --assign-to-job false
```

Después puedes usarla en un job:

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

O dejarla como default global:

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
bash wsl/run_audio.sh --job-id 000001
```

### Flujo 2: voz individual por job

1. crear o auto-registrar una voz de job
2. guardarla como `voice_job_<job_id>_<nnnn>`
3. asignarla al `job.json`
4. reutilizarla siempre dentro de ese job

Ejemplo explícito:

```bash
bash wsl/run_design_voice.sh --scope job --job-id 000001 --voice-name campaña_a --assign-to-job
```

Ejemplo por compatibilidad:

- si el job no tiene voz asignada y lanzas `run_audio.sh`
- el sistema puede auto-registrar una voz `job` desde el preset/seed actual
- la asignación queda persistida en `job.json`

### Flujo 3: selección manual de voz existente

1. localizar un `voice_id` del registry
2. pasarlo por CLI
3. el job queda ligado a esa voz

Ejemplo:

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

## Cómo reproducir exactamente una voz

Para reproducibilidad necesitas revisar:

1. `jobs/<job_id>/job.json`
2. `jobs/<job_id>/status.json`
3. `voices/<voice_id>/voice.json`

Campos críticos:

- `voice_id`
- `scope`
- `model_name`
- `seed`
- `voice_instruct`
- `reference_file`
- `voice_clone_prompt_path`
- `selection_mode`
- `voice_source`
- `audio_file`
- `audio_generated_at`

## Ejecución

### Editorial

Desde la raíz:

```bash
python main.py
```

Con override de dataset:

```bash
python main.py --dataset-root /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset
```

Solo un job:

```bash
python main.py --job-id 000001
```

### Audio VoiceDesign

```bash
bash wsl/run_audio.sh --job-id 000001
```

Con selección manual de voz:

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

### Diseñar y registrar voz

Voz global:

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

Voz de job:

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name campaña_a \
  --description "Voz específica de campaña." \
  --reference-text "Hola, esta es la voz de esta campaña." \
  --assign-to-job
```

### Audio por clone prompt

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --job-id 000001 \
  --voice-id voice_global_0001 \
  --overwrite
```

O registrando manualmente desde un `reference.wav`:

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --job-id 000001 \
  --reference-wav /mnt/c/ruta/a/reference.wav \
  --reference-text "Texto exacto del reference.wav" \
  --save-prompt \
  --overwrite
```

### Subtítulos

```bash
bash wsl/run_subs.sh --job-id 000001
```

## Ejemplo concreto de job `000001`

```text
jobs/000001/
├── job.json
├── status.json
├── source/
│   ├── 000001_brief.json
│   ├── 000001_script.json
│   ├── 000001_visual_manifest.json
│   └── 000001_rendered_comfy_workflow.json
├── audio/
│   └── 000001_narration.wav
├── subtitles/
│   └── 000001_narration.srt
└── logs/
    ├── 000001_phase_editorial.log
    ├── 000001_phase_audio.log
    └── 000001_phase_subtitles.log
```

## Ejemplo concreto de voz global

```json
{
  "voice_id": "voice_global_0001",
  "scope": "global",
  "job_id": null,
  "voice_name": "marca_personal_es",
  "voice_description": "Voz principal estable para la marca.",
  "model_name": "/mnt/d/.../Qwen3-TTS-12Hz-1.7B-VoiceDesign",
  "language": "Spanish",
  "seed": 424242,
  "voice_instruct": "Voz madura, profesional, sobria y consistente.",
  "reference_file": "/mnt/c/.../video-dataset/voices/voice_global_0001/reference.wav",
  "status": "active"
}
```

## Migración desde la estructura anterior

Compatibilidad actual:

- lectura legacy de `jobs/<job_id>/brief.json`
- lectura legacy de `jobs/<job_id>/script.json`
- lectura legacy de `jobs/<job_id>/visual_manifest.json`
- lectura legacy de `jobs/<job_id>/audio/narration.wav`
- lectura legacy de `jobs/<job_id>/subtitles/narration.srt`
- lectura legacy de `jobs/<job_id>/voice.json`

Nuevo comportamiento:

- la escritura nueva usa `source/`, `audio/`, `subtitles/`, `logs/`
- el naming nuevo usa `job_id` en todos los artefactos del job
- la voz ya no queda como texto libre suelto: queda registrada y asignada

Recomendación de migración:

1. definir `VIDEO_DATASET_ROOT`
2. crear la estructura con `bash wsl/create_video_jobs.sh`
3. ejecutar `python main.py`
4. ejecutar audio/subs con los wrappers WSL
5. revisar `job.json`, `status.json` y `voices/voices_index.json`

## Comentarios de diseño

- La resolución de paths vive centralizada en `job_paths.py` y `config.py`.
- `main.py` y `director.py` ya no asumen que `jobs/` del repo es la raíz principal.
- `job.json` es el contrato estable del job.
- `voice_registry.py` separa identidad vocal, asignación a job y persistencia del registry.
- La consistencia vocal ya depende de una identidad persistida, no solo de un preset o texto suelto.