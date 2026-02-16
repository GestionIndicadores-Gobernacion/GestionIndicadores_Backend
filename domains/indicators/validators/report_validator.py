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

        indicator_map = {ind.id: ind for ind in component_indicators}

        indicator_errors = []

        # ---------------------
        # Extract year from report_date
        # ---------------------
        report_date = data.get("report_date")
        report_year = report_date.year if report_date else None

        for value in indicator_values:

            indicator = indicator_map.get(value.get("indicator_id"))

            if not indicator:
                indicator_errors.append("Invalid indicator_id")
                continue

            field_type = indicator.field_type
            val = value.get("value")

            # ---------------------
            # Type validation
            # ---------------------
            if field_type == "number":

                if not isinstance(val, (int, float)):
                    indicator_errors.append(
                        f"Number expected for indicator {indicator.id}"
                    )
                    continue

                # ---------------------
                # Target validation (ONLY for number)
                # ---------------------
                target = ComponentIndicatorTarget.query.filter_by(
                    indicator_id=indicator.id,
                    year=report_year
                ).first()

                if not target:
                    indicator_errors.append(
                        f"No target defined for indicator {indicator.id} in year {report_year}"
                    )

            elif field_type == "text":

                if not isinstance(val, str):
                    indicator_errors.append(
                        f"Text expected for indicator {indicator.id}"
                    )

            elif field_type == "select":

                options = indicator.config.get("options", []) if indicator.config else []
                if val not in options:
                    indicator_errors.append(
                        f"Invalid option selected for indicator {indicator.id}"
                    )

            elif field_type == "sum_group":

                if not isinstance(val, dict):
                    indicator_errors.append(
                        f"Dictionary expected for indicator {indicator.id}"
                    )

        if indicator_errors:
            errors["indicator_values"] = indicator_errors

        return errors
