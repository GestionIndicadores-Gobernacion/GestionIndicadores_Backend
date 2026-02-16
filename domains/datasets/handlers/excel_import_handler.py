import pandas as pd
from domains.datasets.models.dataset import Dataset
from domains.datasets.models.table import Table
from domains.datasets.handlers.field_handler import create_fields
from domains.datasets.handlers.record_import_handler import import_records
from domains.utils.normalizers import MAX_TABLE_NAME_LENGTH, normalize_name
from extensions import db


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

    for sheet_name in excel.sheet_names:
        df = excel.parse(sheet_name)

        if df.empty:
            continue

        df = df.dropna(axis=1, how="all")
        if df.empty:
            continue

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
        "failed_rows": failed_rows
    }
