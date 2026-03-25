# main.py

import csv
import json
from typing import Any, Dict, List

from config import DATA_FILE, OUTPUT_FILE
from director import OllamaError, generate_script

REQUIRED_COLUMNS = {
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


def _clean_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value.strip() if isinstance(value, str) else value
        for key, value in row.items()
    }


def _validate_headers(fieldnames: List[str] | None) -> None:
    if not fieldnames:
        raise ValueError(f"El archivo CSV está vacío o no tiene cabeceras: {DATA_FILE}")

    missing = sorted(REQUIRED_COLUMNS - set(fieldnames))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Faltan columnas obligatorias en {DATA_FILE}: {missing_text}")


def load_briefs() -> List[Dict[str, Any]]:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"No existe el archivo de briefs: {DATA_FILE}. "
            "Crea data\\ideas.csv antes de ejecutar python main.py."
        )

    briefs: List[Dict[str, Any]] = []

    with DATA_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        _validate_headers(reader.fieldnames)

        for row in reader:
            clean_row = _clean_row(row)
            estado = clean_row.get("estado", "").lower()
            if estado != "pending":
                continue
            briefs.append(clean_row)

    if not briefs:
        raise ValueError(f"No hay briefs con estado 'pending' en {DATA_FILE}")

    return briefs


def save_results(results: List[Dict[str, Any]]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)


def main() -> None:
    print("Cargando briefs...")
    briefs = load_briefs()

    results: List[Dict[str, Any]] = []

    for index, brief in enumerate(briefs, start=1):
        title = brief.get("idea_central", f"brief_{index}")
        print(f"[{index}/{len(briefs)}] {title}")

        try:
            script = generate_script(brief)

            results.append({
                "id": brief.get("id"),
                "estado": "done",
                "idea_central": brief.get("idea_central"),
                "plataforma": brief.get("plataforma"),
                "duracion_seg": brief.get("duracion_seg"),
                "script": script,
            })

        except OllamaError as exc:
            print(f"ERROR: {exc}")
            results.append({
                "id": brief.get("id"),
                "estado": "error",
                "idea_central": brief.get("idea_central"),
                "error": str(exc),
            })
        except Exception as exc:
            print(f"ERROR inesperado: {exc}")
            results.append({
                "id": brief.get("id"),
                "estado": "error",
                "idea_central": brief.get("idea_central"),
                "error": f"Error inesperado: {exc}",
            })

    save_results(results)
    print(f"Resultado guardado en: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()