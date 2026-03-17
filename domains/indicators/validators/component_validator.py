from domains.indicators.models.Component.component import Component
from domains.indicators.models.Strategy.strategy import Strategy


class ComponentValidator:
    """
    Validador para componentes e indicadores.
    """

    VALID_FIELD_TYPES = {
        "number",
        "text",
        "select",
        "multi_select",
        "sum_group",
        "grouped_data",
        "file_attachment",
        "categorized_group", 
        "dataset_select",       
        "dataset_multi_select",
        "group_name",
        "red_animalia"
    }

    # Tipos que requieren targets OBLIGATORIOS
    REQUIRED_TARGET_TYPES = {"number", "sum_group", "categorized_group"}

    # Tipos que pueden tener targets OPCIONALES
    OPTIONAL_TARGET_TYPES = {"grouped_data"}

    # Tipos que NO aceptan targets
    NO_TARGET_TYPES = {"text", "select", "multi_select", "file_attachment",
                   "dataset_select", "dataset_multi_select", "red_animalia"}

    @staticmethod
    def validate_create(data, component_id=None):
        errors = {}

        # =============================================
        # VALIDACIONES BÁSICAS
        # =============================================

        strategy = Strategy.query.get(data.get("strategy_id"))
        if not strategy:
            errors["strategy_id"] = "Strategy does not exist"

        if not data.get("name"):
            errors["name"] = "Component name is required"

        exists = Component.query.filter_by(
            strategy_id=data.get("strategy_id"),
            name=data.get("name")
        ).first()

        if exists and exists.id != component_id:
            errors["name"] = "Component already exists in this strategy"

        objectives = data.get("objectives")
        if not objectives:
            errors["objectives"] = "At least one objective is required"

        mga = data.get("mga_activities")
        if not mga:
            errors["mga_activities"] = "At least one MGA activity is required"

        # =============================================
        # VALIDACIONES DE INDICADORES
        # =============================================

        indicators = data.get("indicators")
        if not indicators:
            errors["indicators"] = "At least one indicator is required"
            return errors

        indicator_map = {ind.get("name"): ind for ind in indicators}
        names = set()

        for ind in indicators:

            if ind.get("name") in names:
                errors["indicators"] = "Indicator names cannot repeat"
                break
            names.add(ind.get("name"))

            field_type = ind.get("field_type")
            if field_type not in ComponentValidator.VALID_FIELD_TYPES:
                errors["indicators"] = f"Invalid field_type: '{field_type}'"
                break

            if field_type == "select":
                error = ComponentValidator._validate_select(ind)
                if error:
                    errors["indicators"] = error
                    break

            if field_type == "multi_select":
                error = ComponentValidator._validate_multi_select(ind)
                if error:
                    errors["indicators"] = error
                    break

            if field_type == "sum_group":
                error = ComponentValidator._validate_sum_group(ind)
                if error:
                    errors["indicators"] = error
                    break

            if field_type == "grouped_data":
                error = ComponentValidator._validate_grouped_data(ind, indicator_map)
                if error:
                    errors["indicators"] = error
                    break

            if field_type == "file_attachment":
                error = ComponentValidator._validate_file_attachment(ind)
                if error:
                    errors["indicators"] = error
                    break

            if field_type == "categorized_group":
                error = ComponentValidator._validate_categorized_group(ind)
                if error:
                    errors["indicators"] = error
                    break
                
            if field_type in ("dataset_select", "dataset_multi_select"):
                error = ComponentValidator._validate_dataset_select(ind)
                if error:
                    errors["indicators"] = error
                    break
                
            if field_type == "red_animalia":
                error = ComponentValidator._validate_red_animalia(ind)
                if error:
                    errors["indicators"] = error
                    break

            if field_type in ComponentValidator.REQUIRED_TARGET_TYPES:
                error = ComponentValidator._validate_targets(ind, required=True)
                if error:
                    errors["indicators"] = error
                    break

            elif field_type in ComponentValidator.OPTIONAL_TARGET_TYPES:
                targets = ind.get("targets")
                if targets and len(targets) > 0:
                    error = ComponentValidator._validate_targets(ind, required=False)
                    if error:
                        errors["indicators"] = error
                        break

        group_error = ComponentValidator._validate_groups(indicators)
        if group_error:
            errors["indicators"] = group_error

        return errors                         

    # =============================================
    # VALIDADORES ESPECÍFICOS POR TIPO
    # =============================================

    @staticmethod
    def _validate_select(indicator):
        config = indicator.get("config")

        if not config or not config.get("options"):
            return "Select indicators require 'options' in config"

        if not isinstance(config["options"], list):
            return "Select 'options' must be a list"

        if len(config["options"]) == 0:
            return "Select 'options' cannot be empty"

        return None

    @staticmethod
    def _validate_multi_select(indicator):
        config = indicator.get("config")

        if not config or not config.get("options"):
            return "Multi-select indicators require 'options' in config"

        if not isinstance(config["options"], list):
            return "Multi-select 'options' must be a list"

        if len(config["options"]) == 0:
            return "Multi-select 'options' cannot be empty"

        return None

    @staticmethod
    def _validate_sum_group(indicator):
        config = indicator.get("config")

        if not config or not config.get("fields"):
            return "Sum_group indicators require 'fields' in config"

        if not isinstance(config["fields"], list):
            return "Sum_group 'fields' must be a list"

        if len(config["fields"]) == 0:
            return "Sum_group 'fields' cannot be empty"

        return None

    @staticmethod
    def _validate_grouped_data(indicator, all_indicators):
        config = indicator.get("config")

        if not config:
            return f"Indicator '{indicator.get('name')}': grouped_data requires 'config'"

        parent_field_name = config.get("parent_field")

        if not parent_field_name:
            return f"Indicator '{indicator.get('name')}': grouped_data requires 'parent_field' in config"

        parent_indicator = all_indicators.get(parent_field_name)

        if not parent_indicator:
            return f"Indicator '{indicator.get('name')}': parent field '{parent_field_name}' does not exist"

        if parent_indicator.get("field_type") != "multi_select":
            return f"Indicator '{indicator.get('name')}': parent field '{parent_field_name}' must be type 'multi_select'"

        sub_fields = config.get("sub_fields")

        if not sub_fields:
            return f"Indicator '{indicator.get('name')}': grouped_data requires 'sub_fields' in config"

        if not isinstance(sub_fields, list):
            return f"Indicator '{indicator.get('name')}': 'sub_fields' must be a list"

        if len(sub_fields) == 0:
            return f"Indicator '{indicator.get('name')}': 'sub_fields' cannot be empty"

        sub_field_names = set()

        for idx, sub_field in enumerate(sub_fields):
            if not isinstance(sub_field, dict):
                return f"Indicator '{indicator.get('name')}': sub_field at index {idx} must be an object"

            if not sub_field.get("name"):
                return f"Indicator '{indicator.get('name')}': sub_field at index {idx} requires 'name'"

            if not sub_field.get("type"):
                return f"Indicator '{indicator.get('name')}': sub_field at index {idx} requires 'type'"

            if sub_field["type"] not in ["number", "text"]:
                return f"Indicator '{indicator.get('name')}': sub_field '{sub_field.get('name')}' has invalid type '{sub_field['type']}'"

            if sub_field["name"] in sub_field_names:
                return f"Indicator '{indicator.get('name')}': duplicate sub_field name '{sub_field['name']}'"

            sub_field_names.add(sub_field["name"])

        return None

    @staticmethod
    def _validate_categorized_group(indicator):
    
        config = indicator.get("config")
        name   = indicator.get("name")

        if not config:
            return f"Indicator '{name}': categorized_group requires 'config'"

        if not config.get("category_label"):
            return f"Indicator '{name}': config requires 'category_label'"

        categories = config.get("categories")
        if not categories or not isinstance(categories, list) or len(categories) == 0:
            return f"Indicator '{name}': config requires 'categories' as a non-empty list"

        if len(set(categories)) != len(categories):
            return f"Indicator '{name}': 'categories' cannot have duplicates"

        groups = config.get("groups")
        if not groups or not isinstance(groups, list) or len(groups) == 0:
            return f"Indicator '{name}': config requires 'groups' as a non-empty list"

        if len(set(groups)) != len(groups):
            return f"Indicator '{name}': 'groups' cannot have duplicates"

        metrics = config.get("metrics")
        if not metrics or not isinstance(metrics, list) or len(metrics) == 0:
            return f"Indicator '{name}': config requires 'metrics' as a non-empty list"

        metric_keys = set()
        for idx, m in enumerate(metrics):
            if not isinstance(m, dict):
                return f"Indicator '{name}': metric at index {idx} must be an object"
            if not m.get("key"):
                return f"Indicator '{name}': metric at index {idx} requires 'key'"
            if not m.get("label"):
                return f"Indicator '{name}': metric at index {idx} requires 'label'"
            if m["key"] in metric_keys:
                return f"Indicator '{name}': duplicate metric key '{m['key']}'"
            metric_keys.add(m["key"])

        sub_sections = config.get("sub_sections")
        if sub_sections is not None:
            if not isinstance(sub_sections, list):
                return f"Indicator '{name}': 'sub_sections' must be a list"

            sub_keys = set()
            valid_max_sources = {"metrics_total", "none"}

            for idx, s in enumerate(sub_sections):
                if not isinstance(s, dict):
                    return f"Indicator '{name}': sub_section at index {idx} must be an object"
                if not s.get("key"):
                    return f"Indicator '{name}': sub_section at index {idx} requires 'key'"
                if not s.get("label"):
                    return f"Indicator '{name}': sub_section at index {idx} requires 'label'"
                if s.get("max_source") and s["max_source"] not in valid_max_sources:
                    return (...)
                if s["key"] in sub_keys:
                    return f"Indicator '{name}': duplicate sub_section key '{s['key']}'"
                
                # ← AGREGAR: validar dataset_id si es red_animalia
                if s.get("key") == "red_animalia" and s.get("dataset_id") is not None:
                    from domains.datasets.models.dataset import Dataset
                    if not isinstance(s["dataset_id"], int):
                        return f"Indicator '{name}': sub_section 'red_animalia' dataset_id must be an integer"
                    if not Dataset.query.get(s["dataset_id"]):
                        return f"Indicator '{name}': sub_section 'red_animalia' dataset {s['dataset_id']} does not exist"
                
                sub_keys.add(s["key"])

        return None

    @staticmethod
    def _validate_targets(indicator, required=True):
        targets = indicator.get("targets")

        if required and not targets:
            return f"Indicator '{indicator.get('name')}' of type '{indicator.get('field_type')}' must define at least one annual target"

        if not targets:
            return None

        if not isinstance(targets, list):
            return f"Indicator '{indicator.get('name')}': targets must be a list"

        years = set()

        for idx, target in enumerate(targets):
            year  = target.get("year")
            value = target.get("target_value")

            if not isinstance(year, int):
                return f"Indicator '{indicator.get('name')}': target at index {idx} has invalid year (must be integer)"

            if year in years:
                return f"Indicator '{indicator.get('name')}': duplicate target year {year}"
            years.add(year)

            if value is None or not isinstance(value, (int, float)) or value <= 0:
                return f"Indicator '{indicator.get('name')}': target for year {year} must be a positive number"

        return None

    @staticmethod
    def _validate_file_attachment(indicator):
        config = indicator.get("config")
        if not config:
            return None

        allowed_types = config.get("allowed_types")
        if allowed_types is not None:
            if not isinstance(allowed_types, list) or len(allowed_types) == 0:
                return f"Indicator '{indicator.get('name')}': 'allowed_types' must be a non-empty list"
            valid_extensions = {
                "pdf", "doc", "docx", "xls", "xlsx",
                "png", "jpg", "jpeg", "gif", "txt", "csv", "zip"
            }
            for ext in allowed_types:
                if ext not in valid_extensions:
                    return f"Indicator '{indicator.get('name')}': extension '{ext}' is not allowed"

        max_size_mb = config.get("max_size_mb")
        if max_size_mb is not None:
            if not isinstance(max_size_mb, (int, float)) or max_size_mb <= 0:
                return f"Indicator '{indicator.get('name')}': 'max_size_mb' must be a positive number"

        return None
    
    @staticmethod
    def _validate_dataset_select(indicator):
        from domains.datasets.models.dataset import Dataset

        config = indicator.get("config")
        name   = indicator.get("name")

        if not config:
            return f"Indicator '{name}': dataset_select requires 'config'"

        dataset_id = config.get("dataset_id")

        if dataset_id is None:
            return f"Indicator '{name}': config requires 'dataset_id'"

        if not isinstance(dataset_id, int):
            return f"Indicator '{name}': 'dataset_id' must be an integer"

        dataset = Dataset.query.get(dataset_id)
        if not dataset:
            return f"Indicator '{name}': dataset {dataset_id} does not exist"

        # ── show_if (opcional) ──────────────────────────────────────────────
        # Permite condicionar la obligatoriedad a otro indicador.
        # Estructura: {"indicator_name": "<nombre>", "value": "<valor>"}
        show_if = config.get("show_if")
        if show_if is not None:
            if not isinstance(show_if, dict):
                return f"Indicator '{name}': 'show_if' must be an object"
            if not show_if.get("indicator_name"):
                return f"Indicator '{name}': 'show_if' requires 'indicator_name'"
            if show_if.get("value") is None:
                return f"Indicator '{name}': 'show_if' requires 'value'"

        return None
    
    @staticmethod
    def _validate_groups(indicators):
        from collections import defaultdict
        groups = defaultdict(list)

        for ind in indicators:
            gname = ind.get("group_name")
            if gname:
                groups[gname].append(ind)

        for gname, members in groups.items():
            if len(members) < 2:
                return f"Group '{gname}' must have at least 2 indicators"
            required_values = {m.get("group_required", False) for m in members}
            if len(required_values) > 1:
                return f"Group '{gname}': all indicators must have the same 'group_required' value"

        return None
    
    @staticmethod
    def _validate_red_animalia(indicator):
        from domains.datasets.models.dataset import Dataset

        config = indicator.get("config")
        name   = indicator.get("name")

        if not config:
            return f"Indicator '{name}': red_animalia requires 'config'"

        dataset_id = config.get("dataset_id")

        if dataset_id is None:
            return f"Indicator '{name}': config requires 'dataset_id'"

        if not isinstance(dataset_id, int):
            return f"Indicator '{name}': 'dataset_id' must be an integer"

        dataset = Dataset.query.get(dataset_id)
        if not dataset:
            return f"Indicator '{name}': dataset {dataset_id} does not exist"

        return None