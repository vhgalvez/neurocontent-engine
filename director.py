# director.py

import json
from typing import Any, Dict

import requests

from config import MODEL, OLLAMA_URL, OPTIONS, REQUEST_TIMEOUT_SECONDS
from prompts import SYSTEM_SCRIPT, USER_SCRIPT


class OllamaError(Exception):
    """Error controlado al interactuar con Ollama."""


def _strip_code_fences(text: str) -> str:
    """
    Limpia bloques markdown si el modelo devuelve ```json ... ```
    aunque se le haya pedido JSON puro.
    """
    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    Intenta parsear el texto completo como JSON.
    Si falla, busca el primer { y el último } para rescatar el objeto.
    """
    cleaned = _strip_code_fences(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    raise OllamaError(f"No se encontró JSON válido en la respuesta:\n{cleaned}")


def _normalize_brief(brief: Dict[str, Any]) -> Dict[str, str]:
    """
    Asegura que todas las claves usadas por el prompt existan, aunque vengan vacías.
    """
    expected_keys = {
        "id",
        "estado",
        "nicho",
        "subnicho",
        "idioma",
        "plataforma",
        "formato",
        "duracion_seg",
        "objetivo",
        "avatar",
        "audiencia",
        "dolor_principal",
        "deseo_principal",
        "miedo_principal",
        "angulo",
        "tipo_hook",
        "historia_base",
        "idea_central",
        "tesis",
        "enemigo",
        "error_comun",
        "transformacion_prometida",
        "tono",
        "emocion_principal",
        "emocion_secundaria",
        "nivel_intensidad",
        "cta_tipo",
        "cta_texto",
        "prohibido",
        "keywords",
        "referencias",
        "notas_direccion",
        "ritmo",
        "estilo_narracion",
        "tipo_cierre",
        "nivel_agresividad_copy",
        "objetivo_retencion",
    }

    normalized: Dict[str, str] = {}
    for key in expected_keys:
        value = brief.get(key, "")
        normalized[key] = str(value).strip() if value is not None else ""

    return normalized


def mejorar_texto_para_voz(texto: str) -> str:
    """
    Limpieza suave para TTS sin alterar el contenido principal.
    """
    if not texto:
        return ""

    texto = " ".join(texto.split()).strip()

    reemplazos = {
        "¡": "",
        "!": ".",
        "¿": "",
        "?": ".",
        ":": ".",
        ";": ".",
    }

    for viejo, nuevo in reemplazos.items():
        texto = texto.replace(viejo, nuevo)

    while ".." in texto:
        texto = texto.replace("..", ".")

    return texto.strip(" .")


def construir_narracion(script_data: Dict[str, Any]) -> str:
    """
    Convierte el JSON estructurado en un texto continuo pensado para TTS.
    """
    partes = []

    for key in ("hook", "problema", "explicacion"):
        value = mejorar_texto_para_voz(str(script_data.get(key, "")))
        if value:
            partes.append(value)

    for paso in script_data.get("solucion", []):
        paso_limpio = mejorar_texto_para_voz(str(paso))
        if paso_limpio:
            partes.append(paso_limpio)

    for key in ("cierre", "cta"):
        value = mejorar_texto_para_voz(str(script_data.get(key, "")))
        if value:
            partes.append(value)

    narracion = ". ".join(partes).strip()
    if narracion and not narracion.endswith("."):
        narracion += "."

    return narracion


def build_prompt(brief: Dict[str, Any]) -> str:
    """Construye el prompt final desde el brief."""
    normalized = _normalize_brief(brief)
    return USER_SCRIPT.format(**normalized)


def _validate_script_data(script_data: Dict[str, Any]) -> None:
    required_keys = {"hook", "problema", "explicacion", "solucion", "cierre", "cta"}
    missing = required_keys - set(script_data.keys())
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise OllamaError(
            f"El JSON devuelto no tiene todas las claves requeridas. "
            f"Faltan: {missing_text}\n"
            f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
        )

    if not isinstance(script_data["solucion"], list) or len(script_data["solucion"]) != 3:
        raise OllamaError(
            "La clave 'solucion' debe ser una lista de exactamente 3 pasos.\n"
            f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
        )

    for key in ("hook", "problema", "explicacion", "cierre", "cta"):
        if not isinstance(script_data[key], str) or not script_data[key].strip():
            raise OllamaError(
                f"La clave '{key}' debe ser texto no vacío.\n"
                f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
            )

    for index, paso in enumerate(script_data["solucion"], start=1):
        if not isinstance(paso, str) or not paso.strip():
            raise OllamaError(
                f"El paso {index} de 'solucion' está vacío o no es texto.\n"
                f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
            )


def generate_script(brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Envía el brief a Ollama y devuelve el guion estructurado.
    """
    prompt = build_prompt(brief)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_SCRIPT.strip()},
            {"role": "user", "content": prompt.strip()},
        ],
        "stream": False,
        "format": "json",
        "options": OPTIONS,
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise OllamaError(f"No se pudo conectar con Ollama: {exc}") from exc

    if response.status_code != 200:
        raise OllamaError(f"Error Ollama ({response.status_code}):\n{response.text}")

    try:
        data = response.json()
    except ValueError as exc:
        raise OllamaError(f"Ollama devolvió una respuesta no JSON:\n{response.text}") from exc

    message = data.get("message")
    if not isinstance(message, dict):
        raise OllamaError(
            "Respuesta inesperada de Ollama: falta 'message'.\n"
            f"{json.dumps(data, ensure_ascii=False, indent=2)}"
        )

    content = message.get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise OllamaError(
            "La respuesta de Ollama no contiene texto utilizable.\n"
            f"{json.dumps(data, ensure_ascii=False, indent=2)}"
        )

    script_data = _extract_json_from_text(content)
    _validate_script_data(script_data)

    # Este campo no lo genera el LLM: lo construimos nosotros para TTS.
    script_data["narracion"] = construir_narracion(script_data)

    return script_data