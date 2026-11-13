"""
Catálogo de tipos de dashboard de datasets y sus requisitos de columnas.

Una sola fuente de verdad para:
  - detectar el tipo de un conjunto de columnas (``detect_type_from_names``),
    usado al crear un dataset o cuando el dataset aún no tiene tipo guardado;
  - validar que un Excel nuevo sigue siendo compatible con el tipo ya
    guardado en el dataset (``missing_requirements``), usado al actualizar.

Los nombres que se comparan son los ``Field.name`` (salida de
``normalize_name``), nunca los encabezados crudos del Excel.

El orden de ``_TYPES`` es el orden de prioridad de la detección y replica el
que tenía ``detect_dataset_type`` (denuncias primero, censo_animal al final).
"""
from __future__ import annotations

from typing import Callable, Iterable

from app.modules.datasets.red_animalia import is_red_animalia

GENERIC = "generico"

TYPE_LABELS = {
    "denuncias": "Denuncias",
    "donaton": "Donatón",
    "personas_capacitadas_consolidado": "Personas capacitadas (consolidado)",
    "personas_capacitadas": "Personas capacitadas",
    "red_animalia": "Red Animalia",
    "animales": "Animales / protectores",
    "presupuesto": "Presupuesto (Z080)",
    "censo_animal": "Censo animal",
    GENERIC: "Genérico",
}

KNOWN_TYPES = frozenset(TYPE_LABELS)


# ── helpers de requisitos ────────────────────────────────────────────────────
# Un requisito es (descripción legible, test(names) -> bool).

def _exact(*alternatives: str):
    """Alguna de las columnas exactas indicadas."""
    label = " o ".join(alternatives)
    return label, lambda names: any(a in names for a in alternatives)


def _contains(*parts: str, label: str):
    """Alguna columna cuyo nombre contenga todas las partes."""
    return label, lambda names: any(all(p in n for p in parts) for n in names)


def _all_exact(*cols: str):
    return [_exact(c) for c in cols]


def _red_animalia_req():
    return "estructura Red Animalia (vinculación + perros + gatos, o formato unificado)", is_red_animalia


# Cada tipo: lista de "variantes"; el tipo aplica si alguna variante se
# cumple completa. Cada variante es una lista de requisitos.
_TYPES: list[tuple[str, list[list[tuple[str, Callable[[set], bool]]]]]] = [
    ("denuncias", [[
        _contains("numero_de_caso", label="numero_de_caso"),
        _contains("denunciante", label="columna con 'denunciante'"),
        _contains("motivo", label="columna con 'motivo'"),
    ]]),
    ("donaton", [[
        _exact("municipio"),
        _contains("alimento", "perro", label="columna de alimento perro"),
        _contains("alimento", "gato", label="columna de alimento gato"),
    ]]),
    ("personas_capacitadas_consolidado", [
        _all_exact("mujer", "hombre", "municipio", "guia_1", "guia_2", "guia_3",
                   "rural", "urbana", "fecha"),
    ]),
    ("personas_capacitadas", [
        _all_exact("mujer", "hombre", "municipio", "guia_1"),
    ]),
    ("red_animalia", [[_red_animalia_req()]]),
    ("animales", [
        _all_exact("perros_cantidad", "gatos_cantidad",
                   "tipo_de_vinculacion_dentro_de_la_red_animalia_valle"),
        _all_exact("nombres_y_apellidos", "municipio", "otro_telefono", "correo_electronico"),
    ]),
    ("presupuesto", [[
        # Formato resumido (2026) y formato completo SAP del Z080
        # ("Presup. Definitivo", "Presup. Dispon.").
        _exact("apropiacion_definitiva", "presup_definitivo"),
        _exact("presup_disponible", "presup_dispon"),
        _exact("cdp_ejecutado", "total_ejecutado"),
    ]]),
    ("censo_animal", [
        _all_exact("poblacion_perros_2026", "poblacion_gatos_2026", "municipio"),
        [
            _exact("municipio"),
            _contains("perros", label="columna con 'perros'"),
            _contains("gatos", label="columna con 'gatos'"),
        ],
    ]),
]

_TYPE_INDEX = dict(_TYPES)


def _names(field_names: Iterable[str]) -> set[str]:
    return {str(n).lower() for n in field_names}


def is_specific(dtype: str | None) -> bool:
    return bool(dtype) and dtype != GENERIC and dtype in KNOWN_TYPES


def detect_type_from_names(field_names: Iterable[str]) -> str:
    names = _names(field_names)
    for dtype, variants in _TYPES:
        if any(all(test(names) for _, test in variant) for variant in variants):
            return dtype
    return GENERIC


def missing_requirements(dtype: str, field_names: Iterable[str]) -> list[str]:
    """
    Requisitos que faltan para que las columnas sean compatibles con ``dtype``.
    Lista vacía = compatible. Para tipos con varias variantes se informa la
    variante más cercana (la que tiene menos faltantes).
    """
    if not is_specific(dtype):
        return []
    names = _names(field_names)
    best: list[str] | None = None
    for variant in _TYPE_INDEX[dtype]:
        missing = [label for label, test in variant if not test(names)]
        if not missing:
            return []
        if best is None or len(missing) < len(best):
            best = missing
    return best or []


def is_compatible(dtype: str, field_names: Iterable[str]) -> bool:
    return not missing_requirements(dtype, field_names)


def type_label(dtype: str | None) -> str:
    return TYPE_LABELS.get(dtype or GENERIC, dtype or GENERIC)
