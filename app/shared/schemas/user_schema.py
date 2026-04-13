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

    created_at = fields.Str(dump_only=True)
    updated_at = fields.Str(dump_only=True)

    role = fields.Nested(RoleSchema, dump_only=True)

    # Componentes asignados — solo en respuesta
    component_assignments = fields.Nested(
        UserComponentSchema, many=True, dump_only=True
    )