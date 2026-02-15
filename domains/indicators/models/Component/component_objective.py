from extensions import db

class ComponentObjective(db.Model):
    __tablename__ = "component_objectives"

    id = db.Column(db.Integer, primary_key=True)

    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False
    )

    description = db.Column(db.Text, nullable=False)

    component = db.relationship(
        "Component",
        back_populates="objectives"
    )
