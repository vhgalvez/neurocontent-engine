# Guía Técnica del Sistema de Voces

## 1. Propósito de este documento

Este documento es la referencia técnica principal del sistema de voces de `neurocontent-engine`. Su objetivo es explicar de forma clara y completa:

- cómo funciona el registro de voces
- qué diferencia existe entre identidad vocal y estrategia de síntesis
- cómo se integra Qwen3-TTS en WSL2
- cómo se valida la integridad del registry
- cómo debe crearse una voz nueva
- cómo debe borrarse una voz de forma segura

También conserva contexto histórico útil para evitar errores operativos ya conocidos.

## 2. Resumen ejecutivo

El sistema actual de voces ya no trabaja solo con presets o descripciones sueltas. La voz se modela como un recurso persistente, trazable y validable.

Cada voz vive en:

```text
video-dataset/voices/<voice_id>/
```

y normalmente contiene:

- `voice.json`
- `reference.wav`
- `reference.txt`
- opcionalmente `voice_clone_prompt.json`

El índice global vive en:

```text
video-dataset/voices/voices_index.json
```

El proyecto ahora protege explícitamente varios problemas que antes podían ocurrir:

- duplicidad silenciosa de `voice_name`
- alias humanos con formato parecido a `voice_id`
- inconsistencias entre `voices_index.json`, `voice.json` y la carpeta física
- borrados manuales que dejaban referencias colgantes

## 3. Entorno funcional verificado para Qwen3-TTS

### 3.1 Plataforma validada

El entorno operativo verificado para audio y voces es:

- Windows + WSL2
- Ubuntu 24.04 LTS
- GPU NVIDIA RTX 4070
- entorno conda `qwen_gpu`

Python válido:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/python
```

Comando recomendado:

```bash
conda activate qwen_gpu
```

El `venv` antiguo:

```bash
/home/victory/Qwen3-TTS/venv/bin/python
```

ya no debe usarse.

### 3.2 `QWEN_PYTHON` y wrappers Bash

Los wrappers de `wsl/` usan `QWEN_PYTHON` para decidir qué Python ejecuta los scripts reales:

- `wsl/run_design_voice.sh`
- `wsl/run_audio.sh`
- `wsl/run_generate_audio_from_prompt.sh`
- `wsl/run_delete_voice.sh`

Fallback correcto:

```bash
export QWEN_PYTHON="${QWEN_PYTHON:-/home/victory/miniconda3/envs/qwen_gpu/bin/python}"
```

Esto significa:

- si `QWEN_PYTHON` no existe, el wrapper usará el Python del entorno validado
- si `QWEN_PYTHON` ya viene exportado externamente, se respetará el override

## 4. Arquitectura conceptual del sistema de voces

### 4.1 Qué problema resuelve

El objetivo del sistema no es solo sintetizar audio. También necesita:

- mantener identidad vocal consistente entre jobs
- permitir reutilización controlada
- soportar trazabilidad operativa
- separar identidad vocal de estrategia de síntesis
- evitar corrupción lógica del registry

### 4.2 Diferencia entre identidad vocal y estrategia de síntesis

Una voz registrada y la estrategia usada para sintetizar no son lo mismo.

Una voz registrada describe la identidad persistente:

- `voice_id`
- `voice_name`
- `voice_description`
- `seed`
- `model_name`
- `reference_file`
- `voice_mode`
- `tts_strategy_default`

La estrategia de síntesis describe cómo se intentó reutilizar esa voz en una generación concreta:

- `description_seed_preset`
- `reference_conditioned`
- `clone_prompt`
- `legacy_preset_fallback`

La estrategia realmente usada queda trazada en:

- `job.json`
- `status.json`
- logs del job

## 5. `voice_id` vs `voice_name`

### 5.1 `voice_id`

`voice_id` es el identificador técnico persistente del sistema.

Ejemplos:

- `voice_global_0001`
- `voice_job_000001_0001`

Propiedades:

- lo genera el sistema
- debe ser estable
- se usa como clave técnica
- se usa para ubicar la carpeta física de la voz

### 5.2 `voice_name`

`voice_name` es el alias lógico o humano de la voz.

Ejemplos:

- `marca_personal_es`
- `narradora_documental`
- `campana_lanzamiento_q2`

Propiedades:

- lo elige el usuario o el flujo de alta
- describe la voz de forma semántica
- no debe usarse como ID técnico

### 5.3 Bug histórico y corrección

Antes podían coexistir casos confusos como este:

- `voice_id = voice_global_0002`
- `voice_name = voice_global_0001`

Ese caso era peligroso porque mezclaba el identificador técnico con el alias humano y abría la puerta a decisiones operativas equivocadas.

Ahora el sistema aplica estas reglas:

- `voice_name` debe ser único en todo el registry
- `voice_name` no puede parecer un `voice_id` interno
- si el nombre ya existe, el alta aborta con error explícito

La validación quedó centralizada en:

- `voice_registry.py`

## 6. Estructura física del registry

Estructura esperada:

```text
video-dataset/
└── voices/
    ├── voice_global_0001/
    │   ├── voice.json
    │   ├── reference.wav
    │   ├── reference.txt
    │   └── voice_clone_prompt.json
    ├── voice_global_0002/
    │   ├── voice.json
    │   ├── reference.wav
    │   └── reference.txt
    └── voices_index.json
```

### 6.1 `voice.json`

Es la metadata completa de una voz concreta.

Campos habituales:

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
- `reference_text_file`
- `voice_clone_prompt_path`
- `voice_preset`
- `voice_mode`
- `tts_strategy_default`
- `supports_reference_conditioning`
- `supports_clone_prompt`
- `engine`
- `status`
- `notes`
- `created_at`
- `updated_at`

### 6.2 `voices_index.json`

Es el índice global de voces registradas. Su función es permitir:

- listar voces
- resolver voces por `voice_id`
- calcular nuevos IDs
- validar integridad global

## 7. Flujo de creación de voces

### 7.1 Script principal de diseño de voz

El flujo de diseño de voz entra normalmente por:

```bash
bash wsl/run_design_voice.sh ...
```

y ejecuta:

- `wsl/design_voice.py`

### 7.2 Qué hace el flujo

En términos generales:

1. valida el entorno y el registry
2. resuelve modelo y device
3. genera audio de referencia con Qwen3-TTS VoiceDesign
4. registra o actualiza la voz en `voice.json` y `voices_index.json`
5. guarda `reference.wav`
6. guarda `reference.txt`
7. opcionalmente asigna la voz al job

### 7.3 Reglas nuevas de creación

Al crear una voz nueva, el sistema aplica validaciones estrictas:

- `voice_name` no puede estar vacío
- `voice_name` debe ser único
- `voice_name` no puede parecer un `voice_id` interno
- si el registry ya está inconsistente, el alta no debe continuar silenciosamente

Error esperado si el nombre ya existe:

```text
ERROR: ya existe una voz con ese nombre
```

Error esperado si el alias parece un ID interno:

```text
ERROR: voice_name no puede parecer un voice_id interno del sistema
```

### 7.4 Ejemplo de creación correcta

```bash
conda activate qwen_gpu
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine

bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

## 8. Resolución de voz al generar audio

El flujo de audio resuelve la voz en este orden:

1. `--voice-id` explícito
2. voz ya asignada en `job.json`
3. `VIDEO_DEFAULT_VOICE_ID`
4. fallback de compatibilidad cuando aplica

Esto es importante porque:

- `VIDEO_DEFAULT_VOICE_ID` selecciona una voz registrada
- no obliga por sí solo a un conditioning acústico concreto
- la estrategia real depende de `voice_mode`, `tts_strategy_default` y del flujo disponible

## 9. Validación del índice de voces

### 9.1 Qué valida ahora el sistema

La validación del índice ya no se limita a detectar `voice_id` duplicados. Ahora comprueba:

- `registry_version` soportado
- `voice_id` duplicado
- `voice_name` duplicado
- carpeta física existente para cada `voice_id`
- existencia de `voice.json`
- consistencia entre `voice.json` y `voices_index.json`
- validez de `voice_mode`
- validez de `tts_strategy_default`

### 9.2 Por qué era necesario

Antes podían existir inconsistencias silenciosas:

- carpeta borrada manualmente pero índice todavía presente
- `voice.json` distinto de lo que decía `voices_index.json`
- dos voces con el mismo alias lógico

Ese tipo de corrupción lógica es peligrosa porque:

- el sistema sigue pareciendo funcional
- la operación humana se vuelve confusa
- se toman decisiones con información engañosa

## 10. Borrado correcto de voces

### 10.1 Qué no debe hacerse

No debe borrarse manualmente una carpeta dentro de:

```text
video-dataset/voices/
```

porque eso puede dejar:

- entrada viva en `voices_index.json`
- referencias activas en jobs
- inconsistencia entre índice y disco

### 10.2 Flujo oficial de borrado

El borrado oficial se hace mediante:

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

Ese wrapper ejecuta:

- `wsl/delete_voice.py`

que a su vez usa la lógica central en:

- `voice_registry.py`

### 10.3 Qué valida el borrado

Antes de borrar una voz, el sistema:

1. valida que `voice_id` se haya informado
2. valida que exista en `voices_index.json`
3. valida que exista la carpeta física
4. valida que exista `voice.json`
5. valida que `voice.json` corresponda al `voice_id` correcto
6. revisa referencias activas en jobs

### 10.4 Referencias activas en jobs

El borrado se bloquea si la voz sigue apareciendo en:

- `job.voice.voice_id`
- `job.audio_synthesis.voice_id`

Esto evita borrar una voz que todavía forma parte del contrato operativo o histórico de un job.

### 10.5 Rollback

El borrado se hace de forma defensiva:

- la carpeta se mueve primero a un temporal
- se reescribe el índice
- se valida el estado final
- solo si todo cuadra se elimina físicamente la carpeta temporal

Si algo falla, se hace rollback automático de:

- índice
- carpeta de voz

## 11. Troubleshooting del sistema de voces

### 11.1 Error por `voice_name` duplicado

```text
ERROR: ya existe una voz con ese nombre
```

Qué significa:

- ya existe otra voz con ese alias lógico
- el sistema está evitando una ambigüedad operativa

Qué hacer:

- usar otro `voice_name`
- o reutilizar la voz ya existente mediante su `voice_id`

### 11.2 Error por `voice_name` con forma de ID interno

```text
ERROR: voice_name no puede parecer un voice_id interno del sistema
```

Qué significa:

- el alias humano propuesto se parece a un ID técnico reservado

Qué hacer:

- usar un alias semántico real, por ejemplo `marca_personal_es`

### 11.3 Error al borrar una voz

```text
ERROR: no se puede eliminar voice_id=... porque sigue referenciada en jobs
```

Qué significa:

- la voz todavía forma parte de uno o varios jobs

Qué hacer:

- revisar esos jobs
- decidir si deben seguir apuntando a esa voz
- solo después intentar el borrado otra vez

## 12. Comandos operativos reales

### 12.1 Activar entorno

```bash
conda activate qwen_gpu
which python
python -V
```

### 12.2 Validar GPU

```bash
python -c "import torch; print('cuda', torch.cuda.is_available()); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Ninguna')"
```

### 12.3 Validar `qwen_tts`

```bash
python -c "import qwen_tts; print('qwen_tts OK')"
```

### 12.4 Diseñar una voz

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

### 12.5 Generar audio de un job

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

### 12.6 Generar audio clone/reference

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --job-id 000001 \
  --voice-id voice_global_0001 \
  --overwrite
```

### 12.7 Borrar una voz correctamente

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

## 13. Buenas prácticas operativas

- usar siempre `conda activate qwen_gpu` antes de operar audio y voces
- tratar `voice_id` como identificador técnico y `voice_name` como alias lógico
- no editar manualmente `voices_index.json` salvo mantenimiento excepcional
- no borrar carpetas de voces a mano
- revisar `job.json` y `status.json` cuando haya dudas de trazabilidad

## 14. Contexto histórico útil

### 14.1 Warnings no bloqueantes

Durante la validación del entorno aparecieron warnings útiles para referencia futura, pero no bloqueantes:

```text
Warning: flash-attn is not installed. Will only run the manual PyTorch version.
```

y:

```text
onnxruntime ... Failed to open file: "/sys/class/drm/card0/device/vendor"
```

Ambos mensajes no invalidaron el funcionamiento base del sistema.

### 14.2 Compatibilidad y legado

El proyecto mantiene cierta compatibilidad de lectura con artefactos legacy, pero la operación nueva debe seguir el modelo actual:

- registry persistente de voces
- `job.json` como contrato del job
- wrappers WSL con `QWEN_PYTHON` apuntando al entorno conda correcto
