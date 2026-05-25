from marshmallow import Schema, fields
from .role_schema import RoleSchema


class UserComponentSchema(Schema):
    """Schema ligero para mostrar qué componentes tiene un usuario."""
    component_id = fields.Int()
    component_name = fields.Method("get_component_name")

    def get_component_name(self, obj):
        return obj.component.name if obj.component else None


class UserSchema(Schema):

    class Meta:
        title = "User Schema"

    id = fields.Int(dump_only=True)

    first_name = fields.Str(required=True)
    last_name = fields.Str(required=True)
    email = fields.Email(required=True)

    # password SOLO para input
    password = fields.Str(load_only=True, required=True)

    role_id = fields.Int(load_only=True, required=False)

    # Lista de IDs al crear/editar: POST/PUT { "component_ids": [1, 2, 3] }
    component_ids = fields.List(fields.Int(), load_only=True, required=False)

    profile_image_url = fields.Str(allow_none=True)

    is_active = fields.Bool(dump_only=True)

    # ── RBAC (Bloque 11) ────────────────────────────────────────────────
    # Marca al admin principal protegido. El frontend lo usa para deshabilitar
    # el selector de rol en su propio formulario (reemplaza el hardcode por
    # email que existía en user-form.ts).
    is_main_admin = fields.Bool(dump_only=True)

    created_at = fields.Str(dump_only=True)
    updated_at = fields.Str(dump_only=True)

    role = fields.Nested(RoleSchema, dump_only=True)

    # Componentes asignados — solo en respuesta
    component_assignments = fields.Nested(
        UserComponentSchema, many=True, dump_only=True
    )

    # ── RBAC (Bloque 6): permisos efectivos solo para el usuario activo ──
    # Nunca filtramos permisos de OTROS usuarios en listados — devolvemos
    # `null` cuando el objeto serializado no es el del JWT. En login/refresh
    # se inyectan vía contexto (no hay JWT en flight todavía).
    permissions = fields.Method("get_permissions", dump_only=True)

    def get_permissions(self, obj):
        # Caso 1: caller pre-computó los perms (login/refresh).
        ctx = self.context or {}
        precomputed = ctx.get("precomputed_permissions")
        precomputed_for = ctx.get("precomputed_permissions_for_user_id")
        if precomputed is not None and precomputed_for == obj.id:
            return list(precomputed)

        # Caso 2: serializando al usuario del JWT vigente — cache en `g`.
        from app.utils.permissions import _current_user_id, current_user_permissions
        current_uid = _current_user_id()
        if current_uid is not None and obj.id == current_uid:
            return sorted(current_user_permissions())

        # Caso 3: otro usuario en una lista — no filtrar permisos ajenos.
        return None