import re
import unicodedata
import pandas as pd
import numpy as np

MAX_FIELD_NAME_LENGTH = 100
MAX_TABLE_NAME_LENGTH = 50

def normalize_name(value: str, max_len=MAX_FIELD_NAME_LENGTH) -> str:
    value = str(value).strip().lower()

    # quitar acentos
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")

    # eliminar caracteres raros
    value = re.sub(r"[^a-z0-9\s]", "", value)

    # espacios -> _
    value = re.sub(r"\s+", "_", value)

    value = value.strip("_")

    if not value:
        value = "field"

    return value[:max_len]

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
