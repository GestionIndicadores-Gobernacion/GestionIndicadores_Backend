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
        "grouped_data"
    }
    
    # Tipos que requieren targets OBLIGATORIOS
    REQUIRED_TARGET_TYPES = {"number", "sum_group"}
    
    # Tipos que pueden tener targets OPCIONALES
    OPTIONAL_TARGET_TYPES = {"grouped_data"}
    
    # Tipos que NO aceptan targets
    NO_TARGET_TYPES = {"text", "select", "multi_select"}

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

            # ----------------------------------------
            # VALIDACIÓN: SELECT
            # ----------------------------------------
            if field_type == "select":
                error = ComponentValidator._validate_select(ind)
                if error:
                    errors["indicators"] = error
                    break

            # ----------------------------------------
            # VALIDACIÓN: MULTI_SELECT
            # ----------------------------------------
            if field_type == "multi_select":
                error = ComponentValidator._validate_multi_select(ind)
                if error:
                    errors["indicators"] = error
                    break

            # ----------------------------------------
            # VALIDACIÓN: SUM_GROUP
            # ----------------------------------------
            if field_type == "sum_group":
                error = ComponentValidator._validate_sum_group(ind)
                if error:
                    errors["indicators"] = error
                    break

            # ----------------------------------------
            # VALIDACIÓN: GROUPED_DATA
            # ----------------------------------------
            if field_type == "grouped_data":
                error = ComponentValidator._validate_grouped_data(ind, indicator_map)
                if error:
                    errors["indicators"] = error
                    break

            # ----------------------------------------
            # VALIDACIÓN: TARGETS (solo para tipos que los REQUIEREN)
            # ----------------------------------------
            if field_type in ComponentValidator.REQUIRED_TARGET_TYPES:
                error = ComponentValidator._validate_targets(ind, required=True)
                if error:
                    errors["indicators"] = error
                    break
            
            # Validar targets opcionales si existen
            elif field_type in ComponentValidator.OPTIONAL_TARGET_TYPES:
                targets = ind.get("targets")
                if targets and len(targets) > 0:
                    error = ComponentValidator._validate_targets(ind, required=False)
                    if error:
                        errors["indicators"] = error
                        break

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
        
        # ----------------------------------------
        # Validar parent_field
        # ----------------------------------------
        parent_field_name = config.get("parent_field")
        
        if not parent_field_name:
            return f"Indicator '{indicator.get('name')}': grouped_data requires 'parent_field' in config"
        
        parent_indicator = all_indicators.get(parent_field_name)
        
        if not parent_indicator:
            return f"Indicator '{indicator.get('name')}': parent field '{parent_field_name}' does not exist"
        
        if parent_indicator.get("field_type") != "multi_select":
            return f"Indicator '{indicator.get('name')}': parent field '{parent_field_name}' must be type 'multi_select'"
        
        # ----------------------------------------
        # Validar sub_fields
        # ----------------------------------------
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
    def _validate_targets(indicator, required=True):
        """
        Valida targets anuales.
        
        Args:
            indicator: El indicador a validar
            required: Si True, al menos un target es obligatorio
        """
        targets = indicator.get("targets")

        if required and not targets:
            return f"Indicator '{indicator.get('name')}' of type '{indicator.get('field_type')}' must define at least one annual target"
        
        # Si no hay targets y no son requeridos, OK
        if not targets:
            return None
        
        if not isinstance(targets, list):
            return f"Indicator '{indicator.get('name')}': targets must be a list"
        
        years = set()

        for idx, target in enumerate(targets):
            year = target.get("year")
            value = target.get("target_value")

            if not isinstance(year, int):
                return f"Indicator '{indicator.get('name')}': target at index {idx} has invalid year (must be integer)"

            if year in years:
                return f"Indicator '{indicator.get('name')}': duplicate target year {year}"
            years.add(year)

            if value is None or not isinstance(value, (int, float)) or value <= 0:
                return f"Indicator '{indicator.get('name')}': target for year {year} must be a positive number"

        return None