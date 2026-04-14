# ─── Fuente única de verdad para los tipos de métrica ────────────────────────

METRIC_TYPES = [
    "report_count",        # cuenta reportes del componente
    "report_sum",          # suma un campo numérico plano del reporte
    "report_sum_nested",   # suma un campo numérico dentro de un JSON anidado
    "dataset_sum",         # suma columna de dataset externo
    "dataset_count",       # cuenta registros de dataset externo
    "manual",              # valor ingresado manualmente
]