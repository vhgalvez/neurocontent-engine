# NeuroContent Engine

`neurocontent-engine` es un pipeline editorial y de preproducción para short-form content. El repositorio genera y mantiene artefactos por job, pero la raíz principal de esos artefactos ya no vive dentro del repo: vive en el dataset externo.

El contrato editorial ahora soporta targets de render explícitos:

- `vertical`
- `horizontal`
- `vertical|horizontal`

## Estado operativo y mapa documental

La documentación del proyecto se ha auditado y reorganizado para reflejar el estado real del sistema después de las correcciones recientes en:

- entorno funcional de Qwen3-TTS sobre WSL2
- wrappers Bash que usan `QWEN_PYTHON`
- registro de voces y unicidad de `voice_name`
- borrado consistente de voces
- validación fuerte de `voices_index.json`

Punto de entrada recomendado para entender el sistema:

- este `README.md`: visión general del repositorio, estructura de jobs y flujo operativo principal
- `wsl/VOICE_SYSTEM_GUIDE.md`: guía técnica extensa del sistema de voces, registry, validaciones y borrado
- `wsl/errores.md`: troubleshooting operativo y estado verificado del entorno Qwen3-TTS en WSL2
- `wsl/AUDIO_GUIDE.md`: guía corta de arranque, comandos reales y navegación documental

Si estás trabajando en audio y voces, la lectura recomendada es:

1. `README.md`
2. `wsl/VOICE_SYSTEM_GUIDE.md`
3. `wsl/errores.md`
4. `wsl/AUDIO_GUIDE.md`

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

## Render targets editoriales

El CSV `data/ideas.csv` acepta cuatro columnas nuevas:

- `render_targets`
- `default_render_target`
- `content_orientation`
- `target_aspect_ratio`

Valores soportados:

- `render_targets`: `vertical`, `horizontal`, `vertical|horizontal`
- `default_render_target`: `vertical`, `horizontal`
- `content_orientation`: `portrait`, `landscape`, `multi`
- `target_aspect_ratio`: `9:16`, `16:9`, `9:16|16:9`

Compatibilidad con CSV antiguos:

- si esas columnas no existen, el pipeline sigue funcionando
- defaults efectivos: `render_targets=vertical`, `default_render_target=vertical`, `content_orientation=portrait`, `target_aspect_ratio=9:16`

Ejemplos en `ideas.csv`:

```csv
id,...,render_targets,default_render_target,content_orientation,target_aspect_ratio
101,...,vertical,vertical,portrait,9:16
102,...,horizontal,horizontal,landscape,16:9
103,...,vertical|horizontal,vertical,multi,9:16|16:9
```

## Contrato de render derivado

Los campos resueltos se propagan a:

- `data/index.csv`
- `jobs/<job_id>/job.json`
- `jobs/<job_id>/status.json`
- `jobs/<job_id>/source/<job_id>_visual_manifest.json`

### `index.csv`

El índice derivado ahora incluye:

- `render_targets`
- `default_render_target`
- `content_orientation`

Ejemplo:

```csv
job_id,source_id,estado_csv,idea_central,platform,language,render_targets,default_render_target,content_orientation,brief_created,script_generated,audio_generated,subtitles_generated,visual_manifest_generated,export_ready,last_step,updated_at
000103,103,pending,ejemplo multi target,youtube,es,vertical|horizontal,vertical,multi,True,True,False,False,True,False,visual_manifest_generated,2026-03-28T17:55:46+00:00
```

### `job.json`

Ejemplo vertical:

```json
{
  "render": {
    "targets": ["vertical"],
    "default_target": "vertical",
    "content_orientation": "portrait",
    "aspect_ratios": ["9:16"]
  }
}
```

Ejemplo horizontal:

```json
{
  "render": {
    "targets": ["horizontal"],
    "default_target": "horizontal",
    "content_orientation": "landscape",
    "aspect_ratios": ["16:9"]
  }
}
```

Ejemplo multi target:

```json
{
  "render": {
    "targets": ["vertical", "horizontal"],
    "default_target": "vertical",
    "content_orientation": "multi",
    "aspect_ratios": ["9:16", "16:9"]
  }
}
```

### `status.json`

`status.json` mantiene compatibilidad con el estado actual y añade:

- `render_targets`
- `default_render_target`
- `render_vertical_requested`
- `render_horizontal_requested`
- `render_vertical_ready`
- `render_horizontal_ready`

Ejemplo:

```json
{
  "render_targets": ["vertical", "horizontal"],
  "default_render_target": "vertical",
  "render_vertical_requested": true,
  "render_horizontal_requested": true,
  "render_vertical_ready": false,
  "render_horizontal_ready": false
}
```

### `visual_manifest.json`

El manifest ya no asume `9:16` como contrato universal. Ahora expone:

- `render_targets`
- `default_render_target`
- `content_orientation`
- `target_aspect_ratios`
- `render_profiles`

Ejemplo multi target:

```json
{
  "render_targets": ["vertical", "horizontal"],
  "default_render_target": "vertical",
  "content_orientation": "multi",
  "target_aspect_ratios": ["9:16", "16:9"],
  "render_profiles": {
    "vertical": {
      "aspect_ratio": "9:16",
      "safe_area": "center-weighted mobile frame",
      "platform_behavior": "short-form vertical video, fast clarity, early payoff"
    },
    "horizontal": {
      "aspect_ratio": "16:9",
      "safe_area": "wider composition for desktop and long-form framing",
      "platform_behavior": "landscape framing, stronger lateral composition"
    }
  }
}
```

## Voz: arquitectura nueva

La identidad vocal ahora se trata como un recurso registrable y trazable.

Cada voz tiene:

- `voice_id`
- `scope`
- `job_id` si aplica
- `voice_mode`
- `voice_name`
- `voice_description`
- `model_name`
- `language`
- `seed`
- `voice_instruct`
- `reference_file`
- `reference_text_file`
- `voice_clone_prompt_path`
- `tts_strategy_default`
- `supports_reference_conditioning`
- `supports_clone_prompt`
- `status`
- `notes`
- `created_at`
- `updated_at`

### `voice_id` vs `voice_name`

- `voice_id`: identificador tecnico persistente del sistema. Ejemplo: `voice_global_0001`.
- `voice_name`: nombre logico humano de la voz. Ejemplo: `marca_personal_es`.
- `voice_name` debe ser unico dentro del registry.
- `voice_name` no puede parecer un `voice_id` interno como `voice_global_0001` o `voice_job_000001_0001`.
- si intentas crear una voz con un `voice_name` ya usado, el alta aborta con error explicito.

## Semántica de voz y síntesis

El sistema separa dos conceptos:

- identidad vocal registrada
- estrategia real de síntesis usada al generar audio

### `voice_mode`

- `design_only`: la voz se reutiliza como descripción persistente, seed y preset. `reference.wav` queda como referencia trazable, no como garantía de condicionamiento acústico directo.
- `reference_conditioned`: la voz espera reutilizar `reference.wav` y, si existe, `reference.txt` o `reference_text_file`.
- `clone_prompt`: la voz espera reutilizar `voice_clone_prompt_path`.

### `tts_strategy_default`

Expresa la estrategia pedida por defecto para esa voz:

- `description_seed_preset`
- `reference_conditioned`
- `clone_prompt`
- `legacy_preset_fallback`

### Regla importante de UX

`VIDEO_DEFAULT_VOICE_ID` solo selecciona qué voz registrada usar. No obliga por sí mismo a que el motor consuma `reference.wav`. La estrategia real depende de `voice_mode`, `tts_strategy_default` y de la capacidad del flujo de síntesis disponible.

Si el flujo no puede usar la estrategia pedida, el sistema ahora:

- registra la estrategia pedida
- registra la estrategia realmente usada
- marca si hubo fallback
- guarda la razón del fallback en `job.json`, `status.json` y logs

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
    "voice_mode": "design_only",
    "tts_strategy_default": "description_seed_preset",
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
- `voice_mode`
- `tts_strategy_requested`
- `tts_strategy_used`
- `tts_fallback_used`
- `tts_fallback_reason`

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

## Logs y trazabilidad de síntesis

El log de audio ya no resume todo como un simple `preset=...` cuando se resolvió una voz registrada. Ahora distingue:

- `voice_id` resuelto
- `voice_mode`
- estrategia pedida
- estrategia usada
- fallback y motivo si aplica

Ejemplo sin fallback:

```text
[000001] Voice resolved: voice_global_0001 mode=design_only
[000001] Requested strategy: description_seed_preset
[000001] Preset used: mujer_podcast_seria_35_45 (source=global_default)
[000001] Strategy used: description_seed_preset
[000001] Audio generado en ... con voice_id=voice_global_0001, voice_mode=design_only, strategy=description_seed_preset
```

Ejemplo con fallback:

```text
[000001] Voice resolved: voice_global_0001 mode=reference_conditioned
[000001] Requested strategy: reference_conditioned
[000001] Fallback strategy used: description_seed_preset
[000001] Fallback reason: Current synthesis path could not consume reference conditioning directly: ...
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

### Entorno WSL2 para Qwen3-TTS

El entorno operativo válido para audio con Qwen3-TTS en WSL2 es el entorno conda `qwen_gpu`. Ese entorno ya fue verificado con GPU real y es el único que debe considerarse válido como base operativa para los wrappers de audio y de diseño de voz.

Entorno funcional verificado:

- activación: `conda activate qwen_gpu`
- Python válido: `/home/victory/miniconda3/envs/qwen_gpu/bin/python`
- sistema: Windows + WSL2
- distro validada: Ubuntu 24.04 LTS
- GPU validada: NVIDIA GeForce RTX 4070
- Python: `3.12`
- `torch==2.5.1`
- `torchvision==0.20.1`
- `torchaudio==2.5.1`
- CUDA operativa en WSL2
- `qwen_tts` importando correctamente
- `run_design_voice.sh` generando `reference.wav` correctamente

El `venv` antiguo:

```bash
/home/victory/Qwen3-TTS/venv/bin/python
```

ya no debe usarse.

El fallback correcto en los wrappers WSL es:

```bash
export QWEN_PYTHON="${QWEN_PYTHON:-/home/victory/miniconda3/envs/qwen_gpu/bin/python}"
```

Esto mantiene dos propiedades importantes:

- si `QWEN_PYTHON` no viene definido, el sistema usa por defecto el Python bueno del entorno `qwen_gpu`
- si `QWEN_PYTHON` ya viene exportado externamente, el wrapper no lo pisa y mantiene compatibilidad con override manual

Comandos de verificación rápida:

```bash
conda activate qwen_gpu
which python
python -V
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

Resultado esperado:

- el `python` debe resolver al entorno `qwen_gpu`
- `Python 3.12`
- `torch 2.5.1`
- `True` para CUDA
- `qwen_tts OK`

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

Reglas de alta:

- `--voice-name` es un alias logico, no un `voice_id`
- si ya existe ese `voice_name`, el sistema aborta con `ERROR: ya existe una voz con ese nombre`
- si el nombre parece un id interno del sistema, el alta tambien aborta

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

### Borrar una voz de forma consistente

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

Comportamiento:

- valida que el `voice_id` exista en `voices_index.json`
- valida que existan la carpeta fisica y `voice.json`
- aborta si algun `job.json` sigue referenciando esa voz
- elimina la carpeta de la voz y su entrada en `voices_index.json`
- valida el registry final y hace rollback automatico si algo falla durante el proceso

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
  "voice_mode": "design_only",
  "job_id": null,
  "voice_name": "marca_personal_es",
  "voice_description": "Voz principal estable para la marca.",
  "model_name": "/mnt/d/.../Qwen3-TTS-12Hz-1.7B-VoiceDesign",
  "language": "Spanish",
  "seed": 424242,
  "voice_instruct": "Voz madura, profesional, sobria y consistente.",
  "reference_file": "/mnt/c/.../video-dataset/voices/voice_global_0001/reference.wav",
  "reference_text_file": "/mnt/c/.../video-dataset/voices/voice_global_0001/reference.txt",
  "tts_strategy_default": "description_seed_preset",
  "supports_reference_conditioning": false,
  "supports_clone_prompt": false,
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

## Troubleshooting resumido

Problemas típicos y causa probable:

- `ERROR: no existe Python ejecutable en ...`
  Suele indicar que `QWEN_PYTHON` apunta al `venv` antiguo o a una ruta inexistente.
- `QWEN_TTS_DEVICE=cuda pero CUDA no esta disponible`
  Suele indicar que no estás en el entorno `qwen_gpu` correcto o que la GPU no está expuesta correctamente dentro de WSL2.
- `ImportError` al importar `torch`, `torchaudio` o `qwen_tts`
  Suele indicar mezcla de entornos, versiones incompatibles o uso accidental del Python antiguo.
- `ERROR: ya existe una voz con ese nombre`
  Indica que `voice_name` ya está registrado y que el alta fue bloqueada para evitar ambigüedad.
- `voice_name no puede parecer un voice_id interno`
  Indica que el alias lógico propuesto se parece a un ID técnico reservado del sistema.
- `ERROR: no se puede eliminar voice_id=... porque sigue referenciada en jobs`
  Indica que la voz aún está asignada o trazada en algún job y el borrado fue bloqueado de forma segura.

Qué hacer:

```bash
conda activate qwen_gpu
which python
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

Qué no hacer:

- no apuntar manualmente a `/home/victory/Qwen3-TTS/venv/bin/python`
- no borrar carpetas de voces a mano dentro de `video-dataset/voices/`
- no forzar `voice_name` con formato parecido a `voice_global_0001`
- no mezclar entornos de conda y `venv` antiguos

Para troubleshooting detallado y casos históricos:

- consulta `wsl/errores.md`
- consulta `wsl/VOICE_SYSTEM_GUIDE.md`


# VOS SDPA

voice over synthesis con SDPA (sin usar atención tradicional) para evitar problemas de memoria y mejorar la calidad en voces largas.

```bash
export ACCELERATE_USE_SDPA=true
```
