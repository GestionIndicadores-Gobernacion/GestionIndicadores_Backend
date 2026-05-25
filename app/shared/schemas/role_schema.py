from marshmallow import Schema, fields


class RoleSchema(Schema):

    class Meta:
        title = "Role Schema"

    id = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)


class RoleDetailSchema(RoleSchema):
    """Vista detallada de un rol para la UI admin (D1).

    Extiende `RoleSchema` con metadata operacional: descripción,
    flag `is_system` (protege roles canónicos de borrado en la UI)
    y conteos derivados (permisos asignados + usuarios con el rol).
    Los conteos se calculan desde las relaciones cargadas; si no
    están cargadas, SQLAlchemy emite los SELECTs adicionales — para
    listados use eager loading explícito.
    """

    class Meta:
        title = "Role Detail Schema"

    description     = fields.Str(dump_only=True, allow_none=True)
    is_system       = fields.Bool(dump_only=True)
    permission_count = fields.Method("get_permission_count", dump_only=True)
    user_count       = fields.Method("get_user_count", dump_only=True)

    def get_permission_count(self, obj):
        rps = getattr(obj, "role_permissions", None) or []
        return len(rps)

    def get_user_count(self, obj):
        users = getattr(obj, "users", None) or []
        return len(users)


class RolePermissionsUpdateSchema(Schema):
    """Input del PUT /roles/:id/permissions (D2).

    Estrategia: bulk replace — el cliente envía el set ENTERO de codes
    que quedará asignado al rol. Si llegan duplicados, el handler los
    procesa como set; si llega un code que no existe en BD, la operación
    falla con 404 y no se persiste nada.
    """

    class Meta:
        title = "Role Permissions Update"

    permission_codes = fields.List(
        fields.Str(),
        required=True,
        metadata={"description": "Lista de codes que quedará asignada al rol (reemplazo total)."},
    )
