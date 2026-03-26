# AUDIO GUIDE

## 1. Diferencia entre VoiceDesign, CustomVoice y Base

### VoiceDesign
- Modelo: `Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- Caso correcto: describir la voz con lenguaje natural.
- Metodo oficial: `generate_voice_design(...)`
- Uso en este proyecto:
  - `wsl/generar_audio_qwen.py`
  - `wsl/design_voice.py`

### CustomVoice
- No se usa en este proyecto.
- Motivo:
  - no se debe mezclar `CustomVoice` con `generate_voice_design(...)`
  - ese flujo era el incorrecto que se queria eliminar

### Base
- Modelo: `Qwen3-TTS-12Hz-1.7B-Base`
- Caso correcto: reutilizar la misma identidad vocal entre muchos clips.
- Metodos oficiales:
  - `create_voice_clone_prompt(...)`
  - `generate_voice_clone(...)`
- Uso en este proyecto:
  - `wsl/generate_audio_from_prompt.py`

## 2. Cuando usar cada uno

### Usa VoiceDesign cuando
- quieres describir una voz con texto natural
- quieres una prueba rapida
- quieres generar jobs directamente con presets y seed
- aceptas consistencia razonable, pero no clonacion real entre muchos clips

### Usa Base cuando
- necesitas la misma voz entre muchos clips
- ya tienes un `reference.wav`
- quieres construir un `voice_clone_prompt` reutilizable

## 3. Flujo actual inmediato del proyecto

### Archivo principal
- `wsl/generar_audio_qwen.py`

### Que hace ahora
- usa `Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- usa `generate_voice_design(...)`
- usa `torch.bfloat16` cuando hay GPU
- mantiene:
  - presets
  - seed
  - override por job con `jobs/<job_id>/voice.json`
  - actualizacion de `jobs/<job_id>/status.json`

### Override por job soportado
- archivo: `jobs/<job_id>/voice.json`

Ejemplo:

```json
{
  "voice_preset": "mujer_podcast_seria_35_45",
  "seed": 424242
}
```

Ejemplo con override completo:

```json
{
  "voice_preset": "mujer_documental_neutra",
  "seed": 777777,
  "identity": "Voz femenina madura, sobria y natural.",
  "style": "Ritmo calmado, diccion clara, tono documental.",
  "voice_description": "Evitar tono juvenil. Mantener caracter profesional."
}
```

## 4. Como cambiar la voz global

Editar:

`wsl/voices.env`

Variables relevantes:

```bash
export QWEN_TTS_VOICE_PRESET="mujer_podcast_seria_35_45"
export QWEN_TTS_SEED="424242"
export QWEN_TTS_LANGUAGE="Spanish"
export QWEN_TTS_DEVICE="auto"
export QWEN_TTS_MODEL_PATH="/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign"
```

## 5. Como hacer una prueba corta

Desde la raiz del proyecto en WSL2:

```bash
bash wsl/run_audio.sh --test-short
```

Salida:

```text
jobs/test_short.wav
```

Tambien puedes generar un clip directo:

```bash
bash wsl/run_audio.sh --text "Esto es una prueba corta de la voz actual." --output outputs/prueba_voice_design.wav
```

## 6. Como ejecutar por jobs

Todos los jobs:

```bash
bash wsl/run_audio.sh --overwrite
```

Un solo job:

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

Compatibilidad mantenida:
- `jobs/000001/script.json`
- `jobs/000002/script.json`
- `jobs/000003/script.json`

Campo requerido en `script.json`:
- `guion_narrado`

Salida:

```text
jobs/<job_id>/audio/narration.wav
```

## 7. Flujo oficial para consistencia real

### Paso 1: disenar voz de referencia
- Script: `wsl/design_voice.py`
- Wrapper: `wsl/run_design_voice.sh`
- Modelo: `Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- Metodo: `generate_voice_design(...)`

Ejemplo:

```bash
bash wsl/run_design_voice.sh \
  --voice-name voz_finanzas \
  --description "Voz femenina madura, seria, clara, profesional y estable para narracion de podcast de finanzas." \
  --reference-text "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores." \
  --overwrite
```

Archivos generados:
- `assets/voices/voz_finanzas/reference.wav`
- `assets/voices/voz_finanzas/reference.txt`
- `assets/voices/voz_finanzas/metadata.json`

### Paso 2: clonar esa voz con Base
- Script: `wsl/generate_audio_from_prompt.py`
- Wrapper: `wsl/run_generate_audio_from_prompt.sh`
- Modelo: `Qwen3-TTS-12Hz-1.7B-Base`
- Metodos:
  - `create_voice_clone_prompt(...)`
  - `generate_voice_clone(...)`

Ejemplo directo:

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_finanzas \
  --text "Este clip debe sonar con la misma voz consistente que la referencia." \
  --save-prompt \
  --output outputs/voz_finanzas_clip.wav
```

Si `--save-prompt` esta activo, el prompt se guarda en:

```text
assets/voices/<voice_name>/voice_clone_prompt.json
```

### Paso 3: reutilizar esa voz en muchos clips

Job concreto:

```bash
bash wsl/run_generate_audio_from_prompt.sh --job-id 000001 --voice-name voz_finanzas --overwrite
```

Otro job:

```bash
bash wsl/run_generate_audio_from_prompt.sh --job-id 000002 --voice-name voz_finanzas --overwrite
```

Todos con la misma referencia:
- mismo `reference.wav`
- mismo `reference.txt`
- mismo `voice_clone_prompt.json` si ya lo generaste

## 8. Cambio de voz por job para el flujo consistente

Puedes crear:

`jobs/<job_id>/voice.json`

Ejemplo:

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

## 9. Comandos exactos recomendados

### Prueba rapida del flujo actual VoiceDesign

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --test-short
```

### Generar audio VoiceDesign para un job

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

### Disenar una voz nueva

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_design_voice.sh \
  --voice-name voz_finanzas \
  --description "Voz femenina madura, sobria, profesional, creible y estable." \
  --reference-text "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores." \
  --overwrite
```

### Generar el primer clip consistente y guardar el prompt

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_finanzas \
  --job-id 000001 \
  --save-prompt \
  --overwrite
```

### Reutilizar la misma voz en otro job

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_finanzas \
  --job-id 000002 \
  --overwrite
```

### Reutilizar el prompt ya serializado

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --job-id 000003 \
  --voice-name voz_finanzas \
  --voice-clone-prompt assets/voices/voz_finanzas/voice_clone_prompt.json \
  --overwrite
```

## 10. Que muestran los wrappers

Cada wrapper imprime:
- proyecto
- python usado
- modelo usado
- device

Y falla con codigo distinto de cero si:
- no existe el python
- falla el script Python

## 11. GPU y dtype

Comportamiento actual:
- `QWEN_TTS_DEVICE=auto`
  - usa GPU si CUDA esta disponible
  - usa `torch.bfloat16` en GPU
- `QWEN_TTS_DEVICE=cpu`
  - usa CPU y `torch.float32`
- `QWEN_TTS_DEVICE=cuda`
  - exige CUDA disponible

## 12. Resumen operativo

### Si quieres describir la voz y generar audio rapido
- usa `bash wsl/run_audio.sh`

### Si quieres la misma voz en muchos clips
1. `bash wsl/run_design_voice.sh ...`
2. `bash wsl/run_generate_audio_from_prompt.sh --save-prompt ...`
3. reutiliza `voice_name` o `voice_clone_prompt.json` en cada job
