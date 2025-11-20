from marshmallow import Schema, fields, validates_schema, ValidationError

class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)

    @validates_schema
    def validate_all(self, data, **kwargs):

        errors = {}

        if not data.get("email"):
            errors["email"] = "El email es obligatorio."

        if not data.get("password") or not data["password"].strip():
            errors["password"] = "La contraseña es obligatoria."

        if errors:
            raise ValidationError(errors)
