Estado funcional verificado — Qwen3-TTS GPU en WSL2
1. Entorno que sí funciona
Sistema
Windows + WSL2
Ubuntu 24.04 LTS
Kernel: 5.15.167.4-microsoft-standard-WSL2
Hardware
GPU: NVIDIA GeForce RTX 4070
RAM: ~23 GiB
Disco raíz WSL (/) con espacio suficiente
Entorno Python válido
Conda env: qwen_gpu
Python: 3.12
2. Stack que quedó funcionando
PyTorch
pytorch==2.5.1
torchvision==0.20.1
torchaudio==2.5.1
pytorch-cuda=12.4
Ajuste crítico que arregló el error

Se tuvo que bajar:

mkl -> 2023.2.0

Porque con MKL más nuevo aparecía:

ImportError: ... libtorch_cpu.so: undefined symbol: iJIT_NotifyEvent
3. Verificaciones reales que salieron bien
Import de PyTorch con CUDA
python -c "import torch; print('cuda', torch.cuda.is_available()); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Ninguna')"

Salida válida:

cuda True
gpu NVIDIA GeForce RTX 4070
Operación real en GPU
python -c "import torch; x=torch.randn(1024,1024,device='cuda'); y=x@x.T; print('OK GPU', y.shape, y.device)"

Salida válida:

OK GPU torch.Size([1024, 1024]) cuda:0
Imports válidos
python -c "import torchaudio; print('torchaudio', torchaudio.__version__)"
python -c "import torchvision; print('torchvision', torchvision.__version__)"
python -c "import qwen_tts; print('qwen_tts OK')"

Salidas válidas:

torchaudio 2.5.1
torchvision 0.20.1
qwen_tts OK
4. Entorno correcto que hay que usar siempre

El Python bueno ahora es:

/home/victory/miniconda3/envs/qwen_gpu/bin/python
Muy importante

El entorno viejo tipo:

/home/victory/Qwen3-TTS/venv/bin/python

ya no es el que debes usar.

5. Qué hay que dejar configurado en el proyecto

En wsl/voices.env debe quedar algo así:

export QWEN_PYTHON="/home/victory/miniconda3/envs/qwen_gpu/bin/python"

Y cualquier script que apunte al venv viejo hay que cambiarlo a esa ruta.

6. Comandos correctos para entrar al entorno
conda activate qwen_gpu
cd ~/Qwen3-TTS
7. Qué no tocar otra vez

No volver a mezclar:

base de conda con el entorno de Qwen
venv viejos borrados
PyTorch CPU con torchaudio CUDA
versiones aleatorias de torch, torchvision, torchaudio
reinstalaciones de CUDA al azar
variables raras de LD_LIBRARY_PATH sin necesidad
8. Warning que no bloquea

Este warning apareció pero no impidió que funcione:

Warning: flash-attn is not installed. Will only run the manual PyTorch version.

Eso significa:

el entorno funciona
solo falta optimizar velocidad más adelante

También apareció esto:

onnxruntime ... Failed to open file: "/sys/class/drm/card0/device/vendor"

Pero tampoco bloqueó el import ni el funcionamiento base.

9. Orden correcto a partir de ahora
Siempre hacer esto primero
conda activate qwen_gpu
cd ~/Qwen3-TTS
Verificación rápida
python -c "import torch; print(torch.cuda.is_available())"

Debe dar:

True
10. Foto final del estado bueno
FUNCIONA
WSL2
Python 3.12
conda env qwen_gpu
PyTorch 2.5.1 + CUDA 12.4
torchaudio 2.5.1
torchvision 0.20.1
qwen_tts importando
GPU RTX 4070 operativa
NO optimizado todavía
flash-attn no instalado aún
11. Comando base de rescate futuro

Si alguna vez dudas si estás en el entorno bueno:

conda activate qwen_gpu
which python
python -V
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"

Esperado:

Python del env qwen_gpu
Python 3.12
torch 2.5.1
CUDA True
12. Próximo paso lógico

No reinstalar nada.
El siguiente paso es probar generación real de audio con este entorno exacto y luego optimizar rendimiento