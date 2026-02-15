from marshmallow import Schema, fields, validate


class ReportIndicatorValueSchema(Schema):
    indicator_id = fields.Int(required=True)
    value = fields.Raw(required=True)


class ReportSchema(Schema):

    id = fields.Int(dump_only=True)

    strategy_id = fields.Int(required=True)
    component_id = fields.Int(required=True)

    report_date = fields.Date(required=True)

    executive_summary = fields.Str(required=True)
    activities_performed = fields.Str(required=True)

    intervention_location = fields.Str(required=True)

    zone_type = fields.Str(
        required=True,
        validate=validate.OneOf(["Urbana", "Rural"])
    )

    evidence_link = fields.Str(allow_none=True)

    indicator_values = fields.List(
        fields.Nested(ReportIndicatorValueSchema),
        required=True
    )

    created_at = fields.DateTime(dump_only=True)
