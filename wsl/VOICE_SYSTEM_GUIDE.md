# Guía completa de voces en `neurocontent-engine`

Este documento explica, de forma clara y práctica, cómo funciona el sistema de voces en `vhgalvez/neurocontent-engine`, cómo crear una **voz global para todo el proyecto**, cómo crear una **voz individual por job**, cómo reutilizar una voz ya registrada, y qué archivos revisar para tener trazabilidad completa.

---

## 1. Qué problema resuelve este sistema

El proyecto no trata la voz como un simple preset suelto.  
La voz ahora se maneja como una **identidad persistente**, con:

- un `voice_id`
- un `scope`
- metadata reproducible
- referencia en disco
- asignación al job
- trazabilidad en `job.json` y `status.json`

Eso permite:

- mantener una voz estable para todos los contenidos
- usar voces distintas por campaña o personaje
- saber exactamente qué voz se usó en cada audio
- volver a generar audio con la misma identidad vocal

---

## 2. Las 3 formas reales de trabajar la voz

Tienes **3 formas reales** de trabajar la voz en `neurocontent-engine`.

### 2.1 Voz global para todo el proyecto

Una sola voz reutilizable para muchos jobs.

Casos típicos:

- tu marca personal
- mismo narrador para todos los videos
- identidad vocal consistente para todo el canal

---

### 2.2 Voz individual por job

Una voz específica para un job concreto.

Casos típicos:

- una campaña distinta
- un personaje diferente
- una prueba aislada
- una voz especial para un contenido puntual

---

### 2.3 Selección manual de una voz ya registrada

No creas una voz nueva.  
Simplemente eliges explícitamente una voz ya existente mediante su `voice_id`.

Esto sirve cuando:

- ya tienes una voz global registrada
- ya tienes varias voces creadas
- quieres controlar exactamente qué voz usar en un job

---

## 3. Cómo funciona realmente la selección de voz

La precedencia real de selección de voz está documentada así:

1. `--voice-id` explícito
2. voz ya asignada en `jobs/<job_id>/job.json`
3. `VIDEO_DEFAULT_VOICE_ID` como voz global por defecto
4. fallback legacy: auto-registro de una voz `job` desde preset/seed si no hay nada asignado

Esto significa:

- si tú pasas `--voice-id`, esa voz manda
- si no pasas nada, el sistema mira si el job ya tiene una voz asignada
- si tampoco hay voz en el job, usa `VIDEO_DEFAULT_VOICE_ID`
- y si no existe ninguna de esas opciones, intenta crear una voz de compatibilidad por job usando el preset/seed actual

---

## 4. Variables clave que intervienen

El wrapper `wsl/run_audio.sh` exporta estas variables relevantes:

- `QWEN_TTS_MODEL_PATH`
- `QWEN_TTS_VOICE_PRESET`
- `QWEN_TTS_SEED`
- `QWEN_TTS_LANGUAGE`
- `QWEN_TTS_OVERWRITE`
- `QWEN_TTS_DEVICE`
- `QWEN_TTS_USE_FLASH_ATTN`
- `VIDEO_DATASET_ROOT`
- `VIDEO_JOBS_ROOT`

En el wrapper `wsl/run_design_voice.sh` también se usan:

- `QWEN_PYTHON`
- `VOICE_ENV_FILE`
- `DOTENV_FILE`
- `VIDEO_DATASET_ROOT`
- `VIDEO_JOBS_ROOT`

Estas variables se cargan desde:

- `.env`
- `wsl/voices.env`

si existen.

---

## 5. Rutas reales del sistema

### Dataset principal

```text
/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset
```

### Jobs root

```text
/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs
```

### Registry de voces

```text
/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/voices
```

---

## 6. Dónde se guardan las voces

La estructura esperada es esta:

```text
video-dataset/
└── voices/
    ├── voice_global_0001/
    │   ├── voice.json
    │   ├── reference.wav
    │   ├── reference.txt
    │   └── voice_clone_prompt.json
    └── voices_index.json
```

### Qué significa cada archivo

#### `voices_index.json`
Índice general de voces registradas.

#### `voices/<voice_id>/voice.json`
Metadata completa de esa voz.

#### `reference.wav`
Audio de referencia generado o guardado para esa voz.

#### `reference.txt`
Texto usado para generar o acompañar la referencia.

#### `voice_clone_prompt.json`
Prompt o metadata asociada a clonación/consistencia si el flujo lo requiere.

---

## 7. Qué guarda cada voz

Cada voz puede contener campos como:

- `voice_id`
- `scope`
- `job_id`
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

---

## 8. Scopes soportados

### `global`
Voz reutilizable entre muchos jobs.

Ejemplo:

```text
voice_global_0001
```

---

### `job`
Voz específica de un solo job.

Ejemplo:

```text
voice_job_000001_0001
```

---

## 9. Cómo crear una voz para todo el proyecto

## Cuándo usar esto

Usa este modo cuando quieras:

- una sola voz para toda tu marca
- consistencia máxima entre muchos jobs
- una identidad vocal unificada

---

## Comando recomendado

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine
```

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

---

## Qué hace ese comando por dentro

El wrapper:

```text
wsl/run_design_voice.sh
```

1. carga `.env` y `wsl/voices.env`
2. exporta:
   - `QWEN_TTS_MODEL_PATH`
   - `QWEN_TTS_DEVICE`
   - `VIDEO_DATASET_ROOT`
   - `VIDEO_JOBS_ROOT`
3. llama a:

```text
wsl/design_voice.py
```

Ese script:

1. carga el modelo VoiceDesign de Qwen3-TTS
2. resuelve la ruta del modelo
3. configura seed y device
4. genera una referencia de voz con `generate_voice_design(...)`
5. registra la voz en el registry con `register_voice(...)`
6. guarda:
   - `voice.json`
   - `reference.wav`
   - `reference.txt`
7. si se le pasa `--assign-to-job` y `--job-id`, también la asigna al job

---

## Resultado esperado

Se creará algo como esto:

```text
video-dataset/voices/voice_global_0001/
├── voice.json
├── reference.wav
└── reference.txt
```

---

## Cómo usar esa voz en todos los jobs

Tienes dos opciones.

### Opción A — pasar `--voice-id` cada vez

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
bash wsl/run_audio.sh --job-id 000002 --voice-id voice_global_0001 --overwrite
bash wsl/run_audio.sh --job-id 000003 --voice-id voice_global_0001 --overwrite
```

### Opción B — definir una voz global por defecto

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
```

Luego:

```bash
bash wsl/run_audio.sh --job-id 000001
bash wsl/run_audio.sh --job-id 000002
bash wsl/run_audio.sh --job-id 000003
```

### Recomendación
Para una marca personal, esta es la mejor estrategia.

---

## 10. Cómo crear una voz individual por job

## Cuándo usar esto

Úsalo cuando un job concreto necesite su propia voz.

Ejemplos:

- una campaña especial
- un personaje diferente
- una prueba A/B
- una narrativa con identidad vocal propia

---

## Comando recomendado

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name campaña_a \
  --description "Voz específica de campaña." \
  --reference-text "Hola, esta es la voz de esta campaña." \
  --assign-to-job
```

---

## Qué hace ese comando

1. genera la referencia de voz
2. registra la voz como `scope=job`
3. la guarda con un `voice_id` tipo:

```text
voice_job_000001_0001
```

4. la asigna a `jobs/000001/job.json` porque usaste `--assign-to-job`

---

## Resultado esperado

Después de eso, el job `000001` queda ligado a esa voz.

Y luego puedes ejecutar simplemente:

```bash
bash wsl/run_audio.sh --job-id 000001
```

sin necesidad de pasar `--voice-id`.

---

## 11. Cómo usar una voz ya registrada manualmente

Si ya conoces el `voice_id`, puedes forzar su uso.

### Ejemplo

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

Esto tiene máxima prioridad.

---

## 12. Cómo funciona realmente la generación de audio

El script real es:

```text
wsl/generar_audio_qwen.py
```

### Flujo real del script

#### 1. Valida el registry
Al arrancar ejecuta:

```python
validate_voice_index(get_runtime_paths())
```

Eso comprueba que el índice de voces sea válido estructuralmente.

---

#### 2. Resuelve la voz para el job
Llama a una función equivalente a:

```python
resolve_or_register_voice(...)
```

La lógica es:

- si pasaste `--voice-id`, usa esa voz
- si el job ya tiene voz asignada, usa esa
- si no, intenta resolver compatibilidad legacy
- si no encuentra nada, puede auto-registrar una voz `job` usando:
  - preset actual
  - seed actual
  - idioma actual

---

#### 3. Construye la instrucción vocal
Usa presets como:

- `mujer_podcast_seria_35_45`
- `mujer_documental_neutra`
- `hombre_narrador_sobrio`

Y a partir de esos valores construye `voice_instruct`.

---

#### 4. Genera el audio WAV
Después:

- escribe el audio del job
- actualiza la trazabilidad en `job.json`
- actualiza `status.json`

---

## 13. Presets de voz disponibles

En el código actual aparecen estos presets:

### `mujer_podcast_seria_35_45`
- voz femenina madura
- seria
- profesional
- creíble

### `mujer_documental_neutra`
- voz femenina adulta
- neutra
- profesional
- serena

### `hombre_narrador_sobrio`
- voz masculina adulta
- sobria
- madura
- segura

---

## 14. Qué actualiza el sistema cuando genera audio

Al generar audio, el job queda trazado con campos como:

- `voice_id`
- `voice_scope`
- `voice_source`
- `voice_name`
- `voice_selection_mode`
- `voice_model_name`
- `voice_reference_file`
- `audio_file`
- `audio_generated_at`

Eso se escribe en:

- `job.json`
- `status.json`

---

## 15. Naming real de archivos del job

El proyecto usa naming basado en `job_id`.

### Ejemplo para `000001`

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

---

## 16. Qué revisar para saber qué voz usó un job

Debes revisar estos tres sitios:

### 1. `job.json`
Ruta típica:

```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/job.json
```

### 2. `status.json`
Ruta típica:

```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/status.json
```

### 3. `voice.json` de la voz elegida
Ruta típica:

```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/voices/voice_global_0001/voice.json
```

---

## 17. Campos más importantes para trazabilidad

Los campos clave que debes mirar son:

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

Con eso puedes reproducir exactamente la identidad vocal.

---

## 18. Flujo recomendado para tu caso

Como quieres control fuerte y consistencia, yo te recomiendo esta estrategia.

---

## Escenario A — misma voz para toda tu marca

### Paso 1 — crea una voz global principal

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, sobria, profesional, clara y estable para la marca personal." \
  --reference-text "Hola, esta es la voz oficial de la marca y se utilizará en todos los contenidos."
```

### Paso 2 — declárala como default global

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
```

### Paso 3 — genera audio en los jobs

```bash
bash wsl/run_audio.sh --job-id 000001
bash wsl/run_audio.sh --job-id 000002
bash wsl/run_audio.sh --job-id 000003
```

### Ventajas
- máxima consistencia
- menos caos
- identidad de marca fuerte
- trazabilidad más simple

---

## Escenario B — voz distinta para un job concreto

### Paso 1 — crea una voz específica para el job

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name personaje_000001 \
  --description "Voz seria, intensa y emocional para este job." \
  --reference-text "Hola, esta voz pertenece solo a esta pieza." \
  --assign-to-job
```

### Paso 2 — genera el audio

```bash
bash wsl/run_audio.sh --job-id 000001
```

### Ventajas
- ese job queda atado a su propia identidad vocal
- ideal para campañas y personajes

---

## Escenario C — forzar manualmente una voz existente

### Comando

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

### Ventaja
Control absoluto.

---

## 19. Comandos completos listos para usar

## Crear voz global
```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

## Crear voz por job
```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name campaña_a \
  --description "Voz específica de campaña." \
  --reference-text "Hola, esta es la voz de esta campaña." \
  --assign-to-job
```

## Usar una voz concreta en un job
```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

## Definir voz global por defecto
```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
```

## Generar audio con la voz global por defecto
```bash
bash wsl/run_audio.sh --job-id 000001
```

## Generar audio para varios jobs con la voz global por defecto
```bash
bash wsl/run_audio.sh --job-id 000001
bash wsl/run_audio.sh --job-id 000002
bash wsl/run_audio.sh --job-id 000003
```

---

## 20. Verificación práctica recomendada

Después de generar audio, revisa:

### Job document
```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/job.json
```

### Status
```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/status.json
```

### Registry
```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/voices/voices_index.json
```

### Audio resultante
```bash
ls -l /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/audio/
```

---

## 21. Recomendación final

Para tu caso, yo usaría:

- **una voz global estable** para la mayoría del proyecto
- **voces por job** solo cuando quieras:
  - personajes distintos
  - campañas especiales
  - pruebas puntuales

Eso te da:

- consistencia
- claridad operativa
- menos caos
- mejor identidad de marca
- trazabilidad mucho más limpia

---

## 22. Conclusión

### Para todo el proyecto
Usa:

```bash
bash wsl/run_design_voice.sh --scope global ...
```

y luego:

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
```

### Para un job específico
Usa:

```bash
bash wsl/run_design_voice.sh --scope job --job-id 000001 --assign-to-job
```

### Para forzar manualmente una voz existente
Usa:

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001
```

---

## 23. Sugerencia de nombre para guardar este documento

Puedes guardarlo como:

```text
VOICE_SYSTEM_GUIDE.md
```

o dentro del repo como:

```text
docs/VOICE_SYSTEM_GUIDE.md
```
