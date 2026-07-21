from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.modules.action_plans.schemas.action_plan_schema import (
    ActionPlanCreateSchema,
    ActionPlanActivityReportSchema,
    ActionPlanActivityAddEvidenceSchema,
    ActionPlanActivityEditSchema,
    ActionPlanResponseSchema,
    ActionPlanActivitySchema,
    ActionPlanActivityDetailSchema,
)
from app.modules.action_plans.services.action_plan_handler import ActionPlanHandler
from app.utils.permissions import dual_required, has_permission
from app.shared.permissions import (
    PERM_ACTION_PLANS_CREATE,
    PERM_ACTION_PLANS_READ,
    PERM_ACTION_PLANS_UPDATE_OWN,
    PERM_ACTION_PLANS_UPDATE_ANY,
    PERM_ACTION_PLANS_DELETE_OWN,
    PERM_ACTION_PLANS_DELETE_ANY,
    PERM_ACTION_PLANS_REPORT_ACTIVITY,
    PERM_ACTION_PLANS_ADD_EVIDENCE,
    PERM_ACTION_PLANS_DASHBOARD,
)

blp = Blueprint(
    "action_plans", __name__,
    url_prefix="/action-plans",
    description="Gestión de Planes de Acción"
)


def _get_current_user():
    from app.shared.models.user import User
    return User.query.get(get_jwt_identity())


def _normalize_person_name(value) -> str:
    """Clave canónica para comparar nombres de personas.

    Minúsculas, sin acentos, espacios colapsados. Se usa para hacer coincidir
    un nombre de texto libre (p. ej. en el campo legacy `responsible`) con el
    nombre real de un usuario y así fusionar sus tareas en el dashboard.
    """
    import unicodedata
    if not value:
        return ""
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def _split_responsible_names(text: str) -> list[str]:
    """Divide un texto de responsables combinado en nombres individuales.

    El sistema une varios responsables con ", " (ver `responsible_display`),
    por lo que un texto libre puede traer varios nombres como si fuera uno.
    Se separa por coma, punto y coma y salto de línea, descartando vacíos.
    """
    import re
    parts = re.split(r"[,;\n]+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _is_super_admin(user) -> bool:
    """True si el usuario es el administrador principal (config SUPER_ADMIN_EMAIL).

    Es el único autorizado a eliminar planes/actividades en estado
    "Pendiente de Evidencia". Comparación case-insensitive y tolerante a espacios.
    """
    from flask import current_app
    target = (current_app.config.get("SUPER_ADMIN_EMAIL") or "").strip().lower()
    if not target:
        return False
    return bool(user and user.email and user.email.strip().lower() == target)


def _activity_is_pending_evidence(activity) -> bool:
    """Pendiente de Evidencia = reportada pero sin evidencia cargada.

    Espeja la property `ActionPlanActivity.status` sin acoplarse al string.
    """
    return activity.reported_at is not None and not activity.evidence_url


def _plan_has_pending_evidence(plan) -> bool:
    """True si el plan tiene al menos una actividad Pendiente de Evidencia."""
    for obj in plan.plan_objectives:
        for act in obj.activities:
            if _activity_is_pending_evidence(act):
                return True
    return False

def _can_manage_plans():
    user = _get_current_user()
    return user and user.role and user.role.name in ("admin", "monitor")

def _is_viewer():
    user = _get_current_user()
    return user and user.role and user.role.name == "viewer"

def _can_modify_plan(plan, perm_any: str) -> bool:
    """Helper unificado para editar/eliminar un plan.

    Política:
      - Viewer bloqueado siempre.
      - Override granular: usuario con `perm_any` en su set efectivo
        (rol ∪ grants) puede modificar cualquier plan, sin restricción de
        creador ni de componente asignado. Admin sin el permiso explícito
        no tiene privilegios extra — el permiso es la única vía de override.
      - Sin override: solo el creador puede modificar. Si el creador es
        editor, además se exige que el componente siga entre sus
        `component_assignments` (si lo desasignaron, pierde la capacidad
        aunque haya sido el autor).

    `perm_any` debe ser `PERM_ACTION_PLANS_UPDATE_ANY` o
    `PERM_ACTION_PLANS_DELETE_ANY` según la operación.
    """
    user = _get_current_user()
    if not user or not user.role or user.role.name == "viewer":
        return False
    if has_permission(perm_any):
        return True
    if plan.user_id is None or plan.user_id != user.id:
        return False
    if user.role.name == "editor":
        assigned = {uc.component_id for uc in user.component_assignments}
        return plan.component_id in assigned
    return True


def _can_edit_plan(plan):
    return _can_modify_plan(plan, PERM_ACTION_PLANS_UPDATE_ANY)


def _can_delete_plan(plan):
    return _can_modify_plan(plan, PERM_ACTION_PLANS_DELETE_ANY)

def _get_activity_plan(activity_id: int):
    """Retorna (activity, plan) o (None, None) si no existe."""
    from app.modules.action_plans.models.action_plan import (
        ActionPlanActivity, ActionPlanObjective, ActionPlan
    )
    activity = ActionPlanActivity.query.get(activity_id)
    if not activity:
        return None, None
    plan = ActionPlan.query.get(activity.plan_objective.action_plan_id)
    return activity, plan


def _can_add_evidence(activity, plan) -> bool:
    """
    Subir/editar evidencia: por defecto SOLO el responsable asignado al plan.

    Override granular: cualquier usuario (incluido admin) que tenga
    `PERM_ACTION_PLANS_ADD_EVIDENCE` en su set efectivo (rol ∪ grants)
    puede agregar/editar evidencia aunque no sea responsable. El permiso
    es la ÚNICA vía de override — admin sin el permiso no tiene
    privilegios extra. Viewer está bloqueado siempre.
    """
    user = _get_current_user()
    if not user or not user.role or user.role.name == "viewer":
        return False
    if user.id in _plan_responsible_ids(plan):
        return True
    return has_permission(PERM_ACTION_PLANS_ADD_EVIDENCE)


def _can_edit_activity(activity, plan) -> bool:
    """Editar una actividad: mismas reglas que editar el plan."""
    return _can_edit_plan(plan)


def _can_delete_activity(activity, plan) -> bool:
    """Eliminar una actividad: mismas reglas que eliminar el plan."""
    return _can_delete_plan(plan)


def _plan_responsible_ids(plan) -> set[int]:
    ids = set(plan.responsible_user_ids or [])
    if plan.responsible_user_id:
        ids.add(plan.responsible_user_id)
    return ids


def _can_report_activity(plan) -> bool:
    """
    Reportar una actividad: por defecto SOLO el responsable asignado al plan.

    Override granular: cualquier usuario (incluido admin) que tenga
    `PERM_ACTION_PLANS_REPORT_ACTIVITY` en su set efectivo (rol ∪ grants)
    puede reportar aunque no sea responsable. El permiso es la ÚNICA vía
    de override — admin sin el permiso no tiene privilegios extra.
    Viewer está bloqueado siempre.
    """
    user = _get_current_user()
    if not user or not user.role or user.role.name == "viewer":
        return False
    if user.id in _plan_responsible_ids(plan):
        return True
    return has_permission(PERM_ACTION_PLANS_REPORT_ACTIVITY)

@blp.route("/")
class ActionPlanList(MethodView):

    @jwt_required()
    @dual_required(
        roles=("admin", "monitor", "editor"),
        perms=(PERM_ACTION_PLANS_READ,),
    )
    def get(self):
        """
        GET /action-plans/[?limit=&offset=&strategy_id=&component_id=&month=&year=]

        - Sin `limit`/`offset` → lista completa (retrocompatible).
        - Con paginación → envelope `{ items, total, limit, offset }`.
        """
        from app.utils.pagination import (
            get_pagination_params, paginate_query, envelope,
        )

        query = ActionPlanHandler.base_query(
            strategy_id=request.args.get("strategy_id", type=int),
            component_id=request.args.get("component_id", type=int),
            month=request.args.get("month", type=int),
            year=request.args.get("year", type=int),
        )

        paginated, limit, offset = get_pagination_params()
        if not paginated:
            return jsonify(
                ActionPlanResponseSchema(many=True).dump(query.all())
            ), 200

        items, total = paginate_query(query, limit, offset)
        return jsonify(
            envelope(ActionPlanResponseSchema(many=True).dump(items),
                     total, limit, offset)
        ), 200

    @blp.arguments(ActionPlanCreateSchema)
    @blp.response(201, ActionPlanResponseSchema)
    @jwt_required()
    @dual_required(
        roles=("admin", "monitor", "editor"),
        perms=(PERM_ACTION_PLANS_CREATE,),
    )
    def post(self, data):
        user = _get_current_user()
        if not user or not user.role or user.role.name == "viewer":
            return jsonify({"error": "Sin permiso"}), 403

        # Editor: solo puede crear planes en sus componentes asignados.
        # Monitor y admin: cualquier componente.
        if user.role.name == "editor":
            assigned = {uc.component_id for uc in user.component_assignments}
            if data.get("component_id") not in assigned:
                return jsonify({"error": "No puedes crear planes en este componente"}), 403

        plan, errors = ActionPlanHandler.create(data)
        if errors:
            return jsonify({"errors": errors}), 422
        return plan


@blp.route("/<int:plan_id>")
class ActionPlanDetail(MethodView):

    @blp.response(200, ActionPlanResponseSchema)
    @jwt_required()
    @dual_required(
        roles=("admin", "monitor", "editor"),
        perms=(PERM_ACTION_PLANS_READ,),
    )
    def get(self, plan_id):
        plan = ActionPlanHandler.get_by_id(plan_id)
        if not plan:
            return jsonify({"error": "No encontrado"}), 404
        return plan

    @jwt_required()
    @dual_required(
        roles=("admin", "monitor", "editor"),
        perms=(PERM_ACTION_PLANS_UPDATE_OWN, PERM_ACTION_PLANS_UPDATE_ANY),
    )
    def put(self, plan_id):          # ← NUEVO
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403
        plan = ActionPlanHandler.get_by_id(plan_id)
        if not plan:
            return jsonify({"error": "No encontrado"}), 404
        if not _can_edit_plan(plan):
            return jsonify({"error": "Sin permiso"}), 403
        data = request.get_json()
        updated_plan, errors = ActionPlanHandler.update_plan(plan_id, data)
        if errors:
            return jsonify({"errors": errors}), 422
        from app.modules.action_plans.schemas.action_plan_schema import ActionPlanResponseSchema
        return jsonify(ActionPlanResponseSchema().dump(updated_plan)), 200

    @jwt_required()
    @dual_required(
        roles=("admin", "monitor", "editor"),
        perms=(PERM_ACTION_PLANS_DELETE_OWN, PERM_ACTION_PLANS_DELETE_ANY),
    )
    def delete(self, plan_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403
        plan = ActionPlanHandler.get_by_id(plan_id)
        if not plan:
            return jsonify({"error": "No encontrado"}), 404

        # Caso especial: planes con actividades "Pendiente de Evidencia"
        # (incluso vencida la ventana). Solo el administrador principal puede
        # eliminarlos — y puede aunque no sea el creador. Cualquier otro queda
        # bloqueado, incluso si tendría permiso de borrado normal.
        if _plan_has_pending_evidence(plan):
            if not _is_super_admin(_get_current_user()):
                return jsonify({
                    "error": "Este plan tiene actividades pendientes de evidencia. "
                             "Solo el administrador principal puede eliminarlo."
                }), 403
        elif not _can_delete_plan(plan):
            return jsonify({"error": "Sin permiso"}), 403

        success, errors = ActionPlanHandler.delete(plan_id)
        if not success:
            return jsonify({"errors": errors}), 404
        return jsonify({"message": "Eliminado"}), 200


@blp.route("/activities/<int:activity_id>/report")
class ActionPlanActivityReport(MethodView):

    @blp.arguments(ActionPlanActivityReportSchema)
    @jwt_required()
    @dual_required(
        roles=("admin", "monitor", "editor"),
        perms=(PERM_ACTION_PLANS_REPORT_ACTIVITY,),
    )
    def put(self, data, activity_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403

        activity, plan = _get_activity_plan(activity_id)
        if not activity:
            return jsonify({"errors": {"activity": "Actividad no encontrada."}}), 404

        if not _can_report_activity(plan):
            return jsonify({"error": "Solo el responsable asignado del plan puede reportar esta actividad"}), 403

        activity, errors = ActionPlanHandler.report_activity(activity_id, data)
        if errors:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify(ActionPlanActivityDetailSchema().dump(activity)), 200


@blp.route("/activities/<int:activity_id>/edit")
class ActionPlanActivityEdit(MethodView):

    @blp.arguments(ActionPlanActivityEditSchema)
    @jwt_required()
    @dual_required(
        roles=("admin", "monitor", "editor"),
        perms=(PERM_ACTION_PLANS_UPDATE_OWN, PERM_ACTION_PLANS_UPDATE_ANY),
    )
    def put(self, data, activity_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403

        activity, plan = _get_activity_plan(activity_id)
        if not activity:
            return jsonify({"errors": {"activity": "Actividad no encontrada."}}), 404

        if not _can_edit_activity(activity, plan):
            return jsonify({"error": "Sin permiso para editar esta actividad"}), 403

        edit_all = data.pop("edit_all", False)
        activity, errors = ActionPlanHandler.update_activity(activity_id, data, edit_all=edit_all)
        if errors:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify(ActionPlanActivityDetailSchema().dump(activity)), 200

@blp.route("/activities/<int:activity_id>")
class ActionPlanActivityDetail(MethodView):

    @jwt_required()
    @dual_required(
        roles=("admin", "monitor", "editor"),
        perms=(PERM_ACTION_PLANS_DELETE_OWN, PERM_ACTION_PLANS_DELETE_ANY),
    )
    def delete(self, activity_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403

        activity, plan = _get_activity_plan(activity_id)
        if not activity:
            return jsonify({"errors": {"activity": "Actividad no encontrada."}}), 404

        # Actividad "Pendiente de Evidencia" (incluso vencida): solo el
        # administrador principal puede eliminarla. Espeja la regla del plan.
        if _activity_is_pending_evidence(activity):
            if not _is_super_admin(_get_current_user()):
                return jsonify({
                    "error": "Esta actividad está pendiente de evidencia. "
                             "Solo el administrador principal puede eliminarla."
                }), 403
        elif not _can_delete_activity(activity, plan):
            return jsonify({"error": "Sin permiso para eliminar esta actividad"}), 403

        delete_all = request.args.get("delete_all", "false").lower() == "true"
        success, errors = ActionPlanHandler.delete_activity(activity_id, delete_all=delete_all)
        if not success:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify({"message": "Actividad eliminada"}), 200

@blp.route("/activities/<int:activity_id>/evidence")
class ActionPlanActivityEvidence(MethodView):
    """
    Agrega o edita la evidencia de una actividad ya reportada.
    Solo dentro de 8 días desde la fecha de entrega y solo el responsable.
    """

    @blp.arguments(ActionPlanActivityAddEvidenceSchema)
    @jwt_required()
    @dual_required(
        roles=("admin", "monitor", "editor"),
        perms=(PERM_ACTION_PLANS_ADD_EVIDENCE,),
    )
    def put(self, data, activity_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403

        activity, plan = _get_activity_plan(activity_id)
        if not activity:
            return jsonify({"errors": {"activity": "Actividad no encontrada."}}), 404

        if not _can_add_evidence(activity, plan):
            return jsonify({"error": "Solo el responsable de la actividad puede agregar o editar la evidencia."}), 403

        activity, errors = ActionPlanHandler.add_evidence(activity_id, data)
        if errors:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify(ActionPlanActivityDetailSchema().dump(activity)), 200


@blp.route("/dashboard/users")
class ActionPlanUserDashboard(MethodView):

    @jwt_required()
    @dual_required(
        roles=("admin", "monitor"),
        perms=(PERM_ACTION_PLANS_DASHBOARD,),
    )
    def get(self):
        from app.modules.action_plans.models.action_plan import (
            ActionPlanActivity, ActionPlanObjective, ActionPlan, activity_is_overdue,
        )
        from app.shared.models.user import User
        from sqlalchemy.orm import selectinload
        from datetime import date

        user = _get_current_user()
        if not user or user.role.name not in ("admin", "monitor"):
            return jsonify({"error": "Sin permiso"}), 403

        from app.modules.action_plans.models.action_plan import ActionPlanResponsibleUser
        from sqlalchemy.orm import selectinload as sil

        # Cargar planes con relaciones eager para evitar lazy loading fuera de sesión
        plans = ActionPlan.query.options(
            selectinload(ActionPlan.plan_objectives)
            .selectinload(ActionPlanObjective.activities)
            .selectinload(ActionPlanActivity.linked_report),
            selectinload(ActionPlan.responsible_users)
        ).all()

        # Mapa nombre-normalizado → (user_id, "Nombre Apellido") para poder
        # fusionar responsables de texto libre con su usuario real y así sumar
        # las tareas bajo una sola persona (misma clave user_{id}).
        users_by_name: dict[str, tuple[int, str]] = {}
        for u in User.query.all():
            full = f"{u.first_name or ''} {u.last_name or ''}".strip()
            key = _normalize_person_name(full)
            if key and key not in users_by_name:
                users_by_name[key] = (u.id, full)

        grouped: dict[str, dict] = {}

        def _get_or_create_group(key: str, display_name: str):
            if key not in grouped:
                grouped[key] = {
                    "responsible": display_name,
                    "plans_owner": [],
                    "activities": [],
                }
            return grouped[key]

        for plan in plans:
            # Determinar lista de responsables para agrupar
            plan_responsible_entries = []

            # Sistema nuevo: múltiples responsables
            if plan.responsible_users:
                for ru in plan.responsible_users:
                    if ru.user:
                        name = f"{ru.user.first_name} {ru.user.last_name}".strip()
                        plan_responsible_entries.append((f"user_{ru.user_id}", name))
            # Fallback legacy: responsible_user_id
            elif plan.responsible_user_id:
                u = User.query.get(plan.responsible_user_id)
                if u:
                    name = f"{u.first_name} {u.last_name}".strip()
                    plan_responsible_entries.append((f"user_{u.id}", name))
            # Fallback texto libre: puede traer varios nombres unidos
            # ("EDILBERTO PEREIRA, NATALIA VALENCIA RODAS"). Se separa en
            # personas individuales y cada una se fusiona con su usuario real
            # si el nombre coincide, para que las tareas se sumen a esa persona.
            elif plan.responsible:
                for nombre in _split_responsible_names(plan.responsible):
                    match = users_by_name.get(_normalize_person_name(nombre))
                    if match:
                        plan_responsible_entries.append((f"user_{match[0]}", match[1]))
                    else:
                        plan_responsible_entries.append((nombre, nombre))

            if not plan_responsible_entries:
                continue

            # Deduplicar por clave dentro del mismo plan para no contar dos
            # veces las actividades si una persona aparece repetida en el texto.
            seen_keys = set()
            unique_entries = []
            for group_key, display_name in plan_responsible_entries:
                if group_key in seen_keys:
                    continue
                seen_keys.add(group_key)
                unique_entries.append((group_key, display_name))

            for group_key, display_name in unique_entries:
                grp = _get_or_create_group(group_key, display_name)

                if plan.user_id:
                    owner = User.query.get(plan.user_id)
                    if owner:
                        owner_info = {
                            "user_id":    owner.id,
                            "first_name": owner.first_name,
                            "last_name":  owner.last_name,
                            "email":      owner.email,
                            "role":       owner.role.name if owner.role else None,
                        }
                        if owner_info not in grp["plans_owner"]:
                            grp["plans_owner"].append(owner_info)

                for obj in plan.plan_objectives:
                    for activity in obj.activities:
                        try:
                            c_score = activity.computed_score
                        except Exception:
                            c_score = activity.score or 0

                        # Verificar si tiene reporte vinculado
                        has_linked_report = False
                        try:
                            has_linked_report = activity.linked_report is not None
                        except Exception:
                            pass

                        grp["activities"].append({
                            "id":                activity.id,
                            "name":              activity.name,
                            "delivery_date":     str(activity.delivery_date),
                            "status":            activity.status,
                            "score":             activity.score,
                            "computed_score":    c_score,
                            "reported_at":       str(activity.reported_at) if activity.reported_at else None,
                            "evidence_url":      activity.evidence_url,
                            "generates_report":  activity.generates_report,
                            "has_linked_report": has_linked_report,
                        })

        result = []
        for _key, data in grouped.items():
            activities = data["activities"]

            completed        = [a for a in activities if a["evidence_url"]]
            pending_evidence = [a for a in activities if a["reported_at"] and not a["evidence_url"]]
            running          = [a for a in activities if not a["reported_at"] and not a["evidence_url"] and not activity_is_overdue(date.fromisoformat(a["delivery_date"]))]
            overdue          = [a for a in activities if not a["reported_at"] and not a["evidence_url"] and activity_is_overdue(date.fromisoformat(a["delivery_date"]))]

            # Actividades que generan reporte pero no tienen reporte vinculado
            without_report = [
                a for a in activities
                if a["generates_report"] and not a["has_linked_report"]
            ]

            total_score = sum(a["computed_score"] or 0 for a in activities)

            result.append({
                "responsible":               data["responsible"],
                "plans_owner":               data["plans_owner"],
                "total_activities":          len(activities),
                "completed":                 len(completed),
                "pending_evidence":          len(pending_evidence),
                "running":                   len(running),
                "pending":                   len(overdue),
                "overdue":                   len(overdue),
                "total_score":               total_score,
                "activities_without_report": len(without_report),
                "activities":                activities,
            })

        return jsonify(result), 200