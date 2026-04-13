def serialize_indicators(accumulator, all_months):
    result = []
    for indicator_id, acc in accumulator.items():
        field_type = acc["field_type"]
        entry = {
            "indicator_id": indicator_id,
            "indicator_name": acc["name"],
            "field_type": field_type,
        }

        if field_type == "number":
            entry["by_month"] = [
                {"month": m, "total": acc["by_month"].get(m, 0)}
                for m in all_months
            ]

        elif field_type in ("sum_group", "grouped_data", "select", "multi_select",
                            "dataset_select", "dataset_multi_select"):
            entry["by_category"] = [
                {"category": cat, "total": round(total, 2)}
                for cat, total in sorted(acc["by_category"].items(), key=lambda x: -x[1])
            ]
            entry["by_month"] = [
                {"month": m, "total": acc["by_month"].get(m, 0)}
                for m in all_months
            ]

        elif field_type == "categorized_group":
            entry["by_nested"] = {
                category: [
                    {"metric": metric, "total": round(total, 2)}
                    for metric, total in metrics.items()
                ]
                for category, metrics in acc["by_nested"].items()
            }
            entry["by_month"] = [
                {"month": m, "total": acc["by_month"].get(m, 0)}
                for m in all_months
            ]

        result.append(entry)
    return result


def serialize_by_location(location_counts):
    return [
        {"location": loc, "total": count}
        for loc, count in sorted(location_counts.items(), key=lambda x: -x[1])
    ]


def serialize_by_location_indicator(location_indicator):
    return [
        {
            "location": loc,
            "indicators": [
                {"indicator_id": ind_id, "total": round(total, 2)}
                for ind_id, total in indicators.items()
            ]
        }
        for loc, indicators in sorted(location_indicator.items())
    ]


def serialize_by_location_nested(location_nested):
    return [
        {
            "location": loc,
            "indicators": [
                {
                    "indicator_id": ind_id,
                    "metrics": [
                        {"metric": metric, "total": round(total, 2)}
                        for metric, total in metrics.items()
                    ]
                }
                for ind_id, metrics in indicators.items()
            ]
        }
        for loc, indicators in sorted(location_nested.items())
    ]


def serialize_by_actor_location(actor_location_acc, accumulator):
    result = []
    for indicator_id, locations in actor_location_acc.items():
        ind_name = accumulator[indicator_id]["name"] if indicator_id in accumulator else str(indicator_id)
        result.append({
            "indicator_id": indicator_id,
            "indicator_name": ind_name,
            "by_location": [
                {
                    "location": loc,
                    "actors": [
                        {"actor": actor, "count": count}
                        for actor, count in sorted(actors.items(), key=lambda x: -x[1])
                    ]
                }
                for loc, actors in sorted(locations.items())
            ]
        })
    return result