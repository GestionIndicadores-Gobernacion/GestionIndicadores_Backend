from marshmallow import Schema, fields


class PermissionSchema(Schema):
    """Read-only del catálogo de permisos.

    Bloque 2: este schema existe únicamente para serialización interna y
    tests; NO se incluye automáticamente en `UserSchema` ni en respuestas
    públicas todavía. La exposición vía UI admin se decidirá en bloques
    posteriores (Fase D del plan).
    """
    class Meta:
        title = "Permission Schema"

    id          = fields.Int(dump_only=True)
    code        = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True, allow_none=True)
    module      = fields.Str(dump_only=True)
    is_system   = fields.Bool(dump_only=True)
