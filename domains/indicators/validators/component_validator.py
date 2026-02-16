from domains.indicators.models.Component.component import Component
from domains.indicators.models.Strategy.strategy import Strategy


class ComponentValidator:

    VALID_FIELD_TYPES = {"number", "text", "select", "sum_group"}

    @staticmethod
    def validate_create(data, component_id=None):
        errors = {}

        # strategy existence
        strategy = Strategy.query.get(data.get("strategy_id"))
        if not strategy:
            errors["strategy_id"] = "Strategy does not exist"

        # name required
        if not data.get("name"):
            errors["name"] = "Component name is required"

        # unique per strategy (permitir edición)
        exists = Component.query.filter_by(
            strategy_id=data.get("strategy_id"),
            name=data.get("name")
        ).first()

        if exists and exists.id != component_id:
            errors["name"] = "Component already exists in this strategy"

        # objectives
        objectives = data.get("objectives")
        if not objectives:
            errors["objectives"] = "At least one objective is required"

        # activities
        mga = data.get("mga_activities")
        if not mga:
            errors["mga_activities"] = "At least one MGA activity is required"

        # indicators
        indicators = data.get("indicators")
        if not indicators:
            errors["indicators"] = "At least one indicator is required"
            return errors

        names = set()

        for ind in indicators:

            # duplicated names
            if ind.get("name") in names:
                errors["indicators"] = "Indicator names cannot repeat"
            names.add(ind.get("name"))

            # valid type
            if ind.get("field_type") not in ComponentValidator.VALID_FIELD_TYPES:
                errors["indicators"] = "Invalid field_type"

            # select config
            if ind.get("field_type") == "select":
                if not ind.get("config") or not ind["config"].get("options"):
                    errors["indicators"] = "Select indicators require options"

            # sum_group config
            if ind.get("field_type") == "sum_group":
                if not ind.get("config") or not ind["config"].get("fields"):
                    errors["indicators"] = "Sum_group indicators require fields"

            # number y sum_group targets
            if ind.get("field_type") in ["number", "sum_group"]:
                targets = ind.get("targets")

                if not targets:
                    errors["indicators"] = f"Each {ind.get('field_type')} indicator must define at least one annual target"
                else:
                    years = set()

                    for t in targets:
                        year = t.get("year")
                        value = t.get("target_value")

                        if not isinstance(year, int):
                            errors["indicators"] = "Target year must be integer"

                        if year in years:
                            errors["indicators"] = "Target years cannot repeat"
                        years.add(year)

                        if value is None or value <= 0:
                            errors["indicators"] = "Target value must be greater than zero"

        return errors