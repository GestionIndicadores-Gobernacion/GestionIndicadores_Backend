from .orchestrator import orchestrate
from .dataset_types import (
    GENERIC, detect_type_from_names, is_specific, missing_requirements, type_label,
)


def detect_dataset_type(fields, name_hint: str = "") -> str:
    """
    Detección heurística por columnas. Solo se usa cuando el dataset no tiene
    un tipo guardado (datasets nuevos o anteriores a la columna
    ``datasets.dataset_type``). ``name_hint`` se conserva por compatibilidad
    de firma pero ya no decide el tipo: la identificación estable es el tipo
    persistido en el dataset, no el nombre del archivo.
    """
    return detect_type_from_names(f.name for f in fields)


def resolve_dataset_type(fields, stored_type: str | None) -> tuple[str, str, str | None]:
    """
    Decide qué dashboard usar para una tabla.

    Devuelve ``(dataset_type, source, warning)``:
      - ``stored``   → el tipo guardado en el dataset y la tabla es compatible.
      - ``detected`` → no hay tipo específico guardado; se detecta por columnas.
      - ``fallback`` → hay tipo guardado pero la tabla no tiene sus columnas
        (p. ej. una hoja auxiliar); se detecta y se informa el motivo en
        ``warning`` en lugar de caer al genérico en silencio.
    """
    names = [f.name for f in fields]
    if is_specific(stored_type):
        missing = missing_requirements(stored_type, names)
        if not missing:
            return stored_type, "stored", None
        detected = detect_type_from_names(names)
        warning = (
            f"Esta tabla no tiene las columnas del dashboard "
            f"'{type_label(stored_type)}' asignado al dataset "
            f"(faltan: {', '.join(missing)}). Se muestra el dashboard "
            f"'{type_label(detected)}'."
        )
        return detected, "fallback", warning
    return detect_type_from_names(names), "detected", None


def analyze_dataset(fields, records, name_hint: str = "", stored_type: str | None = None) -> dict:
    dtype, source, warning = resolve_dataset_type(fields, stored_type)

    total = len(records)
    if total == 0:
        result = {"kpis": [], "sections": [], "total": 0}
    else:
        field_values = {f.name: [r.data.get(f.name) for r in records] for f in fields}
        result = orchestrate(dtype, fields, field_values, total)

    # Sin registros las vistas específicas no tienen qué pintar: se mantiene
    # el comportamiento anterior (vista genérica vacía).
    result["dataset_type"] = dtype if total else GENERIC
    result["dataset_type_source"] = source
    if warning:
        result["dataset_type_warning"] = warning
    return result
