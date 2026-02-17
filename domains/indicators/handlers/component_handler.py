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

            db.session.commit()
            return component, None

        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return None, {"database": str(e)}

    # =====================================================
    # UPSERT INDICATORS
    # Actualiza los existentes, agrega los nuevos,
    # elimina los que ya no están (solo si no tienen reportes)
    # =====================================================
    @staticmethod
    def _upsert_indicators(component, indicators_data):
        # Mapa de indicadores actuales por nombre
        existing = {
            ind.name: ind
            for ind in ComponentIndicator.query.filter_by(component_id=component.id).all()
        }

        # Nombres que vienen en el payload
        incoming_names = {ind["name"] for ind in indicators_data}

        # Eliminar indicadores que ya no están en el payload
        # Solo se pueden eliminar si NO tienen report_indicator_values asociados
        for name, indicator in existing.items():
            if name not in incoming_names:
                has_reports = db.session.execute(
                    db.text(
                        "SELECT COUNT(*) FROM report_indicator_values WHERE indicator_id = :id"
                    ),
                    {"id": indicator.id}
                ).scalar()

                if has_reports == 0:
                    db.session.delete(indicator)
                # Si tiene reportes, se deja — no se borra
                # El indicador queda "huérfano" del componente pero preserva datos históricos

        db.session.flush()

        # Upsert: actualizar existentes o crear nuevos
        for ind_data in indicators_data:
            name = ind_data["name"]

            if name in existing:
                # Actualizar indicador existente
                indicator = existing[name]
                indicator.field_type = ind_data["field_type"]
                indicator.config = ind_data.get("config")
                indicator.is_required = ind_data.get("is_required", True)
            else:
                # Crear nuevo indicador
                indicator = ComponentIndicator(
                    component_id=component.id,
                    name=name,
                    field_type=ind_data["field_type"],
                    config=ind_data.get("config"),
                    is_required=ind_data.get("is_required", True)
                )
                db.session.add(indicator)

            db.session.flush()

            # Upsert de targets (metas)
            if ind_data["field_type"] in ["number", "sum_group", "grouped_data"]:
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

        # Eliminar targets que ya no están
        for year, target in existing_targets.items():
            if year not in incoming_years:
                db.session.delete(target)

        # Upsert targets
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

            if ind["field_type"] in ["number", "sum_group", "grouped_data"]:
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