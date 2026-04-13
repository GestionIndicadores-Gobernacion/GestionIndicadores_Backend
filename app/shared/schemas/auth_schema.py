from marshmallow import Schema, fields


class LoginSchema(Schema):
    class Meta:
        title = "Login"
    email = fields.Email(required=True)
    password = fields.Str(required=True)
