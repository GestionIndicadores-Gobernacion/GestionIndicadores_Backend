import re

COLORS = [
    "#2563EB",  # blue
    "#0891B2",  # cyan
    "#059669",  # emerald
    "#7C3AED",  # violet
    "#DB2777",  # pink
    "#D97706",  # amber
    "#DC2626",  # red
    "#0D9488",  # teal
]


def norm(val) -> str:
    if val is None: return ""
    return str(val).strip().lower()


def is_yes(val) -> bool:
    return norm(val) in ("si", "sí", "yes", "1", "1.0", "true", "x")


def is_no(val) -> bool:
    return norm(val) in ("no", "0", "0.0", "false")


def fill_rate(values, total) -> float:
    filled = sum(1 for v in values if v is not None and str(v).strip())
    return round((filled / total) * 100, 1) if total else 0.0


def unique_clean(values) -> set:
    return set(norm(v) for v in values if v is not None and str(v).strip())


def group_similar(values, top_n=12, normalize_first_word=False):
    normalized = {}
    for v in values:
        if v is None: continue
        raw = str(v).strip()
        if not raw: continue
        if normalize_first_word:
            words = raw.lower().split()
            key = words[0] if words else raw.lower()
            display = key.capitalize()
        else:
            key = raw.lower()
            display = raw
        if key not in normalized:
            normalized[key] = [display, 0]
        normalized[key][1] += 1
    entries = sorted(normalized.values(), key=lambda x: -x[1])
    return [(label, count) for label, count in entries[:top_n]]


def make_bars(grouped, total):
    return [
        {
            "label": label,
            "value": count,
            "pct": round((count / total) * 100, 1),
            "color": COLORS[i % len(COLORS)]
        }
        for i, (label, count) in enumerate(grouped) if count > 0
    ]


def bar_section(field, values, total, subtitle=""):
    grouped = group_similar(values, top_n=12)
    bars = make_bars(grouped, total)
    if not bars: return None
    n_unique = len(unique_clean(values))
    return {
        "id": field.name,
        "title": field.label.strip(),
        "subtitle": subtitle or f"{n_unique} valores únicos",
        "type": "bar",
        "bars": bars,
    }


def numeric_stats(values):
    try:
        nums = sorted(float(v) for v in values if v is not None)
    except Exception:
        return {}
    if not nums: return {}
    n = len(nums)
    mid = n // 2
    median = (nums[mid - 1] + nums[mid]) / 2 if n % 2 == 0 else nums[mid]
    s = sum(nums)
    return {
        "min": round(min(nums), 2), "max": round(max(nums), 2),
        "avg": round(s / n, 2), "median": round(median, 2),
        "total": round(s, 2), "count": n
    }


def numeric_bins(values, buckets=8):
    try:
        nums = [float(v) for v in values if v is not None]
    except Exception:
        return []
    if not nums: return []
    mn, mx = min(nums), max(nums)
    step = (mx - mn) / buckets or 1
    bins = [{"label": f"{mn + i * step:.0f}–{mn + (i + 1) * step:.0f}", "value": 0} for i in range(buckets)]
    for v in nums:
        idx = min(int((v - mn) / step), buckets - 1)
        bins[idx]["value"] += 1
    t = len(nums) or 1
    return [
        {**b, "pct": round(b["value"] / t * 100, 1), "color": COLORS[i % len(COLORS)]}
        for i, b in enumerate(bins) if b["value"] > 0
    ]