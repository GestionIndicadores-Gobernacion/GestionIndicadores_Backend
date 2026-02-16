import click
from flask.cli import with_appcontext

from extensions import db
from domains.indicators.models.User.user import User
from domains.indicators.models.Role.role import Role


# =======================================================
# 🚀 SEED USERS
# =======================================================
@click.command("seed_users")
@with_appcontext
def seed_users():
    click.echo("🚀 Iniciando SEED DE USUARIOS...")

    # ===================================================
    # ROLES
    # ===================================================
    roles = ["viewer", "editor", "admin"]
    role_map = {}

    for name in roles:
        role = Role.query.filter_by(name=name).first()
        if not role:
            role = Role(name=name)
            db.session.add(role)
            click.echo(f"🧩 Rol creado: {name}")
        role_map[name] = role

    db.session.commit()

    # ===================================================
    # USUARIOS DE PRUEBA
    # ===================================================
    users = [
        {
            "first_name": "Admin",
            "last_name": "Sistema",
            "email": "admin@gobernacion.gov.co",
            "password": "Gob2025*",
            "role": "admin"
        },
        {
            "first_name": "Editor",
            "last_name": "PYBA",
            "email": "editor@gobernacion.gov.co",
            "password": "Gob2025*",
            "role": "editor"
        },
        {
            "first_name": "Viewer",
            "last_name": "PYBA",
            "email": "viewer@gobernacion.gov.co",
            "password": "Gob2025*",
            "role": "viewer"
        }
    ]

    for u in users:
        user = User.query.filter_by(email=u["email"]).first()

        if not user:
            user = User(
                first_name=u["first_name"],
                last_name=u["last_name"],
                email=u["email"],
                role_id=role_map[u["role"]].id,
                is_active=True
            )
            user.set_password(u["password"])
            db.session.add(user)
            click.echo(f"👤 Usuario creado: {u['email']}")
        else:
            user.role_id = role_map[u["role"]].id
            click.echo(f"🔁 Usuario actualizado: {u['email']}")

    db.session.commit()

    click.echo("🎉 SEED USERS COMPLETADO")
