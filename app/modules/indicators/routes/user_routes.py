from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from app.modules.indicators.services.user_handler import UserHandler
from app.shared.schemas.user_schema import UserSchema
from app.shared.models.user import User
from app.shared.models.user_component import UserComponent
from app.utils.permissions import role_required
from app.utils.pagination import get_pagination_params, paginate_query, envelope


def _basic_user_dump(users):
    """Proyección mínima (id, first_name, last_name) para roles no privilegiados.
    Suficiente para poblar selects de "responsable" sin filtrar email,
    role ni component_assignments.
    """
    return [
        {"id": u.id, "first_name": u.first_name, "last_name": u.last_name}
        for u in users
    ]

blp = Blueprint(
    "users",
    "users",
    url_prefix="/users",
    description="User management"
)


# ── CRUD base ────────────────────────────────────────────────────────────────

from flask_jwt_extended import get_jwt_identity

@blp.route("/me")
class UserMeResource(MethodView):

    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self):
        user_id = get_jwt_identity()
        user = UserHandler.get_by_id(int(user_id))
        if not user:
            return {"message": "User not found"}, 404
        return user
    
@blp.route("/")
class UserListResource(MethodView):

    @jwt_required()
    def get(self):
        """
        GET /users/[?limit=&offset=]

        Acceso:
          - admin / monitor → datos completos (UserSchema).
          - editor          → proyección básica (id + nombre) para poblar
                              selects de responsable en el Plan de Acción.
          - viewer          → 403.

        - Sin parámetros → lista completa (retrocompatible).
        - Con `limit`/`offset` → envelope `{ items, total, limit, offset }`.
        """
        current_id = int(get_jwt_identity())
        current = UserHandler.get_by_id(current_id)
        role_name = current.role.name if current and current.role else None
        if role_name not in ("admin", "monitor", "editor"):
            return jsonify({"message": "Forbidden"}), 403

        is_privileged = role_name in ("admin", "monitor")
        dump = (lambda items: UserSchema(many=True).dump(items)) if is_privileged else _basic_user_dump

        query = User.query.order_by(User.created_at.desc())

        # Filtro opcional: ?component_id=N → solo usuarios con ese componente
        # asignado en user_components. Útil para poblar el select de
        # "Responsables" en el modal de Plan de Acción según el componente
        # elegido.
        component_id = request.args.get("component_id", type=int)
        if component_id:
            query = (
                query
                .join(UserComponent, UserComponent.user_id == User.id)
                .filter(UserComponent.component_id == component_id)
                .distinct()
            )

        paginated, limit, offset = get_pagination_params()
        if not paginated:
            return jsonify(dump(query.all())), 200
        items, total = paginate_query(query, limit, offset)
        return jsonify(envelope(dump(items), total, limit, offset)), 200

    @jwt_required()
    @role_required("admin")
    @blp.arguments(UserSchema)
    @blp.response(201, UserSchema)
    def post(self, data):
        """Crear usuario. Puede incluir component_ids: [1,2,3]"""
        user, errors = UserHandler.create(data)
        if errors:
            return {"errors": errors}, 400
        return user


@blp.route("/<int:user_id>")
class UserResource(MethodView):

    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self, user_id):
        # Solo admin/monitor pueden ver cualquier usuario; el resto
        # solamente su propio perfil (/users/me es la ruta canónica).
        current_id = int(get_jwt_identity())
        current = UserHandler.get_by_id(current_id)
        is_privileged = bool(
            current and current.role and current.role.name in ("admin", "monitor")
        )
        if not is_privileged and current_id != user_id:
            return {"message": "Forbidden"}, 403

        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        return user

    @jwt_required()
    @role_required("admin")
    @blp.arguments(UserSchema(partial=True))
    @blp.response(200, UserSchema)
    def put(self, data, user_id):
        """Editar usuario. Si incluye component_ids, reemplaza todas las asignaciones."""
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        return UserHandler.update(user, data)

    @jwt_required()
    @role_required("admin")
    @blp.response(204)
    def delete(self, user_id):
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        UserHandler.delete(user)


# ── Asignaciones de componentes ──────────────────────────────────────────────

@blp.route("/<int:user_id>/components/<int:component_id>")
class UserComponentResource(MethodView):

    @jwt_required()
    @role_required("admin")
    @blp.response(201)
    def post(self, user_id, component_id):
        """Asignar un componente a un usuario."""
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404

        uc, error = UserHandler.assign_component(user_id, component_id)
        if error:
            return {"message": error}, 400
        return {"message": "Component assigned", "user_id": user_id, "component_id": component_id}

    @jwt_required()
    @role_required("admin")
    @blp.response(204)
    def delete(self, user_id, component_id):
        """Quitar un componente de un usuario."""
        removed = UserHandler.remove_component(user_id, component_id)
        if not removed:
            return {"message": "Assignment not found"}, 404