from flask.cli import with_appcontext
import click
import random  # 👈 AÑADIDO PARA GENERAR METAS
from extensions import db
from models.user import User
from models.role import Role
from models.strategy import Strategy
from models.component import Component
from models.indicator import Indicator
from models.activity import Activity


@click.command("seed")
@with_appcontext
def seed():
    click.echo("🚀 Iniciando SEED del sistema...")

    # ===================================================
    # 1️⃣ ROLES
    # ===================================================
    roles = ["SuperAdmin", "Editor", "Viewer"]
    for role_name in roles:
        if not Role.query.filter_by(name=role_name).first():
            db.session.add(Role(name=role_name, description=f"Rol del sistema: {role_name}"))
    db.session.commit()
    click.echo("✔ Roles verificados")

    # ===================================================
    # 2️⃣ USUARIO SUPERADMIN
    # ===================================================
    admin_email = "admin@gobernacion.gov.co"
    admin = User.query.filter_by(email=admin_email).first()

    if not admin:
        admin = User(
            name="Administrador Sistema",
            email=admin_email
        )
        admin.set_password("Gob2025*")
        db.session.add(admin)
        click.echo("👑 Usuario SuperAdmin creado")

    superadmin_role = Role.query.filter_by(name="SuperAdmin").first()
    admin.role_id = superadmin_role.id
    db.session.commit()

    # ======================================================
    # 3️⃣ Usuarios adicionales (Editor y Viewer)
    # ======================================================
    usuarios_extra = [
        {
            "name": "Editor del Sistema",
            "email": "editor@gobernacion.gov.co",
            "password": "Editor2025*",
            "role": "Editor",
        },
        {
            "name": "Usuario Viewer",
            "email": "viewer@gobernacion.gov.co",
            "password": "Viewer2025*",
            "role": "Viewer",
        }
    ]

    for data in usuarios_extra:
        user = User.query.filter_by(email=data["email"]).first()
        if not user:
            user = User(name=data["name"], email=data["email"])
            user.set_password(data["password"])
            db.session.add(user)
            click.echo(f"👤 Usuario creado: {data['email']}")

        role = Role.query.filter_by(name=data["role"]).first()
        user.role_id = role.id

    db.session.commit()

    # ======================================================
    # 4️⃣ ESTRATEGIAS + ACTIVIDADES
    # ======================================================
    estrategias_con_actividades = {
        "OPERATIVIZAR": [
            "DESARROLLAR LA METODOLOGÍA PARA LA PREVENCIÓN DE LOS RIESGOS DE VIOLENCIAS CONTRA LOS ANIMALES",
            "OPERATIVIZAR EL COMITÉ INTERDISCIPLINARIO, CON SABERES FINANCIEROS, JURÍDICOS, SOCIALES Y MEDICO VETERINARIOS...",
            "CAPACITAR A LOS GRUPOS DE INTERÉS RELACIONADOS CON LA PROTECCIÓN Y EL BIENESTAR ANIMAL...",
            "IMPLEMENTAR EL OBSERVATORIO DEPARTAMENTAL DE POLÍTICA PÚBLICA DE PROTECCIÓN Y BIENESTAR ANIMAL"
        ],
        "DOTAR TRES CENTROS DE BIENESTAR ANIMAL REGIONAL": [
            "Asesorar técnica y administrativamente los procesos desarrollados por los centros de bienestar animal regional",
            "Dotar los centros de bienestar animal regional con insumos definidos concertadamente",
        ],
        "ATENDER 10.000 ANIMALES": [
            "REALIZAR JORNADAS DE ATENCIÓN INTEGRAL PARA LOS ANIMALES EN SITUACIÓN DE VULNERABILIDAD",
            "ELABORAR DIAGNOSTICOS POBLACIONALES QUE IDENTIFIQUEN ZONAS PRIORITARIAS"
        ],
        "COFINANCIAR A 40 ACTORES": [
            "ACOMPAÑAR TÉCNICAMENTE LAS ACCIONES DESARROLLADAS POR ACTORES ANIMALISTAS",
            "SUMINISTRAR INSUMOS A ACTORES VOLUNTARIOS QUE PROTEGEN ANIMALES"
        ],
        "CREAR Y SOSTENER 3 REDES DE ACTORES": [
            "SUMINISTRAR INSUMOS A REDES DE PROTECCIÓN ANIMAL",
            "ACOMPAÑAR TÉCNICAMENTE A LOS ACTORES DE LA RED"
        ],
        "CAPACITAR 10.000 PERSONAS EN BIENESTAR ANIMAL": [
            "CAPACITAR A GRUPOS EN PROCESOS DE INCLUSIÓN Y RESPETO A LOS ANIMALES",
            "ELABORAR DIAGNÓSTICOS POBLACIONALES",
            "REALIZAR EVENTOS DE PROMOCIÓN DE EXPERIENCIAS"
        ]
    }

    estrategia_objs = {}

    for nombre_estrategia, actividades in estrategias_con_actividades.items():
        estrategia = Strategy.query.filter_by(name=nombre_estrategia).first()
        if not estrategia:
            estrategia = Strategy(
                name=nombre_estrategia,
                description=f"Estrategia automática: {nombre_estrategia}",
                active=True
            )
            db.session.add(estrategia)
            click.echo(f"📌 Estrategia creada: {nombre_estrategia}")
        else:
            click.echo(f"✔ Estrategia existente: {nombre_estrategia}")

        db.session.commit()
        estrategia_objs[nombre_estrategia] = estrategia

        for act_desc in actividades:
            existe = Activity.query.filter_by(
                strategy_id=estrategia.id, description=act_desc).first()
            if not existe:
                db.session.add(Activity(
                    strategy_id=estrategia.id,
                    description=act_desc,
                    active=True
                ))
                click.echo(f" ➕ Actividad agregada: {act_desc[:60]}...")

        db.session.commit()

    click.echo("🎉 Estrategias y actividades creadas exitosamente")

    # ======================================================
    # 5️⃣ COMPONENTES POR ESTRATEGIA
    # ======================================================
    componentes_por_estrategia = {
        "DOTAR TRES CENTROS DE BIENESTAR ANIMAL REGIONAL": [
            "ASISTENCIA TECNICA"
        ],
        "ATENDER 10.000 ANIMALES": [
            "ATENCION EN SALUD ANIMAL COMPAÑERO",
            "ATENCION PRIMARIA EN SALUD PARA ANIMALES DE PRODUCCION Y GRANJA",
            "PREVENCION EN SALUD DE LA FAUNA LIMINAL Y SILVESTRE",
            "EQUIPO URIA (VETERINARIOS - PSICOLOGO - ABOGADO)"
        ],
        "COFINANCIAR A 40 ACTORES": [
            "CLÚSTER EMPRESARIAL",
            "AUTOSOSTENIBILIDAD DE REFUGIOS",
            "EMPRENDIMIENTOS CONSCIENTES VALLEINN",
            "ALIANZAS ESTRATEGICAS"
        ],
        "CREAR Y SOSTENER 3 REDES DE ACTORES": [
            "DONATON SALVANDO HUELLAS",
            "RED ANIMALIA",
            "ACOMPÁÑAMIENTO PSICOSOCIAL",
            "PROGRAMA DE ADOPCIONES",
            "JUNTAS DEFENSORAS DE ANIMALES"
        ],
        "CAPACITAR 10.000 PERSONAS EN BIENESTAR ANIMAL": [
            "PROMOTORES PYBA",
            "ALIANZAS ACADEMICAS"
        ]
    }

    for nombre_estrategia, comps in componentes_por_estrategia.items():
        estrategia = estrategia_objs.get(nombre_estrategia)
        if not estrategia:
            click.echo(f"⚠ Estrategia no encontrada al crear componentes: {nombre_estrategia}")
            continue

        for comp_name in comps:
            comp = Component.query.filter_by(
                name=comp_name, strategy_id=estrategia.id).first()
            if not comp:
                comp = Component(
                    name=comp_name,
                    description=f"Componente de la estrategia {nombre_estrategia}",
                    strategy_id=estrategia.id,
                    active=True
                )
                db.session.add(comp)
                click.echo(f"🧩 Componente creado: {comp_name}")

        db.session.commit()

    click.echo("🎉 COMPONENTES creados")

    # ======================================================
    # 6️⃣ INDICADORES POR COMPONENTE (CON META ALEATORIA)
    # ======================================================
    indicadores_por_componente = {
        "ASISTENCIA TECNICA": [
            "NO DE ASISTENCIAS TECNICAS REALIZADAS",
            "NO DE CENTROS DE BIENESTAR ANIMAL DOTADOS"
        ],
        "ATENCION EN SALUD ANIMAL COMPAÑERO": [
            "NO DE ANIMALES ATENDIDOS",
            "NO DE ALBERGUES INSPECCIONADOS",
            "NO DE EVENTOS O JORNADAS APOYADAS",
            "NO DE DOCUMENTOS DE LINEAMIENTOS TECNICOS ELABORADOS"
        ],
        "ATENCION PRIMARIA EN SALUD PARA ANIMALES DE PRODUCCION Y GRANJA": [
            "NO DE ANIMALES ATENDIDOS",
            "NO DE EVENTOS O JORNADAS APOYADAS"
        ],
        "PREVENCION EN SALUD DE LA FAUNA LIMINAL Y SILVESTRE": [
            "NO DE ANIMALES ATENDIDOS",
            "NO DE DOCUMENTOS DE LINEAMIENTOS TECNICOS ELABORADOS"
        ],
        "EQUIPO URIA (VETERINARIOS - PSICOLOGO - ABOGADO)": [
            "NO DE ANIMALES ATENDIDOS",
            "NO DE ACOMPAÑAMIENTOS REALIZADOS"
        ],
        "CLÚSTER EMPRESARIAL": [
            "NO DE CLÚSTER REALIZADOS"
        ],
        "AUTOSOSTENIBILIDAD DE REFUGIOS": [
            "NO DE ACTORES COFINANCIADOS"
        ],
        "EMPRENDIMIENTOS CONSCIENTES VALLEINN": [
            "NO DE EMPRENDIMIENTOS COFINANCIADOS"
        ],
        "ALIANZAS ESTRATEGICAS": [
            "NO DE ALIANZAS REALIZADAS"
        ],
        "DONATON SALVANDO HUELLAS": [
            "NO DE REFUGIOS, FUNDACIONES O ACTORES CON ALIMENTO ENTREGADO",
            "N° DE TONELADAS"
        ],
        "RED ANIMALIA": [
            "NO DE ACTORES INSCRITOS Y CARACTERIZADOS DE LA RED ANIMALIA",
            "N° DE REDES CREADAS Y ACOMPAÑADAS"
        ],
        "ACOMPÁÑAMIENTO PSICOSOCIAL": [
            "NO DE ACOMPAÑAMIENTOS REALIZADOS",
            "NO DE CUIDADORES ATENDIDOS"
        ],
        "PROGRAMA DE ADOPCIONES": [
            "N° DE ANIMALES ADOPTADOS",
            "N° DE ASISTENCIAS TÉCNICAS"
        ],
        "JUNTAS DEFENSORAS DE ANIMALES": [
            "NO DE METODOLOGIAS IMPLEMENTADAS"
        ],
        "PROMOTORES PYBA": [
            "NO. DE PERSONAS CAPACITADAS",
            "NO. DE TALLERES CAPACITACIONES FORMACION REALIZADOS",
            "NO. DE ORGANZACIONES DE BASES INTERVENIDAS"
        ],
        "ALIANZAS ACADEMICAS": [
            "NO. DE DOCUMENTOS TECNICOS REALIZADOS",
            "NO. DE EVENTOS REALIZADOS"
        ]
    }

    for comp_name, indicadores in indicadores_por_componente.items():
        componente = Component.query.filter_by(name=comp_name).first()
        if not componente:
            click.echo(f"⚠ Componente no encontrado: {comp_name}")
            continue

        for ind_name in indicadores:
            existe = Indicator.query.filter_by(
                name=ind_name, component_id=componente.id).first()

            if not existe:
                meta_aleatoria = random.randint(10, 500)  # 👈 META ALEATORIA

                nuevo_ind = Indicator(
                    name=ind_name,
                    description=f"Indicador del componente {comp_name}",
                    data_type="integer",
                    component_id=componente.id,
                    active=True,
                    meta=meta_aleatoria  # 👈 SE GUARDA LA META
                )

                db.session.add(nuevo_ind)
                click.echo(f"📊 Indicador creado: {ind_name} (Meta: {meta_aleatoria})")

        db.session.commit()

    click.echo("🎉 INDICADORES creados exitosamente")
    click.echo("🎉 SEED COMPLETO 🚀")
