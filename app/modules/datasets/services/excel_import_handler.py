from datetime import datetime
from unicodedata import normalize as _ud_normalize

import pandas as pd
from app.modules.datasets.models.dataset import Dataset
from app.modules.datasets.models.table import Table
from app.modules.datasets.services.field_handler import create_fields, plan_field_names
from app.modules.datasets.services.record_import_handler import import_records
from app.modules.datasets.validators.dataset_validator import validate_dataset_name
from app.utils.normalizers import MAX_TABLE_NAME_LENGTH, normalize_name
from app.core.extensions import db
from app.modules.datasets.red_animalia import is_red_animalia
from app.modules.datasets.dashboard.dataset_types import (
    GENERIC, detect_type_from_names, is_compatible, is_specific,
    missing_requirements, type_label,
)

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
    # Members with basic identity remain valid even with optional answers missing.
    animalia = is_red_animalia(normalize_name(c) for c in df.columns)
    member_columns = [c for c in df.columns if normalize_name(c) == "nombres_y_apellidos"]
    member_rows = pd.Series(False, index=df.index)
    if animalia:
        for column in member_columns:
            member_rows |= df[column].notna() & df[column].astype(str).str.strip().ne("")

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
    df = df[(df.notna().sum(axis=1) >= min_row_values) | member_rows.reindex(df.index, fill_value=False)]
    if df.empty:
        return df, 0

    # 5. Eliminar filas resumen explícitas. Fuente de verdad = filas reales.
    summary_mask = df.apply(_is_summary_row, axis=1)
    summary_count = int(summary_mask.sum())
    if summary_count:
        df = df.loc[~summary_mask]

    return df, summary_count


def _prepare_sheets(excel) -> tuple[list[dict], int, int]:
    """
    Lee y limpia todas las hojas SIN tocar la base de datos.

    Devuelve ``(hojas, filas_descartadas, filas_resumen)``; cada hoja es
    ``{"sheet", "table_name", "df", "field_names"}``. Separar la lectura de la
    escritura permite validar el Excel completo antes de reemplazar datos.
    """
    sheets = []
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
                f"[INFO] Hoja '{sheet_name}': {dropped_summary} fila(s) "
                f"resumen descartadas (ENTREGADO/TOTAL/RESUMEN)."
            )

        sheets.append({
            "sheet": sheet_name,
            "table_name": normalize_name(sheet_name, MAX_TABLE_NAME_LENGTH),
            "df": df,
            "field_names": list(plan_field_names(df.columns).values()),
        })

    return sheets, skipped_rows, summary_rows_dropped


def _main_type(field_name_groups) -> str:
    """Tipo del dataset = primer grupo de columnas (hoja/tabla) con tipo específico."""
    for names in field_name_groups:
        dtype = detect_type_from_names(names)
        if is_specific(dtype):
            return dtype
    return GENERIC


def _write_sheets(dataset_id: int, sheets: list[dict], description: str) -> dict:
    counts = {"tables_created": 0, "fields_created": 0,
              "records_inserted": 0, "failed_rows": 0}
    for sheet in sheets:
        table = Table(
            dataset_id=dataset_id,
            name=sheet["table_name"],
            description=description,
        )
        db.session.add(table)
        db.session.flush()
        counts["tables_created"] += 1

        field_map = create_fields(table, sheet["df"])
        counts["fields_created"] += len(field_map)

        inserted, failed = import_records(table, sheet["df"], field_map)
        counts["records_inserted"] += inserted
        counts["failed_rows"] += failed
    return counts


def import_excel_dataset(file, dataset_name):
    try:
        excel = pd.ExcelFile(file)
    except Exception as e:
        traceback.print_exc()
        return {"message": f"No se pudo leer el archivo Excel: {e}"}, 400

    try:
        sheets, skipped_rows, summary_rows_dropped = _prepare_sheets(excel)
        # El tipo de dashboard se decide una sola vez, al crear el dataset, y
        # queda guardado para las actualizaciones siguientes.
        dataset_type = _main_type(s["field_names"] for s in sheets)

        dataset = Dataset(
            name=dataset_name,
            description="Importado desde Excel",
            dataset_type=dataset_type,
        )
        db.session.add(dataset)
        db.session.flush()

        counts = _write_sheets(dataset.id, sheets, "Importado desde Excel")

        db.session.commit()

        return {
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "dataset_type": dataset_type,
            "dataset_type_label": type_label(dataset_type),
            **counts,
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


def update_excel_dataset(file, dataset_id, dataset_name: str | None = None,
                         allow_type_change: bool = False):
    """
    Reemplaza el contenido de un dataset existente (mismo ``dataset_id``) con
    un Excel nuevo, conservando su tipo de dashboard.

    - El dataset se identifica por ID; el nombre del archivo no influye.
    - Si el dataset tiene un tipo específico (presupuesto, denuncias, ...) y
      ninguna hoja del Excel nuevo tiene las columnas que ese dashboard
      necesita, NO se modifica nada y se responde 409 con las columnas
      faltantes (a menos que ``allow_type_change`` lo autorice).
    - Toda la validación ocurre antes de borrar las tablas anteriores.
    """
    try:
        from app.modules.datasets.models.field import Field
        from app.modules.datasets.models.record import Record

        dataset = Dataset.query.get(dataset_id)
        if not dataset:
            return {"error": "Dataset no encontrado", "message": "Dataset no encontrado"}, 404

        name_changed = False
        if dataset_name:
            new_name = dataset_name.strip()
            if new_name and new_name != dataset.name:
                validate_dataset_name(new_name, dataset_id)
                dataset.name = new_name
                name_changed = True

        counts = {"tables_created": 0, "fields_created": 0,
                  "records_inserted": 0, "failed_rows": 0}
        skipped_rows = 0
        summary_rows_dropped = 0
        previous_type = dataset.dataset_type
        columns_added: list[str] = []
        columns_removed: list[str] = []
        warnings: list[str] = []

        if file is not None:
            try:
                excel = pd.ExcelFile(file)
            except Exception as e:
                db.session.rollback()
                msg = f"No se pudo leer el archivo Excel: {e}"
                return {"error": msg, "message": msg}, 400

            sheets, skipped_rows, summary_rows_dropped = _prepare_sheets(excel)
            if not sheets:
                db.session.rollback()
                msg = "El archivo no contiene hojas con datos. No se modificó el dataset."
                return {"error": msg, "message": msg, "code": "EMPTY_WORKBOOK"}, 400

            old_tables = Table.query.filter_by(dataset_id=dataset_id).order_by(Table.id).all()
            old_groups = [
                [f.name for f in Field.query.filter_by(table_id=t.id).all()]
                for t in old_tables
            ]
            new_groups = [s["field_names"] for s in sheets]

            # Datasets anteriores a la columna dataset_type: el tipo previo se
            # deduce de las columnas que ya estaban cargadas.
            if not previous_type and old_groups:
                previous_type = _main_type(old_groups)

            detected_type = _main_type(new_groups)

            if is_specific(previous_type):
                if any(is_compatible(previous_type, g) for g in new_groups):
                    final_type = previous_type
                elif allow_type_change:
                    final_type = detected_type
                    warnings.append(
                        f"El dashboard cambió de '{type_label(previous_type)}' "
                        f"a '{type_label(detected_type)}' por confirmación del usuario."
                    )
                else:
                    db.session.rollback()
                    missing = min(
                        (missing_requirements(previous_type, g) for g in new_groups),
                        key=len,
                    )
                    msg = (
                        f"El archivo no es compatible con el dashboard "
                        f"'{type_label(previous_type)}' de este dataset. "
                        f"Faltan columnas: {', '.join(missing)}. "
                        f"No se modificó el dataset."
                    )
                    return {
                        "error": msg,
                        "message": msg,
                        "code": "DATASET_TYPE_INCOMPATIBLE",
                        "expected_type": previous_type,
                        "expected_type_label": type_label(previous_type),
                        "detected_type": detected_type,
                        "detected_type_label": type_label(detected_type),
                        "missing_columns": missing,
                    }, 409
            else:
                # Genérico o sin tipo: puede "subir" a un tipo específico si
                # el Excel nuevo ya trae las columnas de uno.
                final_type = detected_type

            old_names = {n for g in old_groups for n in g}
            new_names = {n for g in new_groups for n in g}
            columns_added = sorted(new_names - old_names) if old_names else []
            columns_removed = sorted(old_names - new_names)
            if columns_removed:
                warnings.append(
                    "Columnas que ya no vienen en el archivo: " + ", ".join(columns_removed)
                )

            for t in old_tables:
                Record.query.filter_by(table_id=t.id).delete()
                Field.query.filter_by(table_id=t.id).delete()
                db.session.delete(t)
            db.session.flush()

            counts = _write_sheets(dataset_id, sheets, "Actualizado desde Excel")
            dataset.dataset_type = final_type

        if file is not None or name_changed:
            dataset.updated_at = datetime.utcnow()

        db.session.commit()

        return {
            "dataset_id": dataset_id,
            "dataset_name": dataset.name,
            "dataset_type": dataset.dataset_type,
            "dataset_type_label": type_label(dataset.dataset_type),
            "previous_dataset_type": previous_type,
            **counts,
            "skipped_rows": skipped_rows,
            "summary_rows_dropped": summary_rows_dropped,
            "columns_added": columns_added,
            "columns_removed": columns_removed,
            "warnings": warnings,
            "name_changed": name_changed,
            "file_processed": file is not None,
        }

    except Exception as e:
        db.session.rollback()
        print("[ERROR] update_excel_dataset:")
        traceback.print_exc()
        return {"error": str(e), "message": str(e)}, 500
