"""Schemas RBAC para visualización y edición de permisos por usuario.

Estos schemas sirven a los endpoints admin:
- `UserPermissionsViewSchema` (D1, read-only) → snapshot completo del set
  efectivo de un usuario (rol + grants − revokes) más los conjuntos de
  origen.
- `UserPermissionOverrideSchema` (D1, read-only) → entrada del listado de
  overrides directos (grant/revoke), con metadata de quién y cuándo lo
  otorgó.
- `OverrideEntrySchema` + `UserOverridesUpdateSchema` (D3) → input del
  PUT /users/:id/permissions/overrides para bulk replace.
"""
from marshmallow import Schema, fields
from marshmallow.validate import OneOf


class _UserRefSchema(Schema):
    """Referencia mínima a un usuario en respuestas de permisos."""

    class Meta:
        title = "User Permission Ref"

    id    = fields.Int(dump_only=True)
    email = fields.Str(dump_only=True)


class _RoleRefSchema(Schema):
    """Referencia mínima a un rol en respuestas de permisos."""

    class Meta:
        title = "Role Permission Ref"

    id   = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)


class _UserWithRoleSchema(Schema):
    """Usuario con su rol embebido — usado dentro de
    `UserPermissionsViewSchema.user`.
    """

    class Meta:
        title = "User With Role"

    id    = fields.Int(dump_only=True)
    email = fields.Str(dump_only=True)
    role  = fields.Nested(_RoleRefSchema, dump_only=True)


class _PermissionRefSchema(Schema):
    """Referencia a un permiso para el listado de overrides.

    No incluye `id`/`is_system`/`created_at` porque la UI sólo necesita
    code/description/module para renderizar la fila.
    """

    class Meta:
        title = "Permission Ref"

    code        = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True, allow_none=True)
    module      = fields.Str(dump_only=True)


class UserPermissionsViewSchema(Schema):
    """Vista agregada de permisos efectivos de un usuario.

    Shape:
        {
          "user": {id, email, role: {id, name}},
          "from_role": ["code", ...],
          "grants":    ["code", ...],
          "revokes":   ["code", ...],
          "effective": ["code", ...]
        }

    `effective` = (from_role ∪ grants) − revokes — debe coincidir con
    `get_effective_permissions(user)`.
    """

    class Meta:
        title = "User Permissions View"

    user      = fields.Nested(_UserWithRoleSchema, dump_only=True)
    from_role = fields.List(fields.Str(), dump_only=True)
    grants    = fields.List(fields.Str(), dump_only=True)
    revokes   = fields.List(fields.Str(), dump_only=True)
    effective = fields.List(fields.Str(), dump_only=True)


class UserPermissionOverrideSchema(Schema):
    """Override directo (grant/revoke) sobre un permiso, con metadata.

    Shape:
        {
          "permission": {code, description, module},
          "effect": "grant" | "revoke",
          "granted_by": {id, email} | null,
          "granted_at": "2026-05-25T..."
        }
    """

    class Meta:
        title = "User Permission Override"

    permission = fields.Nested(_PermissionRefSchema, dump_only=True)
    effect     = fields.Str(dump_only=True)
    granted_by = fields.Method("get_granted_by", dump_only=True)
    granted_at = fields.DateTime(dump_only=True)

    def get_granted_by(self, obj):
        granter = getattr(obj, "granted_by_user", None)
        if granter is None:
            return None
        return {"id": granter.id, "email": granter.email}


# ─── D3: Input del PUT /users/:id/permissions/overrides ────────────────────


class OverrideEntrySchema(Schema):
    """Entrada individual del bulk replace de overrides (D3).

    Shape: `{"permission_code": "...", "effect": "grant"|"revoke"}`.
    El handler aplica las validaciones semánticas restantes (que el code
    exista en BD, sin duplicados, revoke sobre algo que el rol da, etc.)
    porque dependen del estado de BD y del actor.
    """

    class Meta:
        title = "Override Entry"

    permission_code = fields.Str(required=True)
    effect          = fields.Str(required=True, validate=OneOf(["grant", "revoke"]))


class UserOverridesUpdateSchema(Schema):
    """Input del PUT /users/:id/permissions/overrides (D3).

    Estrategia: bulk replace — el cliente envía el set ENTERO de overrides
    que quedará persistido tras la operación. Los que no aparezcan se
    eliminan (vuelven al efecto del rol).
    """

    class Meta:
        title = "User Overrides Update"

    overrides = fields.List(
        fields.Nested(OverrideEntrySchema),
        required=True,
        metadata={
            "description": (
                "Lista completa de overrides que quedará asignada al usuario "
                "(reemplazo total). Cada item es {permission_code, effect}."
            ),
        },
    )
