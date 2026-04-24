from datetime import datetime

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


import traceback
print("✅ excel_import_handler cargado correctamente")

def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia el DataFrame antes de importar:
    - Elimina columnas completamente vacías.
    - Elimina columnas con muy pocos valores (< MIN_COL_FILL_RATIO).
    - Elimina filas completamente vacías.
    - Elimina filas con muy pocos valores (< MIN_ROW_FILL_RATIO de las columnas).
    """
    # 1. Eliminar columnas 100% vacías
    df = df.dropna(axis=1, how="all")
    if df.empty:
        return df

    # 2. Eliminar columnas con menos del MIN_COL_FILL_RATIO de datos
    min_col_values = max(1, int(len(df) * MIN_COL_FILL_RATIO))
    df = df.loc[:, df.notna().sum(axis=0) >= min_col_values]
    if df.empty:
        return df

    # 3. Eliminar filas 100% vacías
    df = df.dropna(axis=0, how="all")
    if df.empty:
        return df

    # 4. Eliminar filas con menos del MIN_ROW_FILL_RATIO de columnas con datos
    min_row_values = max(1, int(len(df.columns) * MIN_ROW_FILL_RATIO))
    df = df[df.notna().sum(axis=1) >= min_row_values]

    return df


def import_excel_dataset(file, dataset_name):
    excel = pd.ExcelFile(file)

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

    for sheet_name in excel.sheet_names:
        df = excel.parse(sheet_name)

        if df.empty:
            continue

        original_rows = len(df)
        df = _clean_dataframe(df)

        if df.empty:
            continue

        skipped_rows += original_rows - len(df)

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
    }
    

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

        if file is not None:
            excel = pd.ExcelFile(file)

            old_tables = Table.query.filter_by(dataset_id=dataset_id).all()
            for t in old_tables:
                Record.query.filter_by(table_id=t.id).delete()
                Field.query.filter_by(table_id=t.id).delete()
                db.session.delete(t)
            db.session.flush()

            for sheet_name in excel.sheet_names:
                df = excel.parse(sheet_name)
                if df.empty:
                    continue

                original_rows = len(df)
                df = _clean_dataframe(df)
                if df.empty:
                    continue

                skipped_rows += original_rows - len(df)

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
            "name_changed": name_changed,
            "file_processed": file is not None,
        }

    except Exception as e:
        db.session.rollback()
        print("❌ ERROR en update_excel_dataset:")
        traceback.print_exc()
        return {"error": str(e)}, 500