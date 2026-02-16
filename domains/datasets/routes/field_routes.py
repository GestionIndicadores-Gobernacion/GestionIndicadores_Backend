from flask_smorest import Blueprint
from flask.views import MethodView
from flask import request

from domains.datasets.models.field import Field
from domains.datasets.models.table import Table
from domains.datasets.schemas.field_schema import FieldSchema
from domains.datasets.validators.field_validator import validate_field_definition
from extensions import db

blp = Blueprint(
    "fields",
    __name__,
    url_prefix="/fields",
    description="Gestión de campos"
)

# =========================
# LISTAR / CREAR
# =========================
@blp.route("")
class FieldListResource(MethodView):

    @blp.response(200, FieldSchema(many=True))
    def get(self):
        table_id = request.args.get("table_id", type=int)

        query = Field.query

        if table_id:
            Table.query.get_or_404(table_id)
            query = query.filter_by(table_id=table_id)

        return (
            query
            .order_by(Field.id.asc())
            .all()
        )

    @blp.arguments(FieldSchema)
    @blp.response(201, FieldSchema)
    def post(self, data):
        table_id = data.get("table_id")
        Table.query.get_or_404(table_id)

        validate_field_definition(
            name=data["name"],
            label=data["label"],
            field_type=data["type"],
            table_id=table_id,
            options=data.get("options")
        )

        field = Field(
            table_id=table_id,
            name=data["name"],
            label=data["label"],
            type=data["type"],
            required=data.get("required", False),
            options=data.get("options")
        )

        db.session.add(field)
        db.session.commit()
        return field


# =========================
# DETALLE / UPDATE / DELETE
# =========================
@blp.route("/<int:field_id>")
class FieldResource(MethodView):

    @blp.response(200, FieldSchema)
    def get(self, field_id):
        return Field.query.get_or_404(field_id)

    @blp.arguments(FieldSchema(partial=True))
    @blp.response(200, FieldSchema)
    def put(self, data, field_id):
        field = Field.query.get_or_404(field_id)

        validate_field_definition(
            name=data.get("name", field.name),
            label=data.get("label", field.label),
            field_type=data.get("type", field.type),
            table_id=field.table_id,
            options=data.get("options", field.options),
            field_id=field_id
        )

        for attr in ["name", "label", "type", "required", "options"]:
            if attr in data:
                setattr(field, attr, data[attr])

        db.session.commit()
        return field

    @blp.response(204)
    def delete(self, field_id):
        field = Field.query.get_or_404(field_id)
        db.session.delete(field)
        db.session.commit()
