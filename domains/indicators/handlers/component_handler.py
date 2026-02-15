from extensions import db

from domains.indicators.models.Component.component import Component
from domains.indicators.models.Component.component_objective import ComponentObjective
from domains.indicators.models.Component.component_mga_activity import ComponentMGAActivity
from domains.indicators.models.Component.component_indicator import ComponentIndicator
from domains.indicators.models.Component.component_indicator_target import ComponentIndicatorTarget

from domains.indicators.validators.component_validator import ComponentValidator


class ComponentHandler:

    # =====================================================
    # CREATE
    # =====================================================
    @staticmethod
    def create(data):

        errors = ComponentValidator.validate_create(data)
        if errors:
            return None, errors

        try:
            component = Component(
                strategy_id=data["strategy_id"],
                name=data["name"]
            )

            db.session.add(component)
            db.session.flush()

            ComponentHandler._rebuild_children(component, data)

            db.session.commit()
            return component, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    # =====================================================
    # UPDATE
    # =====================================================
    @staticmethod
    def update(component, data):

        errors = ComponentValidator.validate_create(data, component.id)
        if errors:
            return None, errors

        try:
            component.name = data["name"]

            # eliminar todo
            ComponentObjective.query.filter_by(component_id=component.id).delete()
            ComponentMGAActivity.query.filter_by(component_id=component.id).delete()
            ComponentIndicator.query.filter_by(component_id=component.id).delete()

            db.session.flush()

            ComponentHandler._rebuild_children(component, data)

            db.session.commit()
            return component, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    # =====================================================
    # REBUILD CHILD STRUCTURE
    # =====================================================
    @staticmethod
    def _rebuild_children(component, data):

        # objectives
        for obj in data["objectives"]:
            db.session.add(
                ComponentObjective(
                    component_id=component.id,
                    description=obj["description"]
                )
            )

        # mga activities
        for mga in data["mga_activities"]:
            db.session.add(
                ComponentMGAActivity(
                    component_id=component.id,
                    name=mga["name"]
                )
            )

        # indicators
        for ind in data["indicators"]:

            indicator = ComponentIndicator(
                component_id=component.id,
                name=ind["name"],
                field_type=ind["field_type"],
                config=ind.get("config"),
                is_required=ind.get("is_required", True)
            )

            db.session.add(indicator)
            db.session.flush()

            # SOLO NUMBER TIENE METAS
            if ind["field_type"] == "number":
                for t in ind.get("targets", []):
                    db.session.add(
                        ComponentIndicatorTarget(
                            indicator_id=indicator.id,
                            year=t["year"],
                            target_value=t["target_value"]
                        )
                    )

    # =====================================================
    # BASICS
    # =====================================================
    @staticmethod
    def get_all():
        return Component.query.all()

    @staticmethod
    def get_by_id(component_id):
        return Component.query.get(component_id)

    @staticmethod
    def delete(component):
        db.session.delete(component)
        db.session.commit()
