from flask.cli import with_appcontext
import click
from extensions import db
from models.user import User
from models.role import Role
from models.permission import Permission


@click.command("seed")
@with_appcontext
def seed():
    """Inicializa roles base, permisos granulares y usuario SuperAdmin"""

    click.echo("🚀 Iniciando proceso de seed...")

    # --------------------------
    # 1️⃣ Permisos del sistema
    # --------------------------
    permissions_list = [
        # Gestión de registros
        "records.read", "records.create", "records.update", "records.delete",

        # Gestión indicadores
        "indicators.read", "indicators.create", "indicators.update", "indicators.delete",

        # Gestión componentes
        "components.read", "components.create", "components.update", "components.delete",

        # Gestión usuarios
        "users.read", "users.create", "users.update", "users.delete",

        # Gestión roles y permisos
        "roles.read", "roles.create", "roles.update", "roles.delete",
    ]

    created_permissions = []
    for perm_name in permissions_list:
        perm = Permission.query.filter_by(name=perm_name).first()
        if not perm:
            perm = Permission(name=perm_name, description=f"Permiso para {perm_name.replace('.', ' ')}")
            db.session.add(perm)
            created_permissions.append(perm)

    if created_permissions:
        click.echo(f"🔧 Permisos creados: {len(created_permissions)}")
    else:
        click.echo("✔ No hay permisos nuevos que agregar.")


    # --------------------------
    # 2️⃣ Roles base
    # --------------------------
    roles = {
        "SuperAdmin": permissions_list,  # full access
        "Editor": [p for p in permissions_list if "read" in p or "create" in p or "update" in p],
        "Viewer": [p for p in permissions_list if "read" in p],
    }

    for role_name, perms in roles.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=f"Rol del sistema: {role_name}")
            db.session.add(role)
            db.session.commit()
            click.echo(f"✔ Rol creado: {role_name}")

        # Asignación de permisos
        for perm_name in perms:
            perm = Permission.query.filter_by(name=perm_name).first()

            if perm and perm not in role.permissions:
                role.permissions.append(perm)

        db.session.commit()


    # --------------------------
    # 3️⃣ Usuario administrador
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

    # Asignar el rol SuperAdmin
    superadmin_role = Role.query.filter_by(name="SuperAdmin").first()
    if superadmin_role not in admin.roles:
        admin.roles.append(superadmin_role)

    db.session.commit()

    click.echo("🎉 Seed completado con éxito. Sistema listo.")
