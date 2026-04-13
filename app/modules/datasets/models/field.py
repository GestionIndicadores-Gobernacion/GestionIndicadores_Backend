from app.core.extensions import db

class Field(db.Model):
    __tablename__ = "fields"

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(
        db.Integer,
        db.ForeignKey("tables.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(120), nullable=False)
    label = db.Column(db.Text, nullable=False)

    type = db.Column(
        db.Enum("text", "number", "select", "boolean", "date", name="field_type"),
        nullable=False
    )

    required = db.Column(db.Boolean, default=False)
    options = db.Column(db.JSON)

    table = db.relationship(
        "Table",
        backref=db.backref(
            "fields",
            cascade="all, delete-orphan",
            passive_deletes=True
        )
    )
