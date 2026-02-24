from domains.indicators.models.Component.component_indicator_target import ComponentIndicatorTarget
from domains.indicators.models.Component.component import Component
from domains.indicators.models.Component.component_indicator import ComponentIndicator
from domains.indicators.models.Strategy.strategy import Strategy


class ReportValidator:

    @staticmethod
    def validate_create(data):

        errors = {}

        # ---------------------
        # Basic fields
        # ---------------------
        if not data.get("report_date"):
            errors["report_date"] = "Report date required"

        if not data.get("executive_summary"):
            errors["executive_summary"] = "Executive summary required"

        if not data.get("activities_performed"):
            errors["activities_performed"] = "Activities required"

        if data.get("zone_type") not in ["Urbana", "Rural"]:
            errors["zone_type"] = "Invalid zone type"

        # ---------------------
        # Strategy & Component
        # ---------------------
        strategy = Strategy.query.get(data.get("strategy_id"))
        if not strategy:
            errors["strategy_id"] = "Strategy does not exist"

        component = Component.query.get(data.get("component_id"))
        if not component:
            errors["component_id"] = "Component does not exist"
        elif component.strategy_id != data.get("strategy_id"):
            errors["component_id"] = "Component does not belong to strategy"

        indicator_values = data.get("indicator_values")
        if not indicator_values:
            errors["indicator_values"] = "Indicators required"
            return errors

        component_indicators = ComponentIndicator.query.filter_by(
            component_id=data.get("component_id")
        ).all()

        indicator_map     = {ind.id: ind   for ind in component_indicators}
        indicator_by_name = {ind.name: ind for ind in component_indicators}

        indicator_errors = []

        # ---------------------
        # Extract year from report_date
        # ---------------------
        report_date = data.get("report_date")
        report_year = report_date.year if report_date else None

        # Mapa de valores por nombre (para grouped_data / categorized_group)
        values_by_name = {}
        for value in indicator_values:
            indicator = indicator_map.get(value.get("indicator_id"))
            if indicator:
                values_by_name[indicator.name] = value.get("value")

        for value in indicator_values:

            indicator = indicator_map.get(value.get("indicator_id"))

            if not indicator:
                indicator_errors.append("Invalid indicator_id")
                continue

            field_type = indicator.field_type
            val        = value.get("value")

            if val is None:
                if indicator.is_required:
                    indicator_errors.append(
                        f"'{indicator.name}' is required and cannot be null"
                    )
                continue

            # ========================================
            # TYPE VALIDATION
            # ========================================

            # NUMBER
            if field_type == "number":
                if not isinstance(val, (int, float)):
                    indicator_errors.append(
                        f"Number expected for indicator '{indicator.name}'"
                    )
                    continue

                target = ComponentIndicatorTarget.query.filter_by(
                    indicator_id=indicator.id,
                    year=report_year
                ).first()

                if not target:
                    indicator_errors.append(
                        f"No target defined for indicator '{indicator.name}' in year {report_year}"
                    )

            # TEXT
            elif field_type == "text":
                if not isinstance(val, str):
                    indicator_errors.append(
                        f"Text expected for indicator '{indicator.name}'"
                    )

            # SELECT
            elif field_type == "select":
                options = indicator.config.get("options", []) if indicator.config else []
                if val not in options:
                    indicator_errors.append(
                        f"Invalid option selected for indicator '{indicator.name}'. "
                        f"Valid options: {options}"
                    )

            # MULTI_SELECT
            elif field_type == "multi_select":
                error = ReportValidator._validate_multi_select_value(indicator, val)
                if error:
                    indicator_errors.append(error)

            # SUM_GROUP
            elif field_type == "sum_group":
                if not isinstance(val, dict):
                    indicator_errors.append(
                        f"Dictionary expected for indicator '{indicator.name}'"
                    )
                    continue

                fields = indicator.config.get("fields", []) if indicator.config else []

                for field_def in fields:
                    field_name = field_def.get("name") if isinstance(field_def, dict) else field_def
                    if not field_name:
                        continue
                    if field_name not in val:
                        indicator_errors.append(
                            f"Missing field '{field_name}' in sum_group '{indicator.name}'"
                        )
                    elif not isinstance(val[field_name], (int, float)):
                        indicator_errors.append(
                            f"Field '{field_name}' must be a number in '{indicator.name}'"
                        )

            # GROUPED_DATA
            elif field_type == "grouped_data":
                error = ReportValidator._validate_grouped_data_value(
                    indicator, val, values_by_name
                )
                if error:
                    indicator_errors.append(error)

            # CATEGORIZED_GROUP
            elif field_type == "categorized_group":
                error = ReportValidator._validate_categorized_group_value(indicator, val)
                if error:
                    indicator_errors.append(error)

        if indicator_errors:
            errors["indicator_values"] = indicator_errors

        return errors

    # =============================================
    # VALIDADORES ESPECÍFICOS PARA VALORES
    # =============================================

    @staticmethod
    def _validate_multi_select_value(indicator, value):
        if not isinstance(value, list):
            return f"Multi-select '{indicator.name}' must be a list"

        if indicator.is_required and len(value) == 0:
            return f"Multi-select '{indicator.name}' cannot be empty (required)"

        options = indicator.config.get("options", []) if indicator.config else []

        for selected in value:
            if selected not in options:
                return (
                    f"Invalid option '{selected}' in multi-select '{indicator.name}'. "
                    f"Valid options: {options}"
                )

        return None

    @staticmethod
    def _validate_grouped_data_value(indicator, value, all_values):
        if not isinstance(value, dict):
            return f"Grouped data '{indicator.name}' must be an object/dict"

        config = indicator.config
        if not config:
            return f"Grouped data '{indicator.name}' has no config"

        parent_field_name = config.get("parent_field")
        sub_fields        = config.get("sub_fields", [])
        parent_value      = all_values.get(parent_field_name)

        if parent_value is None:
            return (
                f"Grouped data '{indicator.name}' requires parent field "
                f"'{parent_field_name}' to have a value"
            )

        if not isinstance(parent_value, list):
            return (
                f"Parent field '{parent_field_name}' for '{indicator.name}' must be a list"
            )

        for selected_option in parent_value:
            if selected_option not in value:
                return (
                    f"Grouped data '{indicator.name}' is missing data for '{selected_option}'"
                )

            group_data = value[selected_option]
            if not isinstance(group_data, dict):
                return f"Data for '{selected_option}' in '{indicator.name}' must be an object"

            for sub_field in sub_fields:
                field_name = sub_field.get("name") if isinstance(sub_field, dict) else sub_field
                field_type = sub_field.get("type") if isinstance(sub_field, dict) else None
                if not field_name:
                    continue
                if field_name not in group_data:
                    return (
                        f"Missing field '{field_name}' for '{selected_option}' "
                        f"in '{indicator.name}'"
                    )
                field_value = group_data[field_name]
                if field_type == "number" and not isinstance(field_value, (int, float)):
                    return (
                        f"Field '{field_name}' for '{selected_option}' must be a number "
                        f"in '{indicator.name}'"
                    )
                elif field_type == "text" and not isinstance(field_value, str):
                    return (
                        f"Field '{field_name}' for '{selected_option}' must be text "
                        f"in '{indicator.name}'"
                    )

        for key in value.keys():
            if key not in parent_value:
                return (
                    f"Unexpected data for '{key}' in '{indicator.name}' "
                    f"(not selected in '{parent_field_name}')"
                )

        return None

    @staticmethod
    def _validate_categorized_group_value(indicator, value):
        """
        Valida el valor reportado de un indicador tipo categorized_group.

        Estructura esperada:
        {
            "selected_categories": ["Canino", "Felino"],
            "data": {
                "Canino": {
                    "Hembra": { "vacunados": 3, "desparasitados": 0 },
                    "Macho":  { "vacunados": 1, "desparasitados": 2 }
                },
                ...
            },
            "sub_sections": {
                "red_animalia": {
                    "Canino": { "vacunados": 2, "desparasitados": 1 },
                    "Felino": { "vacunados": 0, "desparasitados": 3 }
                }
            }
        }

        Regla de sub_sections con max_source = "metrics_total":
            sub_sections[section_key][category][metric_key]
                <= sum(data[category][group][metric_key] for all groups)
        """
        name   = indicator.name
        config = indicator.config or {}

        allowed_categories = set(config.get("categories", []))
        allowed_groups     = set(config.get("groups", []))
        metric_keys        = {m["key"] for m in config.get("metrics", [])}
        sub_sections_cfg   = {s["key"]: s for s in config.get("sub_sections", [])}

        if not isinstance(value, dict):
            return f"Categorized group '{name}' must be an object"

        selected_categories = value.get("selected_categories", [])
        data                = value.get("data", {})
        sub_sections        = value.get("sub_sections", {})

        # selected_categories
        if not isinstance(selected_categories, list):
            return f"'{name}': selected_categories must be a list"

        if indicator.is_required and len(selected_categories) == 0:
            return f"'{name}': at least one category must be selected"

        invalid_cats = set(selected_categories) - allowed_categories
        if invalid_cats:
            return f"'{name}': invalid categories: {invalid_cats}"

        # data
        if not isinstance(data, dict):
            return f"'{name}': data must be an object"

        # Calcular total por (categoría, métrica) — necesario para validar sub_sections
        # category_metric_totals[cat][metric_key] = suma de todos los grupos
        category_metric_totals: dict[str, dict[str, float]] = {}

        for cat in selected_categories:
            if cat not in data:
                return f"'{name}': missing data for selected category '{cat}'"

            cat_data = data[cat]
            if not isinstance(cat_data, dict):
                return f"'{name}': data for category '{cat}' must be an object"

            category_metric_totals[cat] = {key: 0.0 for key in metric_keys}

            for group, metrics in cat_data.items():
                if group not in allowed_groups:
                    return f"'{name}': invalid group '{group}' in category '{cat}'"

                if not isinstance(metrics, dict):
                    return f"'{name}': data for group '{group}' in '{cat}' must be an object"

                for key in metric_keys:
                    val = metrics.get(key, 0)
                    if not isinstance(val, (int, float)) or val < 0:
                        return (
                            f"'{name}': metric '{key}' for '{cat}/{group}' "
                            f"must be a number >= 0"
                        )
                    category_metric_totals[cat][key] += val

        # Categorías en data que no están en selected_categories
        for cat in data:
            if cat not in selected_categories:
                return f"'{name}': data contains category '{cat}' that was not selected"

        # sub_sections: sub_sections[section_key][category][metric_key]
        if not isinstance(sub_sections, dict):
            return f"'{name}': sub_sections must be an object"

        for section_key, section_cfg in sub_sections_cfg.items():
            if section_cfg.get("max_source") != "metrics_total":
                continue

            section_data = sub_sections.get(section_key, {})

            for cat in selected_categories:
                cat_values = section_data.get(cat, {})
                cat_totals = category_metric_totals.get(cat, {})

                for metric_key in metric_keys:
                    sec_val = cat_values.get(metric_key, 0)
                    total   = cat_totals.get(metric_key, 0)

                    if not isinstance(sec_val, (int, float)) or sec_val < 0:
                        return (
                            f"'{name}': sub_section '{section_key}' value for "
                            f"'{cat}/{metric_key}' must be a number >= 0"
                        )

                    if sec_val > total:
                        return (
                            f"'{name}': sub_section '{section_key}' value for "
                            f"'{cat}/{metric_key}' ({sec_val}) cannot exceed "
                            f"the reported total for that category ({total})"
                        )

        return None