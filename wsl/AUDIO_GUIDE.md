📄 DOCUMENTACIÓN CORREGIDA — MÓDULO DE AUDIO
# 🎙️ Módulo de audio

Este módulo genera la narración de cada job en:

`jobs/<job_id>/audio/narration.wav`

---

# 🧠 Cómo funciona la voz (IMPORTANTE)

El sistema de voz **NO usa voces predefinidas reales**.

En lugar de eso:

👉 La voz se genera mediante **lenguaje natural (prompting)**

Ejemplo interno:

- "Voz femenina madura, seria, profesional..."
- "Ritmo medio, claro, estilo podcast..."

---

## 🔥 Qué significa esto

- No existen voces fijas como en ElevenLabs
- Cada audio es generado dinámicamente
- Puede haber pequeñas variaciones

---

## ✅ Cómo solucionamos esto

Este sistema usa:

- `VOICE_PRESETS` → define la voz
- `seed` → estabiliza la generación
- `identity + style` → fija personalidad vocal

👉 Resultado: voces consistentes (no perfectas, pero estables)

---

# 📂 Archivos principales

- `wsl/run_audio.sh` → ejecuta el módulo de audio
- `wsl/generar_audio_qwen.py` → genera la voz
- `wsl/voices.env` → configuración global de voz

---

# 🎯 Formas de cambiar la voz

## 1️⃣ Cambiar la voz GLOBAL (recomendado)

Esto cambia la voz de TODO el sistema.

---

### Paso 1

Editar:


wsl/voices.env


---

### Paso 2

Ejemplo:

```bash
export QWEN_TTS_VOICE_PRESET="mujer_documental_neutra"
export QWEN_TTS_SEED=424242
Paso 3

Ejecutar:

bash wsl/run_audio.sh
2️⃣ Cambiar la voz solo para UN JOB

Esto permite que un job tenga una voz distinta.

Paso 1

Crear archivo:

jobs/<job_id>/voice.json

Ejemplo:

jobs/000001/voice.json
Paso 2

Contenido (JSON válido):

{
  "voice_preset": "mujer_podcast_seria_35_45",
  "seed": 424242
}
Paso 3

Ejecutar:

bash wsl/run_audio.sh
⚠️ MUY IMPORTANTE

❌ NO usar:

jobs/voice.json

✔ Correcto:

jobs/000001/voice.json
jobs/000002/voice.json
🎛️ Parámetros de voz
voice_preset

Nombre de la voz definida en el sistema.

Ejemplo:

"voice_preset": "mujer_podcast_seria_35_45"
seed

Número que estabiliza la voz.

Ejemplo:

"seed": 424242
📌 Reglas prácticas
Situación	Acción
Quiero misma voz	misma seed
Quiero variación leve	cambiar seed
Quiero voz distinta	cambiar preset
🎙️ Presets disponibles
mujer_podcast_seria_35_45
Mujer 35–45
Seria
Estilo podcast
Clara y natural
mujer_documental_neutra
Voz más neutra
Estilo documental
Calmado
hombre_narrador_sobrio
Voz masculina
Narrador clásico
Profesional
🧪 Uso avanzado (opcional)

Puedes sobrescribir completamente la voz:

{
  "identity": "Voz femenina madura, elegante, profesional",
  "style": "Ritmo lento, tono serio, estilo documental premium",
  "seed": 123456
}
🧠 Buenas prácticas
✔ Mantener consistencia

NO cambiar:

preset
seed
identity
style

👉 si quieres misma voz en todos los videos

✔ Probar voces sin romper el sistema

Usar:

jobs/<job_id>/voice.json
✔ Guardar combinaciones buenas

Si encuentras una voz buena:

guarda preset
guarda seed
⚠️ Limitaciones

Este sistema:

✔ genera voces naturales
✔ permite controlarlas
✔ permite reutilizarlas

PERO:

❌ no es clon de voz perfecto
❌ puede haber pequeñas variaciones

🚀 Flujo recomendado
Caso normal
bash wsl/run_audio.sh
Cambiar voz global
nano wsl/voices.env
bash wsl/run_audio.sh
Cambiar voz por job
nano jobs/000001/voice.json
bash wsl/run_audio.sh
🧾 Resumen rápido
Acción	Archivo
Cambiar voz global	wsl/voices.env
Cambiar voz por job	jobs/<id>/voice.json
Crear voz nueva	generar_audio_qwen.py
🎯 Recomendación final

Para contenido tipo:

YouTube
podcast
storytelling

Usar:

mujer_podcast_seria_35_45
seed fija