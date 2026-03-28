# Guia Completa de Voces en `neurocontent-engine`

Esta guia explica como funciona el sistema de voces en `vhgalvez/neurocontent-engine`, como crear una voz global, como crear una voz por job, como reutilizar una voz ya registrada y que archivos revisar para tener trazabilidad completa.

## Nota Semantica Importante

Una voz registrada y una estrategia de sintesis no son lo mismo.

- `VIDEO_DEFAULT_VOICE_ID` solo selecciona la voz registrada.
- `voice_mode` indica como se espera reutilizar esa voz.
- `tts_strategy_default` indica la estrategia pedida por defecto.
- el flujo de audio registra siempre la estrategia realmente usada y si hubo fallback.

Modos soportados:

- `design_only`
- `reference_conditioned`
- `clone_prompt`

Importante: una voz creada con `wsl/design_voice.py` queda registrada como `design_only`. Su `reference.wav` sirve como artefacto de referencia y trazabilidad, pero no implica por si solo que el flujo `run_audio.sh` vaya a condicionarse directamente con ese wav en todos los motores o estrategias.

## 1. Que problema resuelve este sistema

El proyecto no trata la voz como un preset suelto. La voz se maneja como una identidad persistente con:

- `voice_id`
- `scope`
- metadata reproducible
- referencia en disco
- asignacion al job
- trazabilidad en `job.json` y `status.json`

Eso permite:

- mantener una voz estable para todos los contenidos
- usar voces distintas por campaña o personaje
- saber exactamente que voz se uso en cada audio
- volver a generar audio con la misma identidad vocal

## 2. Formas de trabajar la voz

### 2.1 Voz global para todo el proyecto

Una sola voz reutilizable para muchos jobs.

Casos tipicos:

- tu marca personal
- mismo narrador para todos los videos
- identidad vocal consistente para todo el canal

### 2.2 Voz individual por job

Una voz especifica para un job concreto.

Casos tipicos:

- una campaña distinta
- un personaje diferente
- una prueba aislada
- una voz especial para un contenido puntual

### 2.3 Seleccion manual de una voz ya registrada

No creas una voz nueva. Eliges explicitamente una voz ya existente mediante su `voice_id`.

Sirve cuando:

- ya tienes una voz global registrada
- ya tienes varias voces creadas
- quieres controlar exactamente que voz usar en un job

## 3. Precedencia real de seleccion de voz

La seleccion de voz sigue este orden:

1. `--voice-id` explicito
2. voz ya asignada en `jobs/<job_id>/job.json`
3. `VIDEO_DEFAULT_VOICE_ID` como voz global por defecto
4. fallback legacy: auto-registro de una voz `job` desde preset y seed si no hay nada asignado

Esto significa:

- si pasas `--voice-id`, esa voz manda
- si no pasas nada, el sistema mira si el job ya tiene una voz asignada
- si tampoco hay voz en el job, usa `VIDEO_DEFAULT_VOICE_ID`
- si no existe ninguna de esas opciones, intenta crear una voz de compatibilidad por job

## 4. Donde vive la configuracion real de la voz

La configuracion no vive en un solo archivo. Se reparte en varias capas.

### 4.1 Wrappers Bash

Scripts:

- `wsl/run_design_voice.sh`
- `wsl/run_audio.sh`

Preparan el entorno y cargan variables como:

- `QWEN_TTS_MODEL_PATH`
- `QWEN_TTS_DEVICE`
- `QWEN_TTS_VOICE_PRESET`
- `QWEN_TTS_SEED`
- `QWEN_TTS_LANGUAGE`
- `VIDEO_DATASET_ROOT`
- `VIDEO_JOBS_ROOT`

Tambien cargan:

- `.env`
- `wsl/voices.env`

### 4.2 Diseno de voz

El script `wsl/design_voice.py` crea una identidad vocal nueva y configurable con parametros como:

- `scope`
- `voice_name`
- `description`
- `reference_text`
- `language`
- `seed`
- `model_path`
- `device`
- `voice_id` opcional
- `assign_to_job` opcional

Ademas:

- genera `reference.wav`
- registra la voz en el registry
- puede asignarla al job

### 4.3 Resolucion de voz al generar audio

El script `wsl/generar_audio_qwen.py` decide que voz usar realmente en cada job siguiendo la precedencia ya descrita.

Tambien:

- construye la instruccion vocal final (`voice_instruct`)
- genera el `wav`
- actualiza `job.json`
- actualiza `status.json`

### 4.4 Persistencia y trazabilidad

La configuracion y el uso real de la voz quedan registrados en:

- `video-dataset/voices/voices_index.json`
- `video-dataset/voices/<voice_id>/voice.json`
- `jobs/<job_id>/job.json`
- `jobs/<job_id>/status.json`

## 5. Variables clave

### En `wsl/run_audio.sh`

Variables relevantes:

- `QWEN_TTS_MODEL_PATH`
- `QWEN_TTS_VOICE_PRESET`
- `QWEN_TTS_SEED`
- `QWEN_TTS_LANGUAGE`
- `QWEN_TTS_OVERWRITE`
- `QWEN_TTS_DEVICE`
- `QWEN_TTS_USE_FLASH_ATTN`
- `VIDEO_DATASET_ROOT`
- `VIDEO_JOBS_ROOT`

### En `wsl/run_design_voice.sh`

Variables relevantes:

- `QWEN_PYTHON`
- `VOICE_ENV_FILE`
- `DOTENV_FILE`
- `VIDEO_DATASET_ROOT`
- `VIDEO_JOBS_ROOT`

### Archivos de entorno

Estas variables se cargan desde:

- `.env`
- `wsl/voices.env`

## 6. Rutas reales del sistema

Dataset principal:

```bash
/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset
```

Jobs root:

```bash
/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs
```

Registry de voces:

```bash
/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/voices
```

## 7. Donde se guardan las voces

Estructura esperada:

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

Que significa cada archivo:

- `voices_index.json`: indice general de voces registradas
- `voices/<voice_id>/voice.json`: metadata completa de esa voz
- `reference.wav`: audio de referencia generado o guardado para esa voz
- `reference.txt`: texto usado para generar o acompanar la referencia
- `voice_clone_prompt.json`: metadata asociada a clonacion o consistencia

## 8. Que guarda cada voz

Campos tipicos:

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

## 9. Scopes soportados

`global`

- voz reutilizable entre muchos jobs
- ejemplo: `voice_global_0001`

`job`

- voz especifica de un solo job
- ejemplo: `voice_job_000001_0001`

## 10. Crear una voz para todo el proyecto

Usa este modo cuando quieras:

- una sola voz para toda tu marca
- consistencia maxima entre muchos jobs
- una identidad vocal unificada

Primero ve a la raiz del repo:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine
```

Luego ejecuta:

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

Que hace ese comando:

- carga `.env` y `wsl/voices.env`
- exporta variables del entorno de TTS
- llama a `wsl/design_voice.py`
- genera la referencia
- registra la voz en el registry
- opcionalmente la asigna a un job

Resultado esperado:

```text
video-dataset/voices/voice_global_0001/
├── voice.json
├── reference.wav
└── reference.txt
```

## 11. Usar esa voz en todos los jobs

### Opcion A: pasar `--voice-id` cada vez

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
bash wsl/run_audio.sh --job-id 000002 --voice-id voice_global_0001 --overwrite
bash wsl/run_audio.sh --job-id 000003 --voice-id voice_global_0001 --overwrite
```

### Opcion B: definir una voz global por defecto

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"

bash wsl/run_audio.sh --job-id 000001
bash wsl/run_audio.sh --job-id 000002
bash wsl/run_audio.sh --job-id 000003
```

Recomendacion: para una marca personal, esta suele ser la mejor estrategia.

## 12. Crear una voz individual por job

Usalo cuando un job concreto necesite su propia voz.

Ejemplos:

- una campaña especial
- un personaje diferente
- una prueba A/B
- una narrativa con identidad vocal propia

Comando recomendado:

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name campaña_a \
  --description "Voz específica de campaña." \
  --reference-text "Hola, esta es la voz de esta campaña." \
  --assign-to-job
```

Despues puedes ejecutar:

```bash
bash wsl/run_audio.sh --job-id 000001
```

## 13. Usar una voz ya registrada manualmente

Si ya conoces el `voice_id`, puedes forzar su uso:

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

Eso tiene maxima prioridad.

## 14. Como funciona realmente la generacion de audio

El script real es:

```text
wsl/generar_audio_qwen.py
```

Flujo general:

1. valida el registry
2. resuelve la voz para el job
3. construye la instruccion vocal
4. genera el `wav`
5. actualiza `job.json`
6. actualiza `status.json`

## 15. Presets de voz disponibles

En el codigo actual aparecen presets como:

- `mujer_podcast_seria_35_45`
- `mujer_documental_neutra`
- `hombre_narrador_sobrio`

## 16. Que actualiza el sistema cuando genera audio

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

## 17. Naming real de archivos del job

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

## 18. Que revisar para saber que voz uso un job

Debes revisar estos tres sitios:

### `job.json`

```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/job.json
```

### `status.json`

```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/status.json
```

### `voice.json` de la voz elegida

```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/voices/voice_global_0001/voice.json
```

## 19. Campos mas importantes para trazabilidad

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

## 20. Verificacion de creacion de voz global

Si al ejecutar el diseno de voz ves algo como esto:

```text
[design_voice] voice_id=voice_global_0001
[design_voice] Referencia guardada en /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/voices/voice_global_0001/reference.wav
Exit code: 0
```

Eso significa que:

- el modelo se cargo correctamente
- la referencia se genero
- la voz se registro en el registry
- se creo un `voice_id` estable
- se guardo `reference.wav`
- el flujo termino sin error fatal

Siguientes pasos recomendados:

### Paso 1: revisar la voz creada

```bash
ls -l /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/voices/voice_global_0001
```

Normalmente deberias ver:

- `voice.json`
- `reference.wav`
- `reference.txt`
- `voice_clone_prompt.json` si aplica

### Paso 2: revisar el indice general

```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/voices/voices_index.json
```

Busca una entrada con:

```text
voice_id = voice_global_0001
```

### Paso 3: definir la voz global por defecto

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
```

### Paso 4: generar audio real para un job

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

Ruta esperada del audio:

```bash
/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/audio/000001_narration.wav
```

### Paso 5: revisar la trazabilidad del job

```bash
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/job.json
cat /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001/status.json
```

Campos a confirmar:

- `voice_id`
- `voice_scope`
- `voice_source`
- `voice_name`
- `voice_selection_mode`
- `voice_model_name`
- `voice_reference_file`
- `audio_file`
- `audio_generated_at`

## 21. Flujo recomendado

### Escenario A: misma voz para toda tu marca

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, sobria, profesional, clara y estable para la marca personal." \
  --reference-text "Hola, esta es la voz oficial de la marca y se utilizara en todos los contenidos."

export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"

bash wsl/run_audio.sh --job-id 000001
bash wsl/run_audio.sh --job-id 000002
bash wsl/run_audio.sh --job-id 000003
```

```bash
bash -x wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca." \
  2>&1 | tee /tmp/run_design_voice_debug.log
  ```

```bash
tail -n 120 /tmp/run_design_voice_debug.log
```

```bash
bash wsl/run_audio.sh
```


Ventajas:

- maxima consistencia
- menos caos
- identidad de marca fuerte
- trazabilidad simple

### Escenario B: voz distinta para un job concreto

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name personaje_000001 \
  --description "Voz seria, intensa y emocional para este job." \
  --reference-text "Hola, esta voz pertenece solo a esta pieza." \
  --assign-to-job

bash wsl/run_audio.sh --job-id 000001
```

### Escenario C: forzar manualmente una voz existente

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

## 22. Comandos listos para usar

### Crear voz global

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

### Crear voz por job

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name campaña_a \
  --description "Voz específica de campaña." \
  --reference-text "Hola, esta es la voz de esta campaña." \
  --assign-to-job
```




### Usar una voz concreta en un job

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

### Definir voz global por defecto

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
```

### Generar audio con la voz global por defecto

```bash
bash wsl/run_audio.sh --job-id 000001
```

### Generar audio para varios jobs

```bash
bash wsl/run_audio.sh --job-id 000001
bash wsl/run_audio.sh --job-id 000002
bash wsl/run_audio.sh --job-id 000003
```

## 23. Verificacion practica recomendada

Despues de generar audio, revisa:

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

## 24. Recomendacion final

Para la mayoria del proyecto:

- usa una voz global estable
- usa voces por job solo para personajes distintos, campañas especiales o pruebas puntuales

Eso te da:

- consistencia
- claridad operativa
- menos caos
- mejor identidad de marca
- trazabilidad mas limpia

## 25. Conclusión

Para todo el proyecto:

```bash
bash wsl/run_design_voice.sh --scope global ...
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
```

Para un job especifico:

```bash
bash wsl/run_design_voice.sh --scope job --job-id 000001 --assign-to-job
```

Para forzar manualmente una voz existente:

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001
```
