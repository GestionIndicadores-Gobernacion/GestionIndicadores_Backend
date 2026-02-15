from marshmallow import Schema, fields


class RoleSchema(Schema):
    
    class Meta:
        title = "Role Schema"
        
    id = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)
