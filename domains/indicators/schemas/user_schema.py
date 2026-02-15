from marshmallow import Schema, fields
from .role_schema import RoleSchema


class UserSchema(Schema):

    class Meta:
        title = "User Schema"

    id = fields.Int(dump_only=True)

    first_name = fields.Str(required=True)
    last_name = fields.Str(required=True)
    email = fields.Email(required=True)

    # password SOLO para input
    password = fields.Str(load_only=True, required=True)

    profile_image_url = fields.Str(allow_none=True)

    is_active = fields.Bool(dump_only=True)

    created_at = fields.Str(dump_only=True)
    updated_at = fields.Str(dump_only=True)

    role = fields.Nested(RoleSchema, dump_only=True)
