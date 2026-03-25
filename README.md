
# NeuroContent Engine 🚀

> **Pipeline automatizado para generación de contenido corto (TikTok, Reels, Shorts)**

| Módulo         | Tecnología         | Plataforma |
| -------------- | ----------------- | ---------- |
| LLM            | Ollama            | Windows    |
| TTS            | Qwen3-TTS         | WSL2       |
| Subtítulos     | WhisperX          | WSL2       |

---

## 1. 🧠 Flujo del sistema

```mermaid
graph TD;
	 A[ideas.csv] --> B[LLM (Ollama)];
	 B --> C[scripts.json];
	 C --> D[Qwen3-TTS (audio)];
	 D --> E[WhisperX (subtítulos)];
```

---

## 2. 📋 Pasos de Ejecución

### 2.1. En Windows

1. Generar guiones desde el CSV:
	```bash
	python main.py
	```

### 2.2. En WSL2

1. Ir al proyecto:
	```bash
	cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine
	```
2. Dar permisos (solo la primera vez):
	```bash
	chmod +x wsl/run_wsl_pipeline.sh
	```
3. Ejecutar pipeline completo:
	```bash
	bash wsl/run_wsl_pipeline.sh
	```

---

## 3. 🔊 Generación de audio (Qwen3-TTS)

- El script usa automáticamente el entorno: `~/Qwen3-TTS/venv/bin/python`
- Modelos disponibles:
  ```bash
  ls -1 /mnt/d/AI_Models/huggingface/hub | grep "models--Qwen--Qwen3-TTS"
  ```

---

## 4. 📂 Rutas importantes

| Recurso   | Ruta                                                        |
| --------- | ----------------------------------------------------------- |
| Proyecto  | /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine |
| Guiones   | outputs/scripts.json                                        |
| Audios    | outputs/audio/*.wav                                         |
| Subtítulos| outputs/subtitles/*.srt                                     |

---

## 5. ⚙️ Pipeline completo (resumen)

| Paso | Acción                                      | Plataforma |
| ---- | -------------------------------------------- | ---------- |
| 1    | python main.py                              | Windows    |
| 2    | cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/neurocontent-engine <br> bash wsl/run_wsl_pipeline.sh | WSL2 |

---

## 6. ⚠️ Notas importantes

| Nota                                                      |
| --------------------------------------------------------- |
| No usar sudo para ejecutar scripts Python                  |
| Qwen3-TTS usa su propio entorno virtual                   |
| WhisperX debe estar instalado en WSL2                     |
| Los modelos deben estar descargados previamente           |

---

## 7. 🚀 Estado del proyecto

| Tarea                        | Estado     |
| ---------------------------- | ---------- |
| Generación de guiones        | ✔️         |
| Generación de audio          | ✔️         |
| Generación de subtítulos     | ✔️         |
| Render final de video        | ⬜ (pendiente) |

---

## 8. 🔥 Próximo paso

Integrar FFmpeg para generar videos automáticos:

```
audio + imágenes + subtítulos → video final
```

---

## 9. 💡 Reflexión final

Esto que tienes ahora mismo ya no es un script…

👉 es una **fábrica automatizada de contenido**

El README ya refleja eso correctamente:

- Claro
- Ejecutable
- Escalable
- Entendible por cualquiera

---

## 10. ¿Qué sigue?

¿Quieres el siguiente paso?

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