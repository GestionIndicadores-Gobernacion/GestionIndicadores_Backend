from app.modules.indicators.models.Component.component_indicator_target import ComponentIndicatorTarget
from app.modules.indicators.models.Component.component import Component
from app.modules.indicators.models.Component.component_indicator import ComponentIndicator
from app.modules.indicators.models.Report.report import Report
from app.modules.indicators.models.Strategy.strategy import Strategy


class ReportValidator:

    @staticmethod
    def validate_create(data, current_report_id=None):

        errors = {}

        # ---------------------
        # Basic fields
        # ---------------------
        if not data.get("report_date"):
            errors["report_date"] = "Report date required"

        if not data.get("executive_summary"):
            errors["executive_summary"] = "Executive summary required"

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

        # Mapa de valores por nombre (para grouped_data / categorized_group / show_if)
        values_by_name = {}
        for value in indicator_values:
            indicator = indicator_map.get(value.get("indicator_id"))
            if indicator:
                values_by_name[indicator.name] = value.get("value")

        # ── GRUPOS MUTUAMENTE EXCLUYENTES ───────────────────────────────────────
        from collections import defaultdict
        groups_in_component = defaultdict(list)
        for ind in component_indicators:
            if ind.group_name:
                groups_in_component[ind.group_name].append(ind)

        submitted_ids = {v.get("indicator_id") for v in indicator_values}

        for gname, members in groups_in_component.items():
            if any(m.group_required for m in members):
                submitted_in_group = [m for m in members if m.id in submitted_ids]
                if not submitted_in_group:
                    names = " / ".join(m.name for m in members)
                    errors[f"group_{gname}"] = (
                        f"At least one of the following indicators must be reported: {names}"
                    )

        grouped_indicator_ids = {
            m.id
            for members in groups_in_component.values()
            for m in members
        }
        # ────────────────────────────────────────────────────────────────────────

        for value in indicator_values:

            indicator = indicator_map.get(value.get("indicator_id"))

            if not indicator:
                indicator_errors.append("Invalid indicator_id")
                continue

            field_type = indicator.field_type
            val        = value.get("value")

            if val is None:
                in_group    = indicator.id in grouped_indicator_ids
                show_if_active = ReportValidator._show_if_is_active(indicator, values_by_name)

                # Si show_if no se cumple → el indicador no aplica en este reporte
                if not show_if_active:
                    continue

                if indicator.is_required and not in_group:
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

                min_value = (indicator.config or {}).get("min_value")
                if min_value is not None and val < min_value:
                    indicator_errors.append(
                        f"'{indicator.name}' must be greater than or equal to {min_value}"
                    )

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

            # DATE
            elif field_type == "date":
                if not isinstance(val, str):
                    indicator_errors.append(
                        f"Date expected for indicator '{indicator.name}'"
                    )
                else:
                    import re
                    if not re.match(r'^\d{4}-\d{2}-\d{2}$', val):
                        indicator_errors.append(
                            f"'{indicator.name}': date must be in format YYYY-MM-DD"
                        )

            # CATEGORIZED_GROUP
            elif field_type == "categorized_group":
                error = ReportValidator._validate_categorized_group_value(indicator, val)
                if error:
                    indicator_errors.append(error)

            # DATASET_SELECT
            elif field_type == "dataset_select":
                # Si show_if no se cumple, ignorar aunque venga en el payload
                if not ReportValidator._show_if_is_active(indicator, values_by_name):
                    continue
                error = ReportValidator._validate_dataset_select_value(indicator, val)
                if error:
                    indicator_errors.append(error)

            # DATASET_MULTI_SELECT
            elif field_type == "dataset_multi_select":
                if not ReportValidator._show_if_is_active(indicator, values_by_name):
                    continue
                error = ReportValidator._validate_dataset_multi_select_value(indicator, val)
                if error:
                    indicator_errors.append(error)

        # ── Verificar dataset_select con show_if activo que son required
        # pero no vinieron en el payload en absoluto ──────────────────────────
        for ind in component_indicators:
            if ind.field_type not in ("dataset_select", "dataset_multi_select"):
                continue
            if not ind.is_required:
                continue
            cfg     = ind.config or {}
            show_if = cfg.get("show_if")
            if not show_if:
                continue
            if not ReportValidator._show_if_is_active(ind, values_by_name):
                continue
            # show_if activo + required → debe estar en el payload
            was_submitted = any(v.get("indicator_id") == ind.id for v in indicator_values)
            if not was_submitted:
                indicator_errors.append(
                    f"'{ind.name}' is required when "
                    f"'{show_if['indicator_name']}' = '{show_if['value']}'"
                )

        if indicator_errors:
            errors["indicator_values"] = indicator_errors
            
        # ── Validación evidence_link duplicado ──────────────────────────────
        evidence_link = (data.get("evidence_link") or "").strip()
        if evidence_link:
            existing = Report.query.filter(
                Report.evidence_link == evidence_link
            ).first()
            if existing and existing.id != current_report_id:
                errors["evidence_link"] = (
                    f"Ya existe un reporte con este link de evidencia (reporte #{existing.id}). "
                    "Si deseas asociar esta actividad a ese reporte, usa el endpoint de vinculación."
                )

        if indicator_errors:
            errors["indicator_values"] = indicator_errors

        return errors

    # =============================================
    # HELPER: evaluar show_if
    # =============================================

    @staticmethod
    def _show_if_is_active(indicator, values_by_name: dict) -> bool:
        """
        Retorna True si el indicador debe aplicarse según su show_if.
        Sin show_if → siempre True (comportamiento normal).

        show_if: {"indicator_name": "¿PERTENECE A LA RED ANIMALIA?", "value": "SI"}
        """
        config  = indicator.config or {}
        show_if = config.get("show_if")

        if not show_if:
            return True

        parent_name    = show_if.get("indicator_name")
        required_value = show_if.get("value")
        actual_value   = values_by_name.get(parent_name)

        # Soporte para padre de tipo multi_select
        if isinstance(actual_value, list):
            return required_value in actual_value

        return actual_value == required_value

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

        if not isinstance(selected_categories, list):
            return f"'{name}': selected_categories must be a list"

        if indicator.is_required and len(selected_categories) == 0:
            return f"'{name}': at least one category must be selected"

        invalid_cats = set(selected_categories) - allowed_categories
        if invalid_cats:
            return f"'{name}': invalid categories: {invalid_cats}"

        if not isinstance(data, dict):
            return f"'{name}': data must be an object"

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

        for cat in data:
            if cat not in selected_categories:
                return f"'{name}': data contains category '{cat}' that was not selected"

        if not isinstance(sub_sections, dict):
            return f"'{name}': sub_sections must be an object"
            
        for section_key, section_cfg in sub_sections_cfg.items():
            
            if section_key == 'red_animalia':
                continue
            
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
    
    @staticmethod
    def _validate_dataset_select_value(indicator, value):
        from app.modules.datasets.models.record import Record

        config     = indicator.config or {}
        dataset_id = config.get("dataset_id")

        if not dataset_id:
            return f"'{indicator.name}': config must include 'dataset_id'"

        if not isinstance(value, int):
            return f"'{indicator.name}': dataset_select value must be a record ID (integer)"

        from app.modules.datasets.models.table import Table
        valid_table_ids = [t.id for t in Table.query.filter_by(dataset_id=dataset_id).all()]
        if not valid_table_ids:
            return f"'{indicator.name}': dataset {dataset_id} has no tables"

        record = Record.query.filter(
            Record.id == value,
            Record.table_id.in_(valid_table_ids)
        ).first()

        if not record:
            return f"'{indicator.name}': record {value} does not exist in dataset {dataset_id}"

        return None

    @staticmethod
    def _validate_dataset_multi_select_value(indicator, value):
        from app.modules.datasets.models.record import Record
        from app.modules.datasets.models.table import Table

        config     = indicator.config or {}
        dataset_id = config.get("dataset_id")

        if not dataset_id:
            return f"'{indicator.name}': config must include 'dataset_id'"

        if not isinstance(value, list):
            return f"'{indicator.name}': dataset_multi_select must be a list of record IDs"

        if indicator.is_required and len(value) == 0:
            return f"'{indicator.name}': dataset_multi_select cannot be empty (required)"

        valid_table_ids = [t.id for t in Table.query.filter_by(dataset_id=dataset_id).all()]
        if not valid_table_ids:
            return f"'{indicator.name}': dataset {dataset_id} has no tables"

        existing_ids = {
            r.id for r in Record.query.filter(
                Record.id.in_(value),
                Record.table_id.in_(valid_table_ids)
            ).all()
        }
        invalid = set(value) - existing_ids
        if invalid:
            return f"'{indicator.name}': records {invalid} do not exist in dataset {dataset_id}"

        return None