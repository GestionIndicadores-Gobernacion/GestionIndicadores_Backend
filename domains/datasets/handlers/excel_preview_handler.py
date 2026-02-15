import pandas as pd

from domains.utils.inference import infer_field_type
from domains.utils.normalizers import normalize_name, normalize_value


def preview_excel(file):
    excel = pd.ExcelFile(file)
    preview = []

    for sheet in excel.sheet_names:
        df = excel.parse(sheet)

        if df.empty:
            continue

        info = {
            "sheet_name": sheet,
            "rows_total": len(df),
            "rows_with_data": int(df.dropna(how="all").shape[0]),
            "fields": [],
            "sample_rows": []
        }

        for col in df.columns:
            if df[col].dropna().empty:
                continue

            info["fields"].append({
                "column": str(col),
                "field_name": normalize_name(col),
                "type": infer_field_type(df[col])
            })

        df_used = df.dropna(how="all")

        for _, row in df_used.head(5).iterrows():
            row_data = {}
            for col, value in row.items():
                value = normalize_value(value)
                if value is not None:
                    row_data[normalize_name(col)] = value

            if row_data:
                info["sample_rows"].append(row_data)

        preview.append(info)

    return preview
