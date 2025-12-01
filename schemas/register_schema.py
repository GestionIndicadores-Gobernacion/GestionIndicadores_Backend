# schemas/register_schema.py
from marshmallow import Schema, fields, validates_schema, ValidationError
import re

class RegisterSchema(Schema):
    name = fields.String(required=True)
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)

    @validates_schema
    def validate_all(self, data, **kwargs):

        errors = {}

        # --- name ---
        name = data.get("name")
        if not name or not name.strip():
            errors["name"] = "El nombre es obligatorio."
        elif len(name) < 3:
            errors["name"] = "El nombre debe tener mínimo 3 caracteres."
        elif not re.match(r"^[a-zA-ZÀ-ÿ\s]+$", name):
            errors["name"] = "El nombre solo puede contener letras."

        # --- email ---
        email = data.get("email")
        if not email:
            errors["email"] = "El email es obligatorio."

        # --- password ---
        password = data.get("password")
        if not password or not password.strip():
            errors["password"] = "La contraseña no puede estar vacía."
        elif len(password) < 6:
            errors["password"] = "Debe tener mínimo 6 caracteres."
        elif not re.search(r"[A-Z]", password):
            errors["password"] = "Debe tener al menos una letra mayúscula."
        elif not re.search(r"[a-z]", password):
            errors["password"] = "Debe tener al menos una letra minúscula."
        elif not re.search(r"[0-9]", password):
            errors["password"] = "Debe tener al menos un número."

        if errors:
            raise ValidationError(errors)
