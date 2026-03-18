from extensions import db

# Tabla de asociación many-to-many entre Component y PublicPolicy
component_public_policies = db.Table(
    "component_public_policies",
    db.Column(
        "component_id",
        db.Integer,
        db.ForeignKey("components.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    ),
    db.Column(
        "public_policy_id",
        db.Integer,
        db.ForeignKey("public_policies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
)