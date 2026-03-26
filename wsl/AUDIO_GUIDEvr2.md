# AUDIO GUIDE

## 1. Objetivo del módulo de audio

Este proyecto tiene dos flujos de voz:

1. **Flujo rápido con VoiceDesign**
   - Diseñas la voz con lenguaje natural.
   - Generas audio directamente.
   - Es rápido y práctico.
   - La consistencia es buena, pero no es la máxima posible entre muchos clips largos.

2. **Flujo profesional con VoiceDesign + Base**
   - Diseñas una voz de referencia.
   - Generas `reference.wav`.
   - Creas un `voice_clone_prompt`.
   - Reutilizas esa misma identidad vocal en muchos clips.
   - Este es el flujo correcto si quieres una voz más estable y consistente.

---

## 2. Diferencia entre VoiceDesign, CustomVoice y Base

### VoiceDesign
- Modelo: `Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- Caso correcto: describir la voz con lenguaje natural
- Método: `generate_voice_design(...)`
- Uso en este proyecto:
  - `wsl/generar_audio_qwen.py`
  - `wsl/design_voice.py`

### CustomVoice
- Modelo: `Qwen3-TTS-12Hz-1.7B-CustomVoice`
- Caso correcto: usar voces predefinidas del modelo
- Método: `generate_custom_voice(...)`
- En este proyecto **no se usa** como flujo principal
- Motivo:
  - el objetivo aquí es diseñar una voz propia con lenguaje natural
  - no mezclar `CustomVoice` con `generate_voice_design(...)`

### Base
- Modelo: `Qwen3-TTS-12Hz-1.7B-Base`
- Caso correcto: clonar y reutilizar una voz desde una referencia
- Métodos:
  - `create_voice_clone_prompt(...)`
  - `generate_voice_clone(...)`
- Uso en este proyecto:
  - `wsl/generate_audio_from_prompt.py`

---

## 3. Cuándo usar cada uno

### Usa VoiceDesign cuando
- quieres describir la voz con texto natural
- quieres una prueba rápida
- quieres ajustar el carácter de la voz
- quieres generar audio directo sin pasar por clonación

### Usa Base cuando
- ya tienes una voz de referencia
- necesitas más consistencia entre muchos clips
- quieres reutilizar la misma voz en varios jobs
- quieres guardar y reutilizar `voice_clone_prompt.json`

### No uses CustomVoice cuando
- tu objetivo es diseñar libremente una voz con descripción natural
- quieres una voz tipo marca personal creada por ti

---

## 4. Flujo actual inmediato del proyecto

### Archivo principal
- `wsl/generar_audio_qwen.py`

### Qué hace ahora
- usa `Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- usa `generate_voice_design(...)`
- usa `torch.bfloat16` cuando hay GPU
- mantiene:
  - presets
  - seed
  - override por job con `jobs/<job_id>/voice.json`
  - actualización de `jobs/<job_id>/status.json`

### Override por job soportado

Archivo:

```text
jobs/<job_id>/voice.json

Ejemplo simple:

{
  "voice_preset": "mujer_podcast_seria_35_45",
  "seed": 424242
}

Ejemplo avanzado:

{
  "voice_preset": "mujer_documental_neutra",
  "seed": 777777,
  "identity": "Voz femenina madura, sobria y natural.",
  "style": "Ritmo calmado, dicción clara, tono documental.",
  "voice_description": "Evitar tono juvenil. Mantener carácter profesional."
}
5. Cómo cambiar la voz global

Editar:

wsl/voices.env

Variables principales:

export QWEN_TTS_VOICE_PRESET="mujer_podcast_seria_35_45"
export QWEN_TTS_SEED="424242"
export QWEN_TTS_LANGUAGE="Spanish"
export QWEN_TTS_DEVICE="auto"
export QWEN_TTS_MODEL_PATH="/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign"
Regla práctica
mismo preset + misma seed = más estabilidad
preset distinto = otra voz
seed distinta = variante de la misma voz
6. Cómo hacer una prueba corta

Desde la raíz del proyecto en WSL2:

cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --test-short

Salida esperada:

jobs/test_short.wav

También puedes generar un clip directo:

bash wsl/run_audio.sh --text "Esto es una prueba corta de la voz actual." --output outputs/prueba_voice_design.wav
7. Cómo ejecutar por jobs
Todos los jobs
bash wsl/run_audio.sh --overwrite
Un solo job
bash wsl/run_audio.sh --job-id 000001 --overwrite

Compatibilidad mantenida:

jobs/000001/script.json
jobs/000002/script.json
jobs/000003/script.json

Campo requerido dentro de script.json:

guion_narrado

Salida final:

jobs/<job_id>/audio/narration.wav
8. Flujo oficial para consistencia real

Este es el flujo correcto si quieres la misma voz en muchos clips.

Paso 1: diseñar voz de referencia
Script: wsl/design_voice.py
Wrapper: wsl/run_design_voice.sh
Modelo: Qwen3-TTS-12Hz-1.7B-VoiceDesign
Método: generate_voice_design(...)

Ejemplo:

bash wsl/run_design_voice.sh \
  --voice-name voz_finanzas \
  --description "Voz femenina madura, seria, clara, profesional y estable para narración de podcast de finanzas." \
  --reference-text "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores." \
  --overwrite

Archivos generados:

assets/voices/voz_finanzas/reference.wav
assets/voices/voz_finanzas/reference.txt
assets/voices/voz_finanzas/voice.json
Paso 2: clonar esa voz con Base
Script: wsl/generate_audio_from_prompt.py
Wrapper: wsl/run_generate_audio_from_prompt.sh
Modelo: Qwen3-TTS-12Hz-1.7B-Base
Métodos:
create_voice_clone_prompt(...)
generate_voice_clone(...)

Ejemplo directo:

bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_finanzas \
  --text "Este clip debe sonar con la misma voz consistente que la referencia." \
  --save-prompt \
  --output outputs/voz_finanzas_clip.wav

Si --save-prompt está activo, el prompt se guarda en:

assets/voices/<voice_name>/voice_clone_prompt.json
Paso 3: reutilizar esa voz en muchos clips

Job concreto:

bash wsl/run_generate_audio_from_prompt.sh --job-id 000001 --voice-name voz_finanzas --overwrite

Otro job:

bash wsl/run_generate_audio_from_prompt.sh --job-id 000002 --voice-name voz_finanzas --overwrite

Todos usan:

el mismo reference.wav
el mismo reference.txt
el mismo voice_clone_prompt.json si ya fue generado
9. Cambio de voz por job en el flujo consistente

Puedes crear:

jobs/<job_id>/voice.json

Ejemplo simple:

{
  "voice_name": "voz_finanzas"
}

Ejemplo avanzado:

{
  "voice_name": "voz_finanzas",
  "reference_wav": "/mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine/assets/voices/voz_finanzas/reference.wav",
  "reference_text": "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores.",
  "voice_clone_prompt_path": "/mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine/assets/voices/voz_finanzas/voice_clone_prompt.json",
  "x_vector_only_mode": false
}
10. Estructura final de carpetas
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
11. Comandos exactos recomendados
Prueba rápida del flujo actual VoiceDesign
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --test-short
Generar audio VoiceDesign para un job
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_audio.sh --job-id 000001 --overwrite
Diseñar una voz nueva
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_design_voice.sh \
  --voice-name voz_finanzas \
  --description "Voz femenina madura, sobria, profesional, creíble y estable." \
  --reference-text "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores." \
  --overwrite
Generar el primer clip consistente y guardar el prompt
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_finanzas \
  --job-id 000001 \
  --save-prompt \
  --overwrite
Reutilizar la misma voz en otro job
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_finanzas \
  --job-id 000002 \
  --overwrite
Reutilizar el prompt ya serializado
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_generate_audio_from_prompt.sh \
  --job-id 000003 \
  --voice-name voz_finanzas \
  --voice-clone-prompt assets/voices/voz_finanzas/voice_clone_prompt.json \
  --overwrite
12. Qué muestran los wrappers

Cada wrapper imprime:

proyecto
python usado
modelo usado
device

Y falla con código distinto de cero si:

no existe el python
falla el script Python
13. GPU y dtype

Comportamiento actual:

QWEN_TTS_DEVICE=auto
usa GPU si CUDA está disponible
usa torch.bfloat16 en GPU
QWEN_TTS_DEVICE=cpu
usa CPU y torch.float32
QWEN_TTS_DEVICE=cuda
exige CUDA disponible
14. Qué hacer si no vas a instalar FlashAttention

No pasa nada.

Puedes trabajar sin flash-attn si:

usas torch.bfloat16 en GPU
haces pruebas cortas primero
usas VoiceDesign para diseñar
usas Base para reutilizar la voz

Recomendación práctica:

primero haz funcionar el flujo
luego optimizas
15. Cómo diseñar bien una voz

Una buena voz se diseña separando:

Identidad

Quién es la voz:

mujer madura
seria
profesional
creíble
medio-grave
Estilo

Cómo habla:

ritmo medio
pausado
claro
estilo podcast
natural
sobrio

Ejemplo bueno para este proyecto:

Voz femenina madura de 35 a 45 años, seria, profesional, natural y creíble. Timbre medio-grave, elegante y estable. Ritmo medio, pausado, muy entendible, con dicción clara. Estilo podcast profesional, cercano pero sobrio, sin exageraciones ni tono robótico.
16. Resumen operativo final
Si quieres describir la voz y generar audio rápido

Usa:

bash wsl/run_audio.sh
Si quieres la misma voz en muchos clips

Haz esto:

Diseña la voz
bash wsl/run_design_voice.sh ...
Genera el primer clip y guarda el prompt
bash wsl/run_generate_audio_from_prompt.sh --save-prompt ...
Reutiliza esa misma voz en más jobs
bash wsl/run_generate_audio_from_prompt.sh --job-id 000002 ...
17. Recomendación práctica para este proyecto

Tu estructura ya está lista para trabajar así:

wsl/design_voice.py
wsl/generate_audio_from_prompt.py
wsl/run_design_voice.sh
wsl/run_generate_audio_from_prompt.sh

Entonces el camino correcto ahora es:

Diseña una voz maestra, por ejemplo:
voz_finanzas
voz_podcast_mujer
voz_documental_seria
Escucha reference.wav
Cuando te guste, úsala en generate_audio_from_prompt.py
Reutiliza esa voz en todos tus jobs
18. Siguiente paso recomendado

Haz primero esto:

cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_design_voice.sh \
  --voice-name voz_podcast_mujer \
  --description "Voz femenina madura de 35 a 45 años, seria, profesional, natural, clara y estable. Timbre medio-grave. Ritmo medio, pausado y entendible. Estilo podcast profesional." \
  --reference-text "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores." \
  --overwrite

Y luego:

bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name voz_podcast_mujer \
  --job-id 000001 \
  --save-prompt \
  --overwrite