# director.py

import csv
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List

import requests

from config import (
    BASE_DIR,
    INDEX_FILE,
    JOB_ID_WIDTH,
    JOBS_DIR,
    MODEL,
    OLLAMA_MAX_RETRIES,
    OLLAMA_URL,
    OPTIONS,
    REQUEST_TIMEOUT_SECONDS,
)
from prompts import (
    REWRITE_SYSTEM_SCRIPT,
    REWRITE_USER_SCRIPT,
    SYSTEM_SCRIPT,
    USER_SCRIPT,
)

SCRIPT_REQUIRED_KEYS = {
    "hook",
    "problema",
    "explicacion",
    "solucion",
    "cierre",
    "cta",
    "guion_narrado",
}

STATUS_DEFAULTS = {
    "brief_created": False,
    "script_generated": False,
    "audio_generated": False,
    "subtitles_generated": False,
    "visual_manifest_generated": False,
    "export_ready": False,
    "last_step": "created",
    "updated_at": "",
}

INDEX_COLUMNS = [
    "job_id",
    "source_id",
    "estado_csv",
    "idea_central",
    "platform",
    "language",
    "brief_created",
    "script_generated",
    "audio_generated",
    "subtitles_generated",
    "visual_manifest_generated",
    "export_ready",
    "last_step",
    "updated_at",
]

TRANSITION_MARKERS = {
    "porque",
    "pero",
    "entonces",
    "por eso",
    "asi que",
    "ahora",
    "si no",
    "mientras",
    "aunque",
    "primero",
    "despues",
    "al final",
    "y ahi",
    "por eso mismo",
    "de hecho",
}


class OllamaError(Exception):
    """Error controlado al interactuar con Ollama."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def pad_job_id(value: Any) -> str:
    raw = str(value).strip()
    if not raw:
        raise ValueError("El brief no contiene un id utilizable.")
    return raw.zfill(JOB_ID_WIDTH)


def ensure_job_dir(job_id: str) -> Path:
    job_dir = JOBS_DIR / job_id
    (job_dir / "audio").mkdir(parents=True, exist_ok=True)
    (job_dir / "subtitles").mkdir(parents=True, exist_ok=True)
    return job_dir


def safe_write_json(path: Path, data: Dict[str, Any] | List[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def safe_read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_job_paths(job_id: str) -> Dict[str, Path]:
    job_dir = ensure_job_dir(job_id)
    return {
        "job_dir": job_dir,
        "brief": job_dir / "brief.json",
        "script": job_dir / "script.json",
        "status": job_dir / "status.json",
        "manifest": job_dir / "visual_manifest.json",
        "audio": job_dir / "audio" / "narration.wav",
        "subtitles": job_dir / "subtitles" / "narration.srt",
    }


def load_status(status_path: Path) -> Dict[str, Any]:
    current = safe_read_json(status_path, default={}) or {}
    status = {**STATUS_DEFAULTS, **current}
    status["export_ready"] = bool(
        status["brief_created"]
        and status["script_generated"]
        and status["audio_generated"]
        and status["subtitles_generated"]
        and status["visual_manifest_generated"]
    )
    return status


def update_status(
    status_path: Path,
    *,
    last_step: str | None = None,
    **changes: Any,
) -> Dict[str, Any]:
    status = load_status(status_path)
    status.update(changes)
    if last_step:
        status["last_step"] = last_step
    status["updated_at"] = utc_now_iso()
    status["export_ready"] = bool(
        status["brief_created"]
        and status["script_generated"]
        and status["audio_generated"]
        and status["subtitles_generated"]
        and status["visual_manifest_generated"]
    )
    safe_write_json(status_path, status)
    return status


def sync_status_with_files(paths: Dict[str, Path]) -> Dict[str, Any]:
    return update_status(
        paths["status"],
        brief_created=paths["brief"].exists(),
        script_generated=paths["script"].exists(),
        audio_generated=paths["audio"].exists(),
        subtitles_generated=paths["subtitles"].exists(),
        visual_manifest_generated=paths["manifest"].exists(),
    )


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned


def _extract_json_from_text(text: str) -> Dict[str, Any]:
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

    raise OllamaError(f"No se encontro JSON valido en la respuesta:\n{cleaned}")


def _normalize_brief(brief: Dict[str, Any]) -> Dict[str, str]:
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


def _clean_compare_text(text: str) -> str:
    normalized = " ".join(str(text).lower().split()).strip()
    normalized = re.sub(r"[^\wáéíóúüñ\s]", "", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def _remove_exact_cta(text: str, cta: str) -> str:
    text_norm = " ".join(str(text).split()).strip()
    cta_norm = " ".join(str(cta).split()).strip()

    if not cta_norm:
        return text_norm

    if text_norm.endswith(cta_norm):
        return text_norm[: -len(cta_norm)].strip(" .,!?:;")

    return text_norm


def build_prompt(brief: Dict[str, Any]) -> str:
    normalized = _normalize_brief(brief)
    return USER_SCRIPT.format(**normalized)


def build_naive_narration(script_data: Dict[str, Any], include_cta: bool = False) -> str:
    pieces = [
        script_data.get("hook", ""),
        script_data.get("problema", ""),
        script_data.get("explicacion", ""),
        *script_data.get("solucion", []),
        script_data.get("cierre", ""),
    ]

    if include_cta:
        pieces.append(script_data.get("cta", ""))

    return " ".join(
        " ".join(str(piece).split()) for piece in pieces if str(piece).strip()
    ).strip()


def _count_exact_block_reuse(script_data: Dict[str, Any], narration: str) -> int:
    narration_clean = _clean_compare_text(narration)

    blocks = [
        script_data.get("hook", ""),
        script_data.get("problema", ""),
        script_data.get("explicacion", ""),
        *script_data.get("solucion", []),
        script_data.get("cierre", ""),
    ]

    reused = 0
    for block in blocks:
        block_clean = _clean_compare_text(block)
        if block_clean and block_clean in narration_clean:
            reused += 1
    return reused


def _should_try_rewrite(exc: OllamaError) -> bool:
    text = str(exc).lower()
    rewrite_triggers = [
        "concatenacion mecanica",
        "guion_narrado",
        "transiciones naturales",
        "demasiado corto",
        "bloques literales",
    ]
    return any(trigger in text for trigger in rewrite_triggers)


def _ollama_chat_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": OPTIONS,
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        raise OllamaError(f"Error Ollama ({response.status_code}):\n{response.text}")

    try:
        data = response.json()
    except ValueError:
        raise OllamaError(f"Ollama devolvio una respuesta no JSON:\n{response.text}")

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

    return _extract_json_from_text(content)


def rewrite_guion_narrado(brief: Dict[str, Any], script_data: Dict[str, Any]) -> str:
    normalized_brief = _normalize_brief(brief)

    rewrite_prompt = REWRITE_USER_SCRIPT.format(
        idea_central=normalized_brief["idea_central"],
        plataforma=normalized_brief["plataforma"],
        duracion_seg=normalized_brief["duracion_seg"],
        tono=normalized_brief["tono"],
        ritmo=normalized_brief["ritmo"],
        emocion_principal=normalized_brief["emocion_principal"],
        emocion_secundaria=normalized_brief["emocion_secundaria"],
        cta_texto=normalized_brief["cta_texto"],
        script_json=json.dumps(script_data, ensure_ascii=False, indent=2),
    )

    rewrite_data = _ollama_chat_json(
        [
            {"role": "system", "content": REWRITE_SYSTEM_SCRIPT.strip()},
            {"role": "user", "content": rewrite_prompt.strip()},
        ]
    )

    guion_narrado = rewrite_data.get("guion_narrado", "")
    if not isinstance(guion_narrado, str) or not guion_narrado.strip():
        raise OllamaError("La reescritura de guion_narrado devolvio texto vacio.")

    return " ".join(guion_narrado.split()).strip()


def _sentence_chunks(text: str) -> List[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def validate_script_data(script_data: Dict[str, Any]) -> None:
    missing = SCRIPT_REQUIRED_KEYS - set(script_data.keys())
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise OllamaError(
            "El JSON devuelto no tiene todas las claves requeridas. "
            f"Faltan: {missing_text}\n"
            f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
        )

    if not isinstance(script_data["solucion"], list) or len(script_data["solucion"]) != 3:
        raise OllamaError(
            "La clave 'solucion' debe ser una lista de exactamente 3 pasos.\n"
            f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
        )

    for key in ("hook", "problema", "explicacion", "cierre", "cta", "guion_narrado"):
        if not isinstance(script_data[key], str) or not script_data[key].strip():
            raise OllamaError(
                f"La clave '{key}' debe ser texto no vacio.\n"
                f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
            )

    for index, step in enumerate(script_data["solucion"], start=1):
        if not isinstance(step, str) or not step.strip():
            raise OllamaError(
                f"El paso {index} de 'solucion' esta vacio o no es texto.\n"
                f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
            )

    narration = " ".join(script_data["guion_narrado"].split()).strip()
    narration_without_cta = _remove_exact_cta(narration, script_data["cta"])
    naive_narration = build_naive_narration(script_data, include_cta=False)

    sentence_chunks = _sentence_chunks(narration)
    lower_narration = narration.lower()

    similarity = SequenceMatcher(
        None,
        _clean_compare_text(narration_without_cta),
        _clean_compare_text(naive_narration),
    ).ratio()

    exact_reuse = _count_exact_block_reuse(script_data, narration_without_cta)

    if len(sentence_chunks) < 4:
        raise OllamaError("guion_narrado debe tener al menos 4 frases completas.")

    if len(narration.split()) < 40:
        raise OllamaError("guion_narrado es demasiado corto para TTS natural.")

    if similarity > 0.92 and exact_reuse >= 4:
        raise OllamaError(
            "guion_narrado se parece demasiado a una concatenacion mecanica de bloques."
        )

    if exact_reuse >= 5:
        raise OllamaError(
            "guion_narrado reutiliza demasiados bloques literales del esquema original."
        )

    if not any(marker in lower_narration for marker in TRANSITION_MARKERS):
        raise OllamaError(
            "guion_narrado no muestra transiciones naturales suficientes entre ideas."
        )


def _normalize_script_data(script_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "hook": script_data["hook"].strip(),
        "problema": script_data["problema"].strip(),
        "explicacion": script_data["explicacion"].strip(),
        "solucion": [step.strip() for step in script_data["solucion"]],
        "cierre": script_data["cierre"].strip(),
        "cta": script_data["cta"].strip(),
        "guion_narrado": " ".join(script_data["guion_narrado"].split()).strip(),
    }


def generate_script(brief: Dict[str, Any]) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_SCRIPT.strip()},
        {"role": "user", "content": build_prompt(brief).strip()},
    ]

    last_error: Exception | None = None

    for attempt in range(1, OLLAMA_MAX_RETRIES + 1):
        try:
            script_data = _ollama_chat_json(messages)

            try:
                validate_script_data(script_data)
            except OllamaError as validation_error:
                if _should_try_rewrite(validation_error):
                    try:
                        repaired_narration = rewrite_guion_narrado(brief, script_data)
                        script_data["guion_narrado"] = repaired_narration
                        validate_script_data(script_data)
                    except OllamaError as rewrite_error:
                        last_error = OllamaError(
                            f"Intento {attempt} invalido tras reescritura: {rewrite_error}"
                        )
                        continue
                else:
                    last_error = OllamaError(
                        f"Intento {attempt} invalido: {validation_error}"
                    )
                    continue

            return _normalize_script_data(script_data)

        except requests.RequestException as exc:
            last_error = OllamaError(f"No se pudo conectar con Ollama: {exc}")
            continue
        except OllamaError as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    raise OllamaError("No fue posible generar un guion valido con Ollama.")


def _duration_seconds(brief: Dict[str, Any]) -> int:
    duration_raw = str(brief.get("duracion_seg", "0")).strip() or "0"
    try:
        return max(0, int(float(duration_raw)))
    except ValueError:
        return 0


def _keywords_list(brief: Dict[str, Any]) -> List[str]:
    return [keyword.strip() for keyword in str(brief.get("keywords", "")).split(",") if keyword.strip()]


def _character_design(brief: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "identity_anchor": brief.get("avatar", ""),
        "audience_mirror": brief.get("audiencia", ""),
        "persona_function": (
            "credible narrator or protagonist for short-form vertical content who embodies "
            "the problem-to-solution arc of the brief"
        ),
        "tone_alignment": brief.get("tono", ""),
        "styling_notes": brief.get("notas_direccion", ""),
        "consistency_rules": [
            "keep the same subject identity across all scenes unless the scene explicitly uses metaphor",
            "preserve wardrobe, age range, and general look continuity across the full piece",
            "match facial expression and body language to the emotional arc of each beat",
        ],
    }


def _scene_transition(index: int, total: int, role: str) -> str:
    if index == 1:
        return "cold_open"
    if role.startswith("solucion"):
        return "motivated_match_cut"
    if index == total:
        return "clean_end_hold"
    if role == "problema":
        return "smash_cut"
    if role == "explicacion":
        return "graphic_overlay_transition"
    return "fast_continuity_cut"


def _scene_specs(script: Dict[str, Any], brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    solucion = script.get("solucion", ["", "", ""])
    while len(solucion) < 3:
        solucion.append("")

    return [
        {
            "role": "hook",
            "text": script.get("hook", ""),
            "visual_intent": (
                "Open with an arresting visual contradiction that stops the scroll and "
                "frames the core thesis immediately."
            ),
            "camera": "extreme close-up or punch-in opening frame, direct subject emphasis",
            "mood": f"{brief.get('emocion_principal', 'tension')} and immediate urgency",
            "edit_intent": "start cold, first-frame clarity, aggressive pattern interrupt",
        },
        {
            "role": "problema",
            "text": script.get("problema", ""),
            "visual_intent": (
                "Show the pain point as a lived consequence, not as an abstract statement."
            ),
            "camera": "close-up with subtle handheld energy or invasive crop",
            "mood": f"{brief.get('emocion_principal', 'tension')} with discomfort",
            "edit_intent": "tight pacing, reactive cutaways, lived friction",
        },
        {
            "role": "explicacion",
            "text": script.get("explicacion", ""),
            "visual_intent": (
                "Make the hidden mechanism legible through symbolic or causal imagery."
            ),
            "camera": "medium close-up with graphic overlays or conceptual inserts",
            "mood": f"{brief.get('tono', 'directo')} with clarity",
            "edit_intent": "explain without slowing down, visual logic over exposition",
        },
        {
            "role": "solucion_1",
            "text": solucion[0],
            "visual_intent": "Present the first corrective move as immediate and executable.",
            "camera": "medium shot with decisive gesture or practical action",
            "mood": "clarity and momentum",
            "edit_intent": "clean instructional beat, no fluff",
        },
        {
            "role": "solucion_2",
            "text": solucion[1],
            "visual_intent": "Escalate from awareness to a repeatable habit or system.",
            "camera": "alternating close-up and insert detail for rhythm",
            "mood": "control and progression",
            "edit_intent": "show process, reinforce memorability",
        },
        {
            "role": "solucion_3",
            "text": solucion[2],
            "visual_intent": "Land the final action as the bridge to transformation.",
            "camera": "punch-in or lateral motion with stronger forward drive",
            "mood": f"{brief.get('emocion_secundaria', 'resolve')} with confidence",
            "edit_intent": "build toward payoff, stronger motion and contrast",
        },
        {
            "role": "cierre",
            "text": script.get("cierre", ""),
            "visual_intent": "Deliver the emotional payoff or wake-up call with conviction.",
            "camera": "steady medium close-up, hold slightly longer for impact",
            "mood": f"{brief.get('emocion_secundaria', 'impact')} with finality",
            "edit_intent": "slightly slower beat to let the message land",
        },
        {
            "role": "cta",
            "text": script.get("cta", ""),
            "visual_intent": "Close with a direct action cue that feels native to the platform.",
            "camera": "direct-to-camera end frame or simple branded end-card",
            "mood": "decisive and inviting",
            "edit_intent": "clean end beat, readable CTA, room for captions",
        },
    ]


def _distribute_sentences_across_scenes(
    sentence_chunks: List[str],
    specs: List[Dict[str, Any]],
) -> List[List[str]]:
    total = len(specs)
    groups: List[List[str]] = [[] for _ in range(total)]
    sentence_index = 0

    for spec_index, spec in enumerate(specs):
        role = spec["role"]
        remaining_scenes = total - spec_index
        remaining_sentences = len(sentence_chunks) - sentence_index

        if remaining_sentences <= 0:
            break

        take_count = 1
        if role == "hook":
            take_count = 1
        elif role in {"problema", "explicacion", "cierre"}:
            take_count = 1 if remaining_sentences <= remaining_scenes else 2
        elif role.startswith("solucion"):
            take_count = 1

        max_allowed = max(1, remaining_sentences - (remaining_scenes - 1))
        take_count = min(take_count, max_allowed)

        for _ in range(take_count):
            groups[spec_index].append(sentence_chunks[sentence_index])
            sentence_index += 1

    while sentence_index < len(sentence_chunks):
        groups[-1].append(sentence_chunks[sentence_index])
        sentence_index += 1

    return groups


def _scene_time_ranges(duration_sec: int, total_scenes: int) -> List[Dict[str, float]]:
    if total_scenes <= 0:
        return []

    if duration_sec <= 0:
        return [
            {"start_sec": round(float(index), 2), "end_sec": round(float(index + 1), 2)}
            for index in range(total_scenes)
        ]

    weights = []
    for index in range(total_scenes):
        if index == 0:
            weights.append(0.9)
        elif index == total_scenes - 1:
            weights.append(0.8)
        else:
            weights.append(1.0)

    total_weight = sum(weights)
    raw_durations = [duration_sec * (weight / total_weight) for weight in weights]

    current = 0.0
    ranges = []
    for index, raw_duration in enumerate(raw_durations):
        start = current
        end = duration_sec if index == total_scenes - 1 else current + raw_duration
        ranges.append({
            "start_sec": round(start, 2),
            "end_sec": round(end, 2),
        })
        current = end

    return ranges


def _build_scene_plan(script: Dict[str, Any], brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    narration = script.get("guion_narrado", "")
    sentence_chunks = _sentence_chunks(narration)
    specs = [spec for spec in _scene_specs(script, brief) if str(spec["text"]).strip()]
    total = len(specs)

    if total == 0:
        return []

    if not sentence_chunks:
        sentence_chunks = [narration] if narration else []

    duration_sec = _duration_seconds(brief)
    keyword_list = _keywords_list(brief)
    groups = _distribute_sentences_across_scenes(sentence_chunks, specs)
    time_ranges = _scene_time_ranges(duration_sec, total)
    character_design = _character_design(brief)

    scene_plan: List[Dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        narration_focus = " ".join(groups[index - 1]).strip() or spec["text"]
        scene_range = (
            time_ranges[index - 1]
            if index - 1 < len(time_ranges)
            else {"start_sec": None, "end_sec": None}
        )
        transition = _scene_transition(index, total, spec["role"])
        base_prompt = {
            "subject": character_design["identity_anchor"],
            "context": brief.get("idea_central", ""),
            "action": spec["text"],
            "environment": brief.get("historia_base", "") or brief.get("audiencia", ""),
            "style": brief.get("notas_direccion", "") or brief.get("referencias", ""),
            "keywords": keyword_list,
            "platform_bias": brief.get("plataforma", ""),
            "aspect_ratio": "9:16",
            "motion_cue": brief.get("ritmo", ""),
            "composition_goal": spec["camera"],
            "negative_prompt": brief.get("prohibido", ""),
        }
        scene_plan.append(
            {
                "scene_id": f"scene_{index:02d}",
                "scene_role": spec["role"],
                "start_sec": scene_range["start_sec"],
                "end_sec": scene_range["end_sec"],
                "text": narration_focus,
                "visual_intent": spec["visual_intent"],
                "camera": spec["camera"],
                "mood": spec["mood"],
                "transition": transition,
                "comfy_prompt_base": {
                    **base_prompt,
                    "workflow_hint": "single keyframe or key shot for downstream ComfyUI generation/editing",
                    "continuity_anchor": character_design["identity_anchor"],
                    "edit_intent": spec["edit_intent"],
                },
                "wan_prompt_base": {
                    **base_prompt,
                    "workflow_hint": "short motion beat for downstream Wan 2.2 video generation/editing",
                    "continuity_anchor": character_design["identity_anchor"],
                    "transition_hint": transition,
                    "motion_emphasis": brief.get("ritmo", ""),
                },
            }
        )

    return scene_plan


def build_visual_manifest(
    brief: Dict[str, Any],
    script: Dict[str, Any],
    job_id: str,
    audio_path: Path,
    subtitles_path: Path,
) -> Dict[str, Any]:
    scene_plan = _build_scene_plan(script, brief)
    duration_sec = _duration_seconds(brief)

    return {
        "manifest_version": "1.0",
        "pipeline_role": "editorial_preproduction_only",
        "downstream_target": "visual_repo_for_comfyui_wan_multimodal_editing",
        "id": job_id,
        "title": brief.get("idea_central", ""),
        "platform": brief.get("plataforma", ""),
        "language": brief.get("idioma", ""),
        "duration_sec": duration_sec,
        "aspect_ratio": "9:16",
        "brief_context": {
            "niche": brief.get("nicho", ""),
            "subniche": brief.get("subnicho", ""),
            "objective": brief.get("objetivo", ""),
            "audience": brief.get("audiencia", ""),
            "avatar": brief.get("avatar", ""),
            "core_pain": brief.get("dolor_principal", ""),
            "core_desire": brief.get("deseo_principal", ""),
            "core_fear": brief.get("miedo_principal", ""),
            "angle": brief.get("angulo", ""),
            "thesis": brief.get("tesis", ""),
            "enemy": brief.get("enemigo", ""),
            "common_error": brief.get("error_comun", ""),
            "promised_transformation": brief.get("transformacion_prometida", ""),
            "retention_goal": brief.get("objetivo_retencion", ""),
        },
        "script_context": {
            "hook": script.get("hook", ""),
            "problem": script.get("problema", ""),
            "explanation": script.get("explicacion", ""),
            "solution": script.get("solucion", []),
            "close": script.get("cierre", ""),
            "cta": script.get("cta", ""),
            "guion_narrado": script.get("guion_narrado", ""),
            "narrative_arc": [
                "hook",
                "problem",
                "explanation",
                "solution",
                "close",
                "cta",
            ],
        },
        "assets": {
            "audio": str(audio_path.relative_to(BASE_DIR).as_posix()),
            "subtitles": str(subtitles_path.relative_to(BASE_DIR).as_posix()),
        },
        "visual_style": {
            "tone": brief.get("tono", ""),
            "rhythm": brief.get("ritmo", ""),
            "narration_style": brief.get("estilo_narracion", ""),
            "emotional_primary": brief.get("emocion_principal", ""),
            "emotional_secondary": brief.get("emocion_secundaria", ""),
            "intensity": brief.get("nivel_intensidad", ""),
            "references": brief.get("referencias", ""),
            "visual_notes": brief.get("notas_direccion", ""),
            "keywords": brief.get("keywords", ""),
            "forbidden": brief.get("prohibido", ""),
        },
        "character_design": _character_design(brief),
        "edit_guidance": {
            "captions_source": "assets.subtitles",
            "voiceover_source": "assets.audio",
            "pacing": brief.get("ritmo", ""),
            "platform_native_behavior": "short-form vertical video, fast clarity, early payoff",
            "notes": (
                "This repository stops at editorial preproduction. "
                "The downstream visual repository is responsible for visual generation, "
                "multimodal assembly and any final video export."
            ),
        },
        "scene_plan": scene_plan,
    }


def write_index(rows: List[Dict[str, Any]]) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=INDEX_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def build_index_row(brief: Dict[str, Any], status: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    return {
        "job_id": job_id,
        "source_id": str(brief.get("id", "")).strip(),
        "estado_csv": brief.get("estado", ""),
        "idea_central": brief.get("idea_central", ""),
        "platform": brief.get("plataforma", ""),
        "language": brief.get("idioma", ""),
        "brief_created": status["brief_created"],
        "script_generated": status["script_generated"],
        "audio_generated": status["audio_generated"],
        "subtitles_generated": status["subtitles_generated"],
        "visual_manifest_generated": status["visual_manifest_generated"],
        "export_ready": status["export_ready"],
        "last_step": status["last_step"],
        "updated_at": status["updated_at"],
    }