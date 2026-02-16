from domains.datasets.models.record import Record
from domains.utils.normalizers import normalize_value
from extensions import db


def import_records(table, df, field_map):
    inserted = 0
    failed = 0

    for idx, row in df.iterrows():
        row_data = {}

        for col, value in row.items():
            value = normalize_value(value)
            if value is not None:
                row_data[field_map[col]] = value

        if not row_data:
            continue

        try:
            record = Record(
                table_id=table.id,
                data=row_data
            )
            db.session.add(record)
            inserted += 1

        except Exception as e:
            failed += 1
            print(f"❌ Record {idx} failed:", e)

    return inserted, failed
