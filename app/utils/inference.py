import pandas as pd


def infer_field_type(series: pd.Series) -> str:
    s = series.dropna()

    if s.empty:
        return "text"

    if pd.api.types.is_bool_dtype(s):
        return "boolean"

    if pd.api.types.is_numeric_dtype(s):
        return "number"

    if pd.api.types.is_datetime64_any_dtype(s):
        return "date"

    return "text"
