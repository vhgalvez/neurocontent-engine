# AUDIO GUIDE v2

## 1. Objetivo del módulo de audio

Este proyecto tiene **dos flujos reales** de audio, verificados contra el código actual en:

- `wsl/generar_audio_qwen.py`
- `wsl/design_voice.py`
- `wsl/generate_audio_from_prompt.py`
- `wsl/run_audio.sh`
- `wsl/run_design_voice.sh`
- `wsl/run_generate_audio_from_prompt.sh`

Los dos flujos son:

1. **Flujo rápido con VoiceDesign**
   - Diseñas la voz con lenguaje natural.
   - Generas audio directamente.
   - Es el flujo más simple para pruebas rápidas o jobs directos.

2. **Flujo profesional con VoiceDesign + Base**
   - Diseñas una voz de referencia.
   - Generas `reference.wav`.
   - Creas un `voice_clone_prompt`.
   - Reutilizas la misma identidad vocal en muchos clips.

---

## 2. Diferencia entre VoiceDesign, CustomVoice y Base

### 2.1. VoiceDesign

- Modelo:
  - `Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- Método oficial usado:
  - `generate_voice_design(...)`
- Casos de uso:
  - describir una voz con lenguaje natural
  - generar pruebas rápidas
  - generar audio directo por job
- Scripts del proyecto que lo usan:
  - `wsl/generar_audio_qwen.py`
  - `wsl/design_voice.py`

### 2.2. CustomVoice

- Modelo disponible localmente:
  - `Qwen3-TTS-12Hz-1.7B-CustomVoice`
- Flujo teórico:
  - voces predefinidas del modelo
- Estado en este proyecto:
  - **no se usa como flujo principal**
- Regla importante:
  - **no mezclar `CustomVoice` con `generate_voice_design(...)`**

### 2.3. Base

- Modelo:
  - `Qwen3-TTS-12Hz-1.7B-Base`
- Métodos oficiales usados:
  - `create_voice_clone_prompt(...)`
  - `generate_voice_clone(...)`
- Casos de uso:
  - reutilizar la misma voz entre muchos clips
  - guardar un prompt de clonación reutilizable
- Script del proyecto que lo usa:
  - `wsl/generate_audio_from_prompt.py`

---

## 3. Cuándo usar cada flujo

### 3.1. Usa VoiceDesign cuando

- quieres describir la voz con texto natural
- quieres una prueba rápida
- quieres generar audio directo sin clonado
- quieres mantener presets y seed por job

### 3.2. Usa Base cuando

- ya tienes una voz de referencia
- quieres consistencia entre muchos clips
- quieres guardar `voice_clone_prompt.json`
- quieres reutilizar una misma voz en varios jobs

### 3.3. No uses CustomVoice cuando

- tu objetivo es diseñar libremente una voz con descripción natural
- quieres mantener un flujo coherente con `VoiceDesign -> Base`

---

## 4. Resumen técnico verificado con el código

### 4.1. `wsl/generar_audio_qwen.py`

Hace esto:

- usa `Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- resuelve snapshots válidos del modelo
- usa `torch.bfloat16` en GPU
- usa `generate_voice_design(...)`
- soporta:
  - presets
  - seed
  - override por `jobs/<job_id>/voice.json`
  - actualización de `jobs/<job_id>/status.json`
  - modo `--test-short`
  - modo texto directo con `--text`
  - modo jobs con `--job-id`

### 4.2. `wsl/design_voice.py`

Hace esto:

- usa `Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- usa `generate_voice_design(...)`
- genera una referencia corta
- guarda:
  - `assets/voices/<voice_name>/reference.wav`
  - `assets/voices/<voice_name>/reference.txt`
  - `assets/voices/<voice_name>/voice.json`

### 4.3. `wsl/generate_audio_from_prompt.py`

Hace esto:

- usa `Qwen3-TTS-12Hz-1.7B-Base`
- detecta métodos reales de la API con introspección
- usa:
  - `create_voice_clone_prompt(...)`
  - `generate_voice_clone(...)`
- soporta:
  - modo directo con `--text`
  - modo jobs con `--job-id`
  - lectura desde `assets/voices/<voice_name>/reference.wav`
  - lectura de metadata en `assets/voices/<voice_name>/voice.json`
  - lectura opcional de `voice_clone_prompt.json`
  - actualización de `status.json` en modo jobs

### 4.4. Wrappers bash

Los wrappers:

- cargan `.env` si existe
- cargan `wsl/voices.env` si existe
- imprimen:
  - proyecto
  - python usado
  - modelo usado
  - device
- validan que el Python exista
- propagan correctamente el código de salida

---

## 5. Variables globales de configuración

Archivo:

```text
wsl/voices.env
```

Contenido real relevante:

```bash
export QWEN_PYTHON="${QWEN_PYTHON:-$HOME/Qwen3-TTS/venv/bin/python}"

# Flujo inmediato: VoiceDesign por descripcion natural.
export QWEN_TTS_MODEL_PATH="/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign"
export QWEN_TTS_VOICE_PRESET="mujer_podcast_seria_35_45"
export QWEN_TTS_SEED="424242"
export QWEN_TTS_LANGUAGE="Spanish"
export QWEN_TTS_DEVICE="auto"
export QWEN_TTS_OVERWRITE="false"
export QWEN_TTS_TEST_SHORT="false"
export QWEN_TTS_TEST_TEXT="Probando sistema de audio con Qwen3 TTS."
export QWEN_TTS_USE_FLASH_ATTN="false"

# Flujo avanzado: disenar referencia con VoiceDesign y clonar con Base.
export QWEN_TTS_BASE_MODEL_PATH="/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base"
export QWEN_TTS_REFERENCE_ROOT="/mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine/assets/voices"
export QWEN_TTS_REFERENCE_TEXT="Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores."
export QWEN_TTS_REFERENCE_LANGUAGE="Spanish"
export QWEN_TTS_REFERENCE_NAME="voz_principal"
export QWEN_TTS_X_VECTOR_ONLY_MODE="false"
```

Regla práctica:

- mismo preset + misma seed = más estabilidad
- preset distinto = otra voz
- seed distinta = variante de la misma voz

---

## 6. Flujo rápido con VoiceDesign

### 6.1. ¿Qué hace?

Este flujo usa:

- modelo `VoiceDesign`
- `generate_voice_design(...)`
- presets de voz
- seed
- overrides por job

### 6.2. Presets disponibles en el código

Los presets definidos actualmente en `wsl/generar_audio_qwen.py` son:

```text
mujer_podcast_seria_35_45
mujer_documental_neutra
hombre_narrador_sobrio
```

### 6.3. Override por job

Archivo:

```text
jobs/<job_id>/voice.json
```

Ejemplo simple:

```json
{
  "voice_preset": "mujer_podcast_seria_35_45",
  "seed": 424242
}
```

Ejemplo avanzado:

```json
{
  "voice_preset": "mujer_documental_neutra",
  "seed": 777777,
  "identity": "Voz femenina madura, sobria y natural.",
  "style": "Ritmo calmado, diccion clara, tono documental.",
  "voice_description": "Evitar tono juvenil. Mantener caracter profesional."
}
```

### 6.4. Cambiar la voz global

Editar:

```text
wsl/voices.env
```

Luego ejecutar:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

### 6.5. Prueba corta

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --test-short
```

Salida esperada:

```text
jobs/test_short.wav
```

### 6.6. Clip directo de prueba

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --text "Esto es una prueba corta de la voz actual." --output outputs/prueba_voice_design.wav
```

### 6.7. Ejecutar todos los jobs

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --overwrite
```

### 6.8. Ejecutar un solo job

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

Campo requerido en:

```text
jobs/<job_id>/script.json
```

Campo obligatorio:

```text
guion_narrado
```

Salida final:

```text
jobs/<job_id>/audio/narration.wav
```

---

## 7. Flujo profesional con VoiceDesign + Base

### 7.1. Paso 1: diseñar la voz de referencia

Script:

```text
wsl/design_voice.py
```

Wrapper:

```text
wsl/run_design_voice.sh
```

Modelo usado:

```text
Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

Método usado:

```python
generate_voice_design(...)
```

Ejemplo:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_design_voice.sh \
  --voice-name voz_finanzas \
  --description "Voz femenina madura, seria, clara, profesional y estable para narracion de podcast de finanzas." \
  --reference-text "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores." \
  --overwrite
```

Archivos generados:

```text
assets/voices/voz_finanzas/reference.wav
assets/voices/voz_finanzas/reference.txt
assets/voices/voz_finanzas/voice.json
```

### 7.2. Paso 2: clonar esa voz con Base

Script:

```text
wsl/generate_audio_from_prompt.py
```

Wrapper:

```text
wsl/run_generate_audio_from_prompt.sh
```

Modelo usado:

```text
Qwen3-TTS-12Hz-1.7B-Base
```

Métodos usados:

```python
create_voice_clone_prompt(...)
generate_voice_clone(...)
```

Ejemplo directo:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_finanzas \
  --text "Este clip debe sonar con la misma voz consistente que la referencia." \
  --save-prompt \
  --output outputs/voz_finanzas_clip.wav
```

Si `--save-prompt` está activo, se guarda:

```text
assets/voices/<voice_name>/voice_clone_prompt.json
```

### 7.3. Paso 3: reutilizar esa voz en muchos clips

Primer job:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh --job-id 000001 --voice-name voz_finanzas --save-prompt --overwrite
```

Segundo job:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh --job-id 000002 --voice-name voz_finanzas --overwrite
```

Tercer job reutilizando el prompt ya serializado:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --job-id 000003 \
  --voice-name voz_finanzas \
  --voice-clone-prompt assets/voices/voz_finanzas/voice_clone_prompt.json \
  --overwrite
```

---

## 8. Cambio de voz por job en el flujo consistente

Archivo:

```text
jobs/<job_id>/voice.json
```

Ejemplo simple:

```json
{
  "voice_name": "voz_finanzas"
}
```

Ejemplo avanzado:

```json
{
  "voice_name": "voz_finanzas",
  "reference_wav": "/mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine/assets/voices/voz_finanzas/reference.wav",
  "reference_text": "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores.",
  "voice_clone_prompt_path": "/mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine/assets/voices/voz_finanzas/voice_clone_prompt.json",
  "x_vector_only_mode": false
}
```

Este archivo es leído por:

```text
wsl/generate_audio_from_prompt.py
```

---

## 9. Estructura final del módulo de audio

```text
assets/
  voices/
    <voice_name>/
      reference.wav
      reference.txt
      voice.json
      voice_clone_prompt.json

jobs/
  <job_id>/
    script.json
    status.json
    voice.json
    audio/
      narration.wav
```

---

## 10. Qué muestran los wrappers

Los tres wrappers:

- `wsl/run_audio.sh`
- `wsl/run_design_voice.sh`
- `wsl/run_generate_audio_from_prompt.sh`

Imprimen:

- proyecto
- python usado
- modelo usado
- device

Y fallan con código distinto de cero si:

- no existe el Python configurado
- falla el script Python llamado

---

## 11. GPU, dtype y rendimiento

Comportamiento real actual:

1. Si `QWEN_TTS_DEVICE=auto`
   - usa GPU si CUDA está disponible
   - usa `torch.bfloat16` en GPU

2. Si `QWEN_TTS_DEVICE=cpu`
   - usa CPU
   - usa `torch.float32`

3. Si `QWEN_TTS_DEVICE=cuda`
   - exige CUDA disponible
   - usa `torch.bfloat16`

Sobre FlashAttention:

- `QWEN_TTS_USE_FLASH_ATTN=false` por defecto
- si lo activas y la instalación es compatible, el código intenta usar:

```python
attn_implementation="flash_attention_2"
```

---

## 12. Cómo diseñar bien una voz

Separar siempre:

### 12.1. Identidad

Quién es la voz:

- mujer madura
- seria
- profesional
- creíble
- medio-grave

### 12.2. Estilo

Cómo habla:

- ritmo medio
- pausado
- claro
- estilo podcast
- natural
- sobrio

Ejemplo bueno para este proyecto:

```text
Voz femenina madura de 35 a 45 años, seria, profesional, natural y creible. Timbre medio-grave, elegante y estable. Ritmo medio, pausado, muy entendible, con diccion clara. Estilo podcast profesional, cercano pero sobrio, sin exageraciones ni tono robotico.
```

---

## 13. Comandos exactos recomendados

### 13.1. Probar el flujo rápido VoiceDesign

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --test-short
```

### 13.2. Generar audio VoiceDesign para un job

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

### 13.3. Diseñar una voz nueva

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_design_voice.sh \
  --voice-name voz_finanzas \
  --description "Voz femenina madura, sobria, profesional, creible y estable." \
  --reference-text "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores." \
  --overwrite
```

### 13.4. Generar el primer clip consistente y guardar el prompt

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_finanzas \
  --job-id 000001 \
  --save-prompt \
  --overwrite
```

### 13.5. Reutilizar la misma voz en otro job

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_finanzas \
  --job-id 000002 \
  --overwrite
```

### 13.6. Reutilizar el prompt serializado

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --job-id 000003 \
  --voice-name voz_finanzas \
  --voice-clone-prompt assets/voices/voz_finanzas/voice_clone_prompt.json \
  --overwrite
```

---

## 14. Compatibilidad con la estructura actual

La documentación está alineada con estos jobs ya existentes:

- `jobs/000001`
- `jobs/000002`
- `jobs/000003`

Archivos esperados por el flujo:

```text
jobs/<job_id>/script.json
jobs/<job_id>/status.json
jobs/<job_id>/audio/
```

En `script.json`, el campo usado por el flujo Base y por el flujo rápido es:

```text
guion_narrado
```

---

## 15. Resumen operativo final

### 15.1. Si quieres describir la voz y generar audio rápido

Usa:

```bash
bash wsl/run_audio.sh
```

### 15.2. Si quieres la misma voz en muchos clips

Haz esto:

1. Diseña la voz:

```bash
bash wsl/run_design_voice.sh ...
```

2. Genera el primer clip y guarda el prompt:

```bash
bash wsl/run_generate_audio_from_prompt.sh --save-prompt ...
```

3. Reutiliza esa misma voz en más jobs:

```bash
bash wsl/run_generate_audio_from_prompt.sh --job-id 000002 ...
```

---

## 16. Siguiente paso recomendado

Primero:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_design_voice.sh \
  --voice-name voz_podcast_mujer \
  --description "Voz femenina madura de 35 a 45 años, seria, profesional, natural, clara y estable. Timbre medio-grave. Ritmo medio, pausado y entendible. Estilo podcast profesional." \
  --reference-text "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores." \
  --overwrite
```

Después:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_podcast_mujer \
  --job-id 000001 \
  --save-prompt \
  --overwrite
```
