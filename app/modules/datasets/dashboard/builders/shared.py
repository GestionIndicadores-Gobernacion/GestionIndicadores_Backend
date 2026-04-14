from ..formatters import (
    COLORS, norm, is_yes, is_no, fill_rate,
    group_similar, make_bars, bar_section,
    numeric_bins, numeric_stats, unique_clean
)
import re

GENDER_FIELDS  = {"mujer", "hombre", "intersesual", "lgbtiq_"}
ZONA_FIELDS    = {"rural", "urbana"}
GUIA_KEYWORDS  = {"guia", "guía"}
GRUPOS_FIELDS  = {"afro", "indigena", "rrom", "discapacidad", "victima", "reincorporado"}
SKIP_YESNO     = GENDER_FIELDS | ZONA_FIELDS | GRUPOS_FIELDS
ANIMAL_KW      = {"perro", "gato", "animal", "especie", "felino", "canino"}


def _global_fill_rate(fields, field_values, total) -> float:
    if not fields or not total:
        return 100.0
    rates = [
        sum(1 for v in field_values[f.name] if v is not None and str(v).strip()) / total * 100
        for f in fields
    ]
    return round(sum(rates) / len(rates), 1) if rates else 100.0