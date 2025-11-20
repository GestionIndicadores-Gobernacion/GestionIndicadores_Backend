from extensions import db

class Indicator(db.Model):
    __tablename__ = "indicators"

    id = db.Column(db.Integer, primary_key=True)

    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    data_type = db.Column(
        db.Enum("integer", "decimal", "boolean", "text", "date", "category", name="indicator_data_type"),
        nullable=False
    )

    required = db.Column(db.Boolean, default=False)
    use_list = db.Column(db.Boolean, default=False)

    allowed_values = db.Column(db.JSON, nullable=True)

    active = db.Column(db.Boolean, default=True)

    # relación inversa con componente
    component = db.relationship("Component", backref="indicators", lazy=True)
