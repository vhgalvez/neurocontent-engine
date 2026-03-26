# NeuroContent Engine

`neurocontent-engine` es un pipeline editorial y de preproduccion para short-form content. Su alcance termina en artefactos por job:

1. `brief.json`
2. `script.json`
3. `audio/narration.wav`
4. `subtitles/narration.srt`
5. `visual_manifest.json`

Este repositorio no genera video final. No renderiza escenas. No ejecuta ComfyUI. No ejecuta Wan 2.2. No monta ni exporta piezas finales.

## Responsabilidad del repositorio

Lee briefs desde `data/ideas.csv`, genera guiones con Ollama, prepara narracion para TTS, genera audio en WSL2 con Qwen3-TTS, genera subtitulos en WSL2 con WhisperX y deja un `visual_manifest.json` listo para otro repositorio visual downstream.

## Arquitectura

```text
neurocontent-engine/
├── data/
│   ├── ideas.csv
│   └── index.csv
├── jobs/
│   └── 000001/
│       ├── brief.json
│       ├── script.json
│       ├── status.json
│       ├── visual_manifest.json
│       ├── audio/
│       │   └── narration.wav
│       └── subtitles/
│           └── narration.srt
├── wsl/
│   ├── generar_audio_qwen.py
│   ├── generar_subtitulos.py
│   ├── run_audio.sh
│   ├── run_subs.sh
│   └── run_wsl_pipeline.sh
├── config.py
├── director.py
├── main.py
└── prompts.py
```

## Fuente de verdad

- `data/ideas.csv` es la fuente editorial de verdad
- `jobs/<id>/` es la unidad de proceso y trazabilidad
- `data/index.csv` es solo un indice derivado y reconstruible

Eso implica que si el CSV cambia, `brief.json` se vuelve a sincronizar desde el CSV. En cambio `script.json` y `visual_manifest.json` no se regeneran si ya existen, salvo overwrite explicito.

## Ejecucion

### Windows: pipeline editorial

Ejecuta desde la raiz:

```bash
python main.py
```

Para cada fila con `estado=pending`, el pipeline:

1. sincroniza `jobs/<id_padded>/brief.json` desde el CSV
2. genera o reutiliza `jobs/<id_padded>/script.json`
3. genera o reutiliza `jobs/<id_padded>/visual_manifest.json`
4. actualiza `jobs/<id_padded>/status.json`
5. reconstruye `data/index.csv`

### WSL2: audio y subtitulos

Primera vez:

```bash
chmod +x wsl/run_audio.sh wsl/run_subs.sh wsl/run_wsl_pipeline.sh
```

Audio:

```bash
bash wsl/run_audio.sh
```

Subtitulos:

```bash
bash wsl/run_subs.sh
```

Pipeline completo:

```bash
bash wsl/run_wsl_pipeline.sh all
```

Modos soportados por `wsl/run_wsl_pipeline.sh`:

- `all`
- `audio`
- `subs`

## Idempotencia

El pipeline es idempotente por artefacto.

- `brief.json` se sincroniza siempre desde el CSV
- `script.json` se reutiliza si ya existe
- `visual_manifest.json` se reutiliza si ya existe
- `audio/narration.wav` se reutiliza si ya existe
- `subtitles/narration.srt` se reutiliza si ya existe

Overwrite explicito:

- `NC_OVERWRITE_ALL=true`
- `NC_OVERWRITE_SCRIPT=true`
- `NC_OVERWRITE_MANIFEST=true`
- `QWEN_TTS_OVERWRITE=true`
- `WHISPERX_OVERWRITE=true`

## Artefactos por job

### `brief.json`

Instantanea del brief editorial tomada desde `data/ideas.csv`. Sirve para trazabilidad y reproceso.

### `script.json`

Contiene:

- `hook`
- `problema`
- `explicacion`
- `solucion`
- `cierre`
- `cta`
- `guion_narrado`

`guion_narrado` lo produce el LLM como una narracion coherente y natural para TTS. No debe ser una concatenacion mecanica de bloques. El pipeline valida eso y reintenta si la salida parece demasiado pegada o poco fluida.

### `status.json`

Campos minimos:

- `brief_created`
- `script_generated`
- `audio_generated`
- `subtitles_generated`
- `visual_manifest_generated`
- `export_ready`
- `last_step`
- `updated_at`

### `visual_manifest.json`

Es el contrato de handoff hacia el repositorio visual downstream. Incluye:

- `manifest_version`
- `pipeline_role`
- `downstream_target`
- `id`
- `title`
- `platform`
- `language`
- `duration_sec`
- `aspect_ratio`
- `brief_context`
- `script_context`
- `assets`
- `visual_style`
- `character_design`
- `edit_guidance`
- `scene_plan`

`scene_plan` no es un split trivial del texto. Se construye como beats narrativos: hook, problema, explicacion, pasos de solucion, cierre y CTA, con continuidad de personaje, tiempos, transiciones y bases de prompt separadas para ComfyUI y Wan.

## Contrato con el repositorio visual

El repositorio visual downstream debe tratar `visual_manifest.json` como especificacion editorial y de preproduccion.

Debe consumir:

1. `assets.audio` como pista canonica de narracion
2. `assets.subtitles` como referencia de captions y timing
3. `script_context.guion_narrado` como contexto narrativo completo
4. `character_design` como ancla de continuidad visual entre escenas
5. `scene_plan` como beats visuales y base para prompts de ComfyUI o Wan 2.2
6. `visual_style` y `brief_context` para mantener coherencia de tono, audiencia y direccion

No debe asumir que este repositorio entrega video, timeline final ni composicion multimodal cerrada. Ese trabajo pertenece al repositorio visual downstream.

## Guía de consumo downstream

Uso recomendado del repo visual:

1. cargar `visual_manifest.json`
2. abrir `assets.audio` y `assets.subtitles`
3. respetar `character_design` para no romper continuidad de sujeto, tono y presencia
4. mapear cada item de `scene_plan` a una escena o beat de edicion usando `start_sec` y `end_sec`
5. usar `comfy_prompt_base` para pipelines de imagen o edicion en ComfyUI
6. usar `wan_prompt_base` para beats de movimiento o video en Wan 2.2
7. sincronizar cortes, overlays y captions contra audio y subtitulos
8. ensamblar el video final fuera de este repositorio

## Variables de entorno utiles

### Editorial pipeline

- `NC_OLLAMA_MAX_RETRIES`
- `NC_OVERWRITE_ALL`
- `NC_OVERWRITE_SCRIPT`
- `NC_OVERWRITE_MANIFEST`

### Qwen3-TTS

- `QWEN_PYTHON`
- `QWEN_TTS_MODEL_PATH`
- `QWEN_TTS_VOICE_INSTRUCT`
- `QWEN_TTS_LANGUAGE`
- `QWEN_TTS_OVERWRITE`
- `QWEN_TTS_DEVICE`
- `QWEN_TTS_USE_FLASH_ATTN`
- `QWEN_TTS_TEST_SHORT`

### WhisperX

- `WHISPERX_PYTHON`
- `WHISPERX_BIN`
- `WHISPERX_MODEL`
- `WHISPERX_LANGUAGE`
- `WHISPERX_DEVICE`
- `WHISPERX_COMPUTE_TYPE`
- `WHISPERX_OVERWRITE`

## Verificacion rapida

1. Ejecutar `python main.py`
2. Revisar `jobs/000001/brief.json`
3. Revisar `jobs/000001/script.json`
4. Revisar `jobs/000001/visual_manifest.json`
5. En WSL2 ejecutar `bash wsl/run_wsl_pipeline.sh all`
6. Comprobar `jobs/000001/audio/narration.wav`
7. Comprobar `jobs/000001/subtitles/narration.srt`
