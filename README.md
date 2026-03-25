
# NeuroContent Engine 🚀

Pipeline automatizado para generación de contenido corto (TikTok, Reels, Shorts) usando:

- LLM (Ollama)
- TTS (Qwen3-TTS en WSL2)
- Subtítulos (WhisperX)

---

## 🧠 Flujo del sistema

ideas.csv  
→ LLM (Ollama)  
→ scripts.json  
→ Qwen3-TTS (audio)  
→ WhisperX (subtítulos)  

---

## 🪟 Ejecución en Windows

Generar guiones desde el CSV:

```bash
python main.py
```

---

## 🐧 Ejecución en WSL2

Ir al proyecto:

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
```

Dar permisos (solo la primera vez):

```bash
chmod +x wsl/run_wsl_pipeline.sh
```

Ejecutar pipeline completo:

```bash
bash wsl/run_wsl_pipeline.sh
```

---

## 🔊 Generación de audio (Qwen3-TTS)

El script usa automáticamente el entorno:

~/Qwen3-TTS/venv/bin/python

Modelos disponibles:

```bash
ls -1 /mnt/d/AI_Models/huggingface/hub | grep "models--Qwen--Qwen3-TTS"
```

---

## 📂 Rutas importantes

- Proyecto: `/mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine`
- Outputs:
  - `outputs/scripts.json`
  - `outputs/audio/*.wav`
  - `outputs/subtitles/*.srt`

---

## ⚙️ Pipeline completo

1. Generar guiones
	```bash
	python main.py
	```
2. Generar audio + subtítulos (WSL2)
	```bash
	cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
	bash wsl/run_wsl_pipeline.sh
	```

---

## ⚠️ Notas importantes

- No usar sudo para ejecutar scripts Python
- Qwen3-TTS usa su propio entorno virtual
- WhisperX debe estar instalado en WSL2
- Los modelos deben estar descargados previamente

---

## 🚀 Estado del proyecto

✔ Generación de guiones
✔ Generación de audio
✔ Generación de subtítulos
⬜ Render final de video (siguiente paso)

---

## 🔥 Próximo paso

Integrar FFmpeg para generar videos automáticos:

audio + imágenes + subtítulos → video final

---

## 💡 Te lo digo claro

Esto que tienes ahora mismo ya no es un script…

👉 es una **fábrica automatizada de contenido**

Y el README ya refleja eso correctamente:

- claro
- ejecutable
- escalable
- entendible por cualquiera

---

Si quieres en el siguiente paso te hago:

👉 `render_video.py` con FFmpeg (automático con imágenes + audio + subtítulos)

y ya cierras el sistema completo
🐧 Ejecución en WSL2

Ir al proyecto:

cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine

Dar permisos (solo la primera vez):

chmod +x wsl/run_wsl_pipeline.sh

Ejecutar pipeline completo:

bash wsl/run_wsl_pipeline.sh
🔊 Generación de audio (Qwen3-TTS)

El script usa automáticamente el entorno:

~/Qwen3-TTS/venv/bin/python

Modelos disponibles:

ls -1 /mnt/d/AI_Models/huggingface/hub | grep "models--Qwen--Qwen3-TTS"
📂 Rutas importantes

Proyecto:

/mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine

Outputs:

outputs/scripts.json
outputs/audio/*.wav
outputs/subtitles/*.srt
⚙️ Pipeline completo
1. Generar guiones
python main.py
2. Generar audio + subtítulos (WSL2)
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
bash wsl/run_wsl_pipeline.sh
⚠️ Notas importantes
No usar sudo para ejecutar scripts Python
Qwen3-TTS usa su propio entorno virtual
WhisperX debe estar instalado en WSL2
Los modelos deben estar descargados previamente
🚀 Estado del proyecto

✔ Generación de guiones
✔ Generación de audio
✔ Generación de subtítulos
⬜ Render final de video (siguiente paso)

🔥 Próximo paso

Integrar FFmpeg para generar videos automáticos:

audio + imágenes + subtítulos → video final

---

# 💡 Te lo digo claro

Esto que tienes ahora mismo ya no es un script…

👉 es una **fábrica automatizada de contenido**

Y el README ya refleja eso correctamente:

- claro
- ejecutable
- escalable
- entendible por cualquiera

---

Si quieres en el siguiente paso te hago:

👉 `render_video.py` con FFmpeg (automático con imágenes + audio + subtítulos)

y ya cierras el sistema completo 