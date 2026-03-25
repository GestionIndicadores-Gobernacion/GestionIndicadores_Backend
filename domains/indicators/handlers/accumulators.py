from collections import defaultdict


def make_accumulator():
    return defaultdict(lambda: {
        "name": None,
        "field_type": None,
        "by_month": defaultdict(float),
        "by_category": defaultdict(float),
        "by_nested": defaultdict(lambda: defaultdict(float)),
    })


def process_indicator_value(
    iv, indicator, r, month_key,
    accumulator, location_indicator, location_nested,
    actor_location_acc, report_value_map, dataset_record_map
):
    report_value_map[r.id][iv.indicator_id] = iv.value

    acc = accumulator[iv.indicator_id]
    acc["name"] = indicator.name
    acc["field_type"] = indicator.field_type
    value = iv.value

    if indicator.field_type == "number":
        _process_number(iv, r, value, month_key, acc, location_indicator)

    elif indicator.field_type == "sum_group":
        _process_sum_group(value, month_key, acc)

    elif indicator.field_type in ("select", "multi_select"):
        _process_select(value, month_key, acc)

    elif indicator.field_type == "categorized_group":
        _process_categorized_group(iv, r, value, month_key, acc, location_nested)

    elif indicator.field_type == "grouped_data":
        _process_grouped_data(value, month_key, acc)

    elif indicator.field_type == "dataset_select":
        _process_dataset_select(iv, r, value, month_key, acc, actor_location_acc, indicator, dataset_record_map)

    elif indicator.field_type == "dataset_multi_select":
        _process_dataset_multi_select(iv, r, value, month_key, acc, actor_location_acc, indicator, dataset_record_map)


# ── Handlers por field_type ──────────────────────────────────────────────────

def _process_number(iv, r, value, month_key, acc, location_indicator):
    if isinstance(value, (int, float)):
        acc["by_month"][month_key] += value
        if r.intervention_location:
            location_indicator[r.intervention_location][iv.indicator_id] += value


def _process_sum_group(value, month_key, acc):
    if isinstance(value, dict):
        month_total = sum(v for v in value.values() if isinstance(v, (int, float)))
        acc["by_month"][month_key] += month_total
        for category, total in value.items():
            if isinstance(total, (int, float)):
                acc["by_category"][category] += total


def _process_select(value, month_key, acc):
    if isinstance(value, str):
        acc["by_category"][value] += 1
        acc["by_month"][month_key] += 1
    elif isinstance(value, list):
        for option in value:
            if isinstance(option, str):
                acc["by_category"][option] += 1
        acc["by_month"][month_key] += 1


def _process_categorized_group(iv, r, value, month_key, acc, location_nested):
    if not isinstance(value, dict):
        return

    data = value.get("data", {})
    metric_totals: dict[str, float] = defaultdict(float)

    for category, genders in data.items():
        if not isinstance(genders, dict):
            continue
        for gender, metrics in genders.items():
            gender_clean = gender.strip().rstrip(',')
            if not isinstance(metrics, dict):
                continue
            for metric, val in metrics.items():
                if isinstance(val, (int, float)):
                    acc["by_nested"][category][metric] += val
                    acc["by_nested"][f"{category} – {gender_clean}"][metric] += val
                    metric_totals[metric] += val

                    if r.intervention_location:
                        location_nested[r.intervention_location][iv.indicator_id][metric] += val

    # ── FIX: sumar TODAS las métricas, no solo la principal ──────────────
    if metric_totals:
        month_total = 0.0
        for category, genders in data.items():
            if not isinstance(genders, dict):
                continue
            for gender, metrics in genders.items():
                if not isinstance(metrics, dict):
                    continue
                for metric, val in metrics.items():
                    if isinstance(val, (int, float)):
                        month_total += val

        # Cada animal aparece en Hembra + Macho → ya están separados,
        # no hay doble conteo porque iteramos sobre los sexos directamente
        acc["by_month"][month_key] += month_total

    # Sub sections (sin cambios)
    sub = value.get("sub_sections", {})
    if isinstance(sub, dict):
        for section, section_data in sub.items():
            if isinstance(section_data, dict):
                if "actors" in section_data:
                    for actor in section_data["actors"]:
                        metrics = actor.get("metrics", {})
                        if isinstance(metrics, dict):
                            for metric, val in metrics.items():
                                if isinstance(val, (int, float)):
                                    acc["by_nested"][f"sub:{section}"][metric] += val
                else:
                    for metric, val in section_data.items():
                        if isinstance(val, (int, float)):
                            acc["by_nested"][f"sub:{section}"][metric] += val

def _process_grouped_data(value, month_key, acc):
    if isinstance(value, dict):
        month_total = sum(v for v in value.values() if isinstance(v, (int, float)))
        acc["by_month"][month_key] += month_total
        for group, val in value.items():
            if isinstance(val, (int, float)):
                acc["by_category"][group] += val


def _process_dataset_select(iv, r, value, month_key, acc, actor_location_acc, indicator, dataset_record_map):
    if isinstance(value, int):
        cfg = indicator.config or {}
        dataset_id = cfg.get("dataset_id")
        label_field = cfg.get("label_field")  # ← leer label_field del config
        record_data = dataset_record_map.get(dataset_id, {}).get(value, {})
        label = (
            (record_data.get(label_field) if label_field else None)
            or record_data.get("nombre_hogar_de_paso_albergue_o_refugio_fundacion")
            or record_data.get("nombres_y_apellidos")
            or record_data.get("nombre")
            or str(value)
        )
        acc["by_category"][label] += 1
        acc["by_month"][month_key] += 1
        if r.intervention_location:
            actor_location_acc[iv.indicator_id][r.intervention_location][label] += 1


def _process_dataset_multi_select(iv, r, value, month_key, acc, actor_location_acc, indicator, dataset_record_map):
    if isinstance(value, list):
        cfg = indicator.config or {}
        dataset_id = cfg.get("dataset_id")
        label_field = cfg.get("label_field")  # ← leer label_field del config
        record_lookup = dataset_record_map.get(dataset_id, {})
        for record_id in value:
            if not isinstance(record_id, int):
                continue
            record_data = record_lookup.get(record_id, {})
            label = (
                (record_data.get(label_field) if label_field else None)
                or record_data.get("nombre_hogar_de_paso_albergue_o_refugio_fundacion")
                or record_data.get("nombres_y_apellidos")
                or record_data.get("nombre")
                or str(record_id)
            )
            acc["by_category"][label] += 1
            if r.intervention_location:
                actor_location_acc[iv.indicator_id][r.intervention_location][label] += 1
        acc["by_month"][month_key] += 1