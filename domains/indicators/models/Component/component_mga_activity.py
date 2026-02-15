from extensions import db

class ComponentMGAActivity(db.Model):
    __tablename__ = "component_mga_activities"

    id = db.Column(db.Integer, primary_key=True)

    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(255), nullable=False)

    component = db.relationship(
        "Component",
        back_populates="mga_activities"
    )