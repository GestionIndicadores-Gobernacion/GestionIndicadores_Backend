from flask.cli import with_appcontext
import click
from extensions import db
from models.user import User
from models.role import Role
from models.strategy import Strategy
from models.component import Component
from models.indicator import Indicator
from datetime import datetime


@click.command("seed")
@with_appcontext
def seed():
    click.echo("🚀 Iniciando proceso de seed...")

    # ===================================================
    # 1️⃣ ROLES
    # ===================================================
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

    # ===================================================
    # 2️⃣ USUARIO ADMIN
    # ===================================================
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

    superadmin_role = Role.query.filter_by(name="SuperAdmin").first()
    admin.role_id = superadmin_role.id
    db.session.commit()

    # ======================================================
    # 3️⃣ Estrategia + Componentes + Indicadores
    # ======================================================

    strategy_name = "OPERATIVIZAR"

    strategy = Strategy.query.filter_by(name=strategy_name).first()

    if not strategy:
        strategy = Strategy(
            name=strategy_name,
            description=(
                "ESTRATEGIA QUE GARANTICE EL CUMPLIMIENTO DE LA POLÍTICA DE "
                "PROTECCIÓN Y BIENESTAR ANIMAL EN TÉRMINOS DE PREVENCIÓN DEL "
                "RIESGO DE VIOLENCIA Y GOBERNANZA INTERINSTITUCIONAL EN EL "
                "PERIODO DE GOBIERNO"
            ),
            active=True,
            created_at=datetime.utcnow()
        )
        db.session.add(strategy)
        db.session.commit()
        click.echo("📌 Estrategia creada")
    else:
        click.echo("✔ Estrategia ya existente")

    # ======================================================
    # HELPER PARA CREAR COMPONENTES + INDICADORES
    # ======================================================
    def crear_componente(nombre, indicadores):
        comp = Component.query.filter_by(name=nombre).first()

        if not comp:
            comp = Component(
                strategy_id=strategy.id,
                name=nombre,
                description=f"Componente '{nombre}' de la estrategia Operativizar.",
                data_type="integer",   # 👈 siempre integer
                active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(comp)
            db.session.commit()
            click.echo(f"🧩 Componente creado: {nombre}")
        else:
            click.echo(f"🧩 Componente ya existe: {nombre}")

        # Crear indicadores del componente
        for ind_name in indicadores:
            ind = Indicator.query.filter_by(name=ind_name).first()
            if not ind:
                ind = Indicator(
                    component_id=comp.id,
                    name=ind_name,
                    description=f"Indicador '{ind_name}' del componente {nombre}",
                    data_type="integer",   # 👈 también integer
                    active=True,
                    # si tu modelo tiene created_at, déjalo;
                    # si no, quita esta línea:
                    created_at=datetime.utcnow()
                )
                db.session.add(ind)
                db.session.commit()
                click.echo(f"   ✔ Indicador creado: {ind_name}")
            else:
                click.echo(f"   ✔ Indicador ya existe: {ind_name}")

    # ======================================================
    # 4️⃣ LISTA COMPLETA DE COMPONENTES E INDICADORES
    # ======================================================
    componentes = [
        {
            "name": "ANIMALES COMO EMBAJADORES DE PAZ",
            "indicators": [
                "No de Habitantes de Calle Impactados",
                "No de Adultos Mayores Impactados"
            ]
        },
        {
            "name": "TURISMO MULTIESPECIE",
            "indicators": [
                "No Guias Turisticos Capacitados",
                "No de Rutas Turisticas Impactadas"
            ]
        },
        {
            "name": "IMPLEMENTAR EL PROGRAMA ESCUADRON BENJI PRIMERA INFANCIA",
            "indicators": [
                "No de Niños, Niñas, Adolescentes (NNA) Impactados"
            ]
        },
        {
            "name": "IMPLEMENTAR EL PROGRAMA SERVICIO SOCIAL DEJANDO HUELLA",
            "indicators": [
                "No de Casos Atendidos",
                "No de Animales Atendidos",
                "No Guias Operativas Implemetadas"
            ]
        },
        {
            "name": "IMPLEMENTAR PROGRAMA DE GUARDIANTES DE HUELLA EN ARTICULACION CON LA SECRETARIA DE MUJER",
            "indicators": [
                "No de Personas Atendidas",
                "No de Animales Atendidos",
                "No Guias Operativas Implementadas"
            ]
        },
        {
            "name": "IMPLEMENTAR PROGRAMA DE LOS ANIMALES COMO VICTIMAS DEL CONFLICTO ARMADO",
            "indicators": [
                "No de Personas Atendidas",
                "No de Animales Atendidos",
                "No Guias Operativas Implementadas"
            ]
        },
        {
            "name": "IMPLEMENTAR POGRAMA PARA COMUNIDADES ETNICAS",
            "indicators": [
                # No enviaste indicadores → queda vacío
            ]
        },
        {
            "name": "EQUIPO MULTIDISCIPLINARIO",
            "indicators": [
                "No de Asistencias Tecnicas Realizadas"
            ]
        },
        {
            "name": "OBSERVATORIO /PLATAFORMA",
            "indicators": [
                "No de Plataformas Implementadas",
                "No de Estrategias Monitoreadas",
                "No de Observatorios Implementados"
            ]
        },
        {
            "name": "RUTA DE ATENCION PLATAFORMA DENUNCIAS LINEA SEGUIMIENTO OFICIOS",
            "indicators": [
                "No de Casos Recibidos",
                "No de Casos Atendidos",
                "No de Seguimiento de Casos Recibidos"
            ]
        }
    ]

    # Crear todos
    for c in componentes:
        crear_componente(c["name"], c["indicators"])

    click.echo("🎉 Seed completado exitosamente")
