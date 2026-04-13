from app.core.extensions import db

from app.modules.indicators.models.Component.component import Component
from app.modules.indicators.models.Component.component_objective import ComponentObjective
from app.modules.indicators.models.Component.component_mga_activity import ComponentMGAActivity
from app.modules.indicators.models.Component.component_indicator import ComponentIndicator
from app.modules.indicators.models.Component.component_indicator_target import ComponentIndicatorTarget
from app.modules.indicators.models.PublicPolicy.public_policy import PublicPolicy

from app.modules.indicators.validators.component_validator import ComponentValidator

# Tipos de indicador que generan targets (meta anual)
TYPES_WITH_TARGETS = {"number", "sum_group", "grouped_data", "categorized_group"}


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

            # ── Políticas públicas ──────────────────────────────────────
            ComponentHandler._sync_public_policies(component, data.get("public_policy_ids", []))

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

            # Objectives y MGA: delete + recreate (no tienen datos históricos)
            ComponentObjective.query.filter_by(component_id=component.id).delete()
            ComponentMGAActivity.query.filter_by(component_id=component.id).delete()

            db.session.flush()

            # Objectives
            for obj in data["objectives"]:
                db.session.add(
                    ComponentObjective(
                        component_id=component.id,
                        description=obj["description"]
                    )
                )

            # MGA activities
            for mga in data["mga_activities"]:
                db.session.add(
                    ComponentMGAActivity(
                        component_id=component.id,
                        name=mga["name"]
                    )
                )

            # Indicators — UPSERT por nombre para preservar report_indicator_values
            ComponentHandler._upsert_indicators(component, data.get("indicators", []))

            # ── Políticas públicas ──────────────────────────────────────
            ComponentHandler._sync_public_policies(component, data.get("public_policy_ids", []))

            db.session.commit()
            return component, None

        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return None, {"database": str(e)}

    # =====================================================
    # SYNC PUBLIC POLICIES
    # Reemplaza las políticas del componente con las enviadas.
    # =====================================================
    @staticmethod
    def _sync_public_policies(component, policy_ids):
        if not policy_ids:
            component.public_policies = []
            return

        policies = PublicPolicy.query.filter(PublicPolicy.id.in_(policy_ids)).all()
        component.public_policies = policies

    # =====================================================
    # UPSERT INDICATORS
    # =====================================================
    @staticmethod
    def _upsert_indicators(component, indicators_data):
        existing_by_id = {
            ind.id: ind
            for ind in ComponentIndicator.query.filter_by(component_id=component.id).all()
        }
        existing_by_name = {ind.name: ind for ind in existing_by_id.values()}

        incoming_ids   = {ind["id"] for ind in indicators_data if ind.get("id")}
        incoming_names = {ind["name"] for ind in indicators_data if not ind.get("id")}

        # Eliminar los que ya no están
        for ind_id, indicator in existing_by_id.items():
            in_incoming_ids   = ind_id in incoming_ids
            in_incoming_names = indicator.name in incoming_names
            if not in_incoming_ids and not in_incoming_names:
                has_reports = db.session.execute(
                    db.text("SELECT COUNT(*) FROM report_indicator_values WHERE indicator_id = :id"),
                    {"id": indicator.id}
                ).scalar()
                if has_reports == 0:
                    db.session.delete(indicator)

        db.session.flush()

        # Upsert
        for index, ind_data in enumerate(indicators_data):
            indicator = None

            if ind_data.get("id"):
                indicator = existing_by_id.get(ind_data["id"])

            if indicator is None:
                indicator = existing_by_name.get(ind_data["name"])

            if indicator:
                indicator.name           = ind_data["name"]
                indicator.field_type     = ind_data["field_type"]
                indicator.config         = ind_data.get("config")
                indicator.is_required    = ind_data.get("is_required", True)
                indicator.group_name     = ind_data.get("group_name")
                indicator.group_required = ind_data.get("group_required", False)
                indicator.order          = index
            else:
                indicator = ComponentIndicator(
                    component_id=component.id,
                    name=ind_data["name"],
                    field_type=ind_data["field_type"],
                    config=ind_data.get("config"),
                    is_required=ind_data.get("is_required", True),
                    group_name=ind_data.get("group_name"),
                    group_required=ind_data.get("group_required", False),
                    order=index
                )
                db.session.add(indicator)

            db.session.flush()

            if ind_data["field_type"] in TYPES_WITH_TARGETS:
                ComponentHandler._upsert_targets(indicator, ind_data.get("targets", []))

    # =====================================================
    # UPSERT TARGETS
    # =====================================================
    @staticmethod
    def _upsert_targets(indicator, targets_data):
        existing_targets = {
            t.year: t
            for t in ComponentIndicatorTarget.query.filter_by(indicator_id=indicator.id).all()
        }

        incoming_years = {t["year"] for t in targets_data}

        for year, target in existing_targets.items():
            if year not in incoming_years:
                db.session.delete(target)

        for t_data in targets_data:
            year = t_data["year"]
            if year in existing_targets:
                existing_targets[year].target_value = t_data["target_value"]
            else:
                db.session.add(
                    ComponentIndicatorTarget(
                        indicator_id=indicator.id,
                        year=year,
                        target_value=t_data["target_value"]
                    )
                )

    # =====================================================
    # REBUILD CHILD STRUCTURE (solo usado en CREATE)
    # =====================================================
    @staticmethod
    def _rebuild_children(component, data):

        for obj in data["objectives"]:
            db.session.add(
                ComponentObjective(
                    component_id=component.id,
                    description=obj["description"]
                )
            )

        for mga in data["mga_activities"]:
            db.session.add(
                ComponentMGAActivity(
                    component_id=component.id,
                    name=mga["name"]
                )
            )

        for index, ind in enumerate(data["indicators"]):
            indicator = ComponentIndicator(
                component_id=component.id,
                name=ind["name"],
                field_type=ind["field_type"],
                config=ind.get("config"),
                is_required=ind.get("is_required", True),
                group_name=ind.get("group_name"),
                group_required=ind.get("group_required", False),
                order=index
            )

            db.session.add(indicator)
            db.session.flush()

            if ind["field_type"] in TYPES_WITH_TARGETS:
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
        
    @staticmethod
    def get_by_strategy(strategy_id: int):
        return Component.query.filter_by(strategy_id=strategy_id).all()    