from datetime import datetime
from unicodedata import normalize as _ud_normalize

import pandas as pd
from app.modules.datasets.models.dataset import Dataset
from app.modules.datasets.models.table import Table
from app.modules.datasets.services.field_handler import create_fields
from app.modules.datasets.services.record_import_handler import import_records
from app.modules.datasets.validators.dataset_validator import validate_dataset_name
from app.utils.normalizers import MAX_TABLE_NAME_LENGTH, normalize_name
from app.core.extensions import db

# Una fila necesita al menos esta fracción de columnas con datos para importarse.
# Ejemplo: 0.3 significa que si hay 10 columnas, al menos 3 deben tener valor.
MIN_ROW_FILL_RATIO = 0.3

# Mínimo de valores no-nulos que debe tener una columna para no descartarse.
# Columnas con menos valores que este % de las filas se descartan.
MIN_COL_FILL_RATIO = 0.05

# Etiquetas que marcan una fila como resumen agregado (no es un registro real).
# Se comparan tras normalizar a mayúsculas sin acentos ni signos.
SUMMARY_ROW_LABELS = {
    "ENTREGADO", "ENTREGADOS", "ENTREGADAS",
    "TOTAL", "TOTAL GENERAL", "TOTALES",
    "RESUMEN", "RESUMEN GENERAL",
    "SUBTOTAL", "SUBTOTALES",
    "GRAN TOTAL", "SUMA", "SUMA TOTAL",
}

# Hojas auxiliares de Google Forms/Sheets (AutoCrat, scripts de macro, etc.)
# que NO contienen datos de negocio y deben ignorarse al importar.
# Se compara con el nombre normalizado a mayúsculas y sin espacios al inicio.
SKIP_SHEET_PATTERNS = (
    "DO NOT DELETE",
    "NVSCRIPTSPROPERTIES",
    "AUTOCRAT",
    "FORM RESPONSES METADATA",
    "_METADATA",
)


def _should_skip_sheet(sheet_name: str) -> bool:
    name = (sheet_name or "").strip().upper()
    return any(p in name for p in SKIP_SHEET_PATTERNS)


import traceback


def _normalize_label(value) -> str:
    """Normaliza un valor a etiqueta comparable (mayúsculas, sin acentos, trim)."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    s = _ud_normalize("NFKD", s)
    s = "".join(c for c in s if not _is_combining(c))
    return " ".join(s.upper().split())


def _is_combining(ch: str) -> bool:
    import unicodedata
    return unicodedata.combining(ch) != 0


def _is_summary_row(row: pd.Series) -> bool:
    """
    Detecta filas resumen agregadas (ENTREGADO, TOTAL GENERAL, RESUMEN, ...).

    Reglas:
    1. Cualquier celda no-nula contiene una etiqueta resumen conocida
       (p. ej. "ENTREGADO", "TOTAL", "RESUMEN").
    2. Patrón "etiqueta + agregados": exactamente una celda de texto
       descriptivo y el resto sólo números — típico de filas como
       "PERRO | 13691" debajo de un bloque "ENTREGADO".
    """
    non_null = row.dropna()
    if non_null.empty:
        return False

    # 1. Etiquetas resumen explícitas
    for v in non_null:
        if _normalize_label(v) in SUMMARY_ROW_LABELS:
            return True

    return False


def _clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Limpia el DataFrame antes de importar y devuelve (df_limpio, filas_resumen_descartadas):
    - Elimina columnas completamente vacías.
    - Elimina columnas con muy pocos valores (< MIN_COL_FILL_RATIO).
    - Elimina filas completamente vacías.
    - Elimina filas con muy pocos valores (< MIN_ROW_FILL_RATIO de las columnas).
    - Elimina filas resumen (ENTREGADO / TOTAL GENERAL / RESUMEN / ...) de
      forma explícita para que no contaminen los KPIs ni las gráficas.
    """
    # 1. Eliminar columnas 100% vacías
    df = df.dropna(axis=1, how="all")
    if df.empty:
        return df, 0

    # 2. Eliminar columnas con menos del MIN_COL_FILL_RATIO de datos
    min_col_values = max(1, int(len(df) * MIN_COL_FILL_RATIO))
    df = df.loc[:, df.notna().sum(axis=0) >= min_col_values]
    if df.empty:
        return df, 0

    # 3. Eliminar filas 100% vacías
    df = df.dropna(axis=0, how="all")
    if df.empty:
        return df, 0

    # 4. Eliminar filas con menos del MIN_ROW_FILL_RATIO de columnas con datos
    min_row_values = max(1, int(len(df.columns) * MIN_ROW_FILL_RATIO))
    df = df[df.notna().sum(axis=1) >= min_row_values]
    if df.empty:
        return df, 0

    # 5. Eliminar filas resumen explícitas. Fuente de verdad = filas reales.
    summary_mask = df.apply(_is_summary_row, axis=1)
    summary_count = int(summary_mask.sum())
    if summary_count:
        df = df.loc[~summary_mask]

    return df, summary_count


def import_excel_dataset(file, dataset_name):
    try:
        excel = pd.ExcelFile(file)
    except Exception as e:
        traceback.print_exc()
        return {"message": f"No se pudo leer el archivo Excel: {e}"}, 400

    try:
        dataset = Dataset(
            name=dataset_name,
            description="Importado desde Excel"
        )
        db.session.add(dataset)
        db.session.flush()

        tables_created = 0
        fields_created = 0
        records_inserted = 0
        failed_rows = 0
        skipped_rows = 0
        summary_rows_dropped = 0

        for sheet_name in excel.sheet_names:
            if _should_skip_sheet(sheet_name):
                print(f"[INFO] Hoja '{sheet_name}' ignorada (auxiliar de Google Forms/AutoCrat).")
                continue

            df = excel.parse(sheet_name)

            if df.empty:
                continue

            original_rows = len(df)
            df, dropped_summary = _clean_dataframe(df)

            if df.empty:
                continue

            skipped_rows += original_rows - len(df)
            summary_rows_dropped += dropped_summary
            if dropped_summary:
                print(
                    f"[INFO] Hoja '{sheet_name}': {dropped_summary} fila(s) resumen "
                    f"descartadas (ENTREGADO/TOTAL/RESUMEN)."
                )

            table = Table(
                dataset_id=dataset.id,
                name=normalize_name(sheet_name, MAX_TABLE_NAME_LENGTH),
                description="Importado desde Excel"
            )

            db.session.add(table)
            db.session.flush()
            tables_created += 1

            field_map = create_fields(table, df)
            fields_created += len(field_map)

            inserted, failed = import_records(table, df, field_map)
            records_inserted += inserted
            failed_rows += failed

        db.session.commit()

        return {
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "tables_created": tables_created,
            "fields_created": fields_created,
            "records_inserted": records_inserted,
            "failed_rows": failed_rows,
            "skipped_rows": skipped_rows,
            "summary_rows_dropped": summary_rows_dropped,
        }

    except Exception as e:
        db.session.rollback()
        print("[ERROR] import_excel_dataset:")
        traceback.print_exc()
        msg = str(e).lower()
        if "duplicate key" in msg or "unique constraint" in msg:
            return {"message": f"Ya existe un dataset con el nombre '{dataset_name}'."}, 400
        if "value too long" in msg:
            return {"message": "Algún encabezado o valor excede la longitud permitida."}, 400
        if "json" in msg and "serial" in msg:
            return {"message": "El Excel contiene un valor que no se puede serializar (revisa fechas/horas)."}, 400
        return {"message": f"No se pudo importar el Excel: {e}"}, 400
    

def update_excel_dataset(file, dataset_id, dataset_name: str | None = None):
    import traceback
    try:
        from app.modules.datasets.models.field import Field
        from app.modules.datasets.models.record import Record

        dataset = Dataset.query.get(dataset_id)
        if not dataset:
            return {"error": "Dataset no encontrado"}, 404

        name_changed = False
        if dataset_name:
            new_name = dataset_name.strip()
            if new_name and new_name != dataset.name:
                validate_dataset_name(new_name, dataset_id)
                dataset.name = new_name
                name_changed = True

        tables_created = 0
        fields_created = 0
        records_inserted = 0
        failed_rows = 0
        skipped_rows = 0
        summary_rows_dropped = 0

        if file is not None:
            excel = pd.ExcelFile(file)

            old_tables = Table.query.filter_by(dataset_id=dataset_id).all()
            for t in old_tables:
                Record.query.filter_by(table_id=t.id).delete()
                Field.query.filter_by(table_id=t.id).delete()
                db.session.delete(t)
            db.session.flush()

            for sheet_name in excel.sheet_names:
                if _should_skip_sheet(sheet_name):
                    print(f"[INFO] Hoja '{sheet_name}' ignorada (auxiliar de Google Forms/AutoCrat).")
                    continue

                df = excel.parse(sheet_name)
                if df.empty:
                    continue

                original_rows = len(df)
                df, dropped_summary = _clean_dataframe(df)
                if df.empty:
                    continue

                skipped_rows += original_rows - len(df)
                summary_rows_dropped += dropped_summary
                if dropped_summary:
                    print(
                        f"[INFO] Hoja '{sheet_name}': {dropped_summary} fila(s) "
                        f"resumen descartadas (ENTREGADO/TOTAL/RESUMEN)."
                    )

                table = Table(
                    dataset_id=dataset_id,
                    name=normalize_name(sheet_name, MAX_TABLE_NAME_LENGTH),
                    description="Actualizado desde Excel"
                )
                db.session.add(table)
                db.session.flush()
                tables_created += 1

                field_map = create_fields(table, df)
                fields_created += len(field_map)

                inserted, failed = import_records(table, df, field_map)
                records_inserted += inserted
                failed_rows += failed

        if file is not None or name_changed:
            dataset.updated_at = datetime.utcnow()

        db.session.commit()

        return {
            "dataset_id": dataset_id,
            "dataset_name": dataset.name,
            "tables_created": tables_created,
            "fields_created": fields_created,
            "records_inserted": records_inserted,
            "failed_rows": failed_rows,
            "skipped_rows": skipped_rows,
            "summary_rows_dropped": summary_rows_dropped,
            "name_changed": name_changed,
            "file_processed": file is not None,
        }

    except Exception as e:
        db.session.rollback()
        print("[ERROR] update_excel_dataset:")
        traceback.print_exc()
        return {"error": str(e)}, 500