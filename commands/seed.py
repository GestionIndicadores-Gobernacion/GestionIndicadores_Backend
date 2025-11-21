from flask.cli import with_appcontext
import click
from extensions import db
from models.user import User
from models.role import Role


@click.command("seed")
@with_appcontext
def seed():
    """Inicializa roles base y usuario Administrador"""
    click.echo("🚀 Iniciando proceso de seed...")

    # --------------------------
    # 1️⃣ Roles base
    # --------------------------
    roles = ["SuperAdmin", "Editor", "Viewer"]

    created_roles = []
    for role_name in roles:
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=f"Rol del sistema: {role_name}")
            db.session.add(role)
            created_roles.append(role)

    if created_roles:
        db.session.commit()
        click.echo(f"✔ Roles creados: {len(created_roles)}")
    else:
        click.echo("✔ Roles ya existentes. Nada que crear.")


    # --------------------------
    # 2️⃣ Usuario admin
    # --------------------------
    admin_email = "admin@gobernacion.gov.co"
    admin = User.query.filter_by(email=admin_email).first()

    if not admin:
        admin = User(
            name="Administrador Sistema",
            email=admin_email,
        )
        admin.set_password("Gob2025*")
        db.session.add(admin)
        click.echo("👑 Usuario SuperAdmin creado")

    # Buscar rol SuperAdmin
    superadmin_role = Role.query.filter_by(name="SuperAdmin").first()

    # Asignar rol al admin
    admin.role_id = superadmin_role.id

    db.session.commit()
    click.echo("🎉 Seed completado con éxito. Sistema listo.")
