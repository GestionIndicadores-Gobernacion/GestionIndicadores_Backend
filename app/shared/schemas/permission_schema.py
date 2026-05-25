from marshmallow import Schema, fields

from app.shared.permissions.catalog import CRITICAL_PERMS


class PermissionSchema(Schema):
    """Read-only del catálogo de permisos.

    Bloque 2: este schema existe únicamente para serialización interna y
    tests; NO se incluye automáticamente en `UserSchema` ni en respuestas
    públicas todavía. La exposición vía UI admin se decidirá en bloques
    posteriores (Fase D del plan).

    Campo derivado `is_critical` (D2): se computa contra el set
    `CRITICAL_PERMS` del catálogo. Es additive — los consumidores antiguos
    pueden ignorarlo sin romper. La UI admin lo usa para deshabilitar el
    checkbox correspondiente cuando se edita el rol `admin`.
    """
    class Meta:
        title = "Permission Schema"

    id          = fields.Int(dump_only=True)
    code        = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True, allow_none=True)
    module      = fields.Str(dump_only=True)
    is_system   = fields.Bool(dump_only=True)
    is_critical = fields.Method("get_is_critical", dump_only=True)

    def get_is_critical(self, obj):
        code = getattr(obj, "code", None)
        if code is None and isinstance(obj, dict):
            code = obj.get("code")
        return bool(code) and code in CRITICAL_PERMS
