import re
import pandas as pd
import numpy as np

MAX_FIELD_NAME_LENGTH = 100
MAX_TABLE_NAME_LENGTH = 50


def normalize_name(value: str, max_len=MAX_FIELD_NAME_LENGTH) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[^\w\s]", "", value)
    value = re.sub(r"\s+", "_", value)
    return value[:max_len] or "field"


def normalize_value(value):
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, (np.integer, np.floating)):
        return value.item()

    if isinstance(value, str):
        value = value.strip()
        return value if value else None

    return value
