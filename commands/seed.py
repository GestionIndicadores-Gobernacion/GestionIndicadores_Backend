from flask.cli import with_appcontext
import click
from extensions import db
from models.user import User
from models.role import Role
from models.strategy import Strategy
from models.component import Component
from models.indicator import Indicator
from models.activity import Activity

# =======================================================
# 🔧 Parseo de indicadores con meta
# =======================================================
def parse_indicator(ind):
    """
    Convierte:
      'NOMBRE, 100' → ('NOMBRE', 100)
      'NOMBRE, 100%' → ('NOMBRE', 100)
      'NOMBRE' → ('NOMBRE', 1)
    """
    if "," in ind:
        name, meta = ind.split(",", 1)
        meta = meta.strip().replace("%", "")
        try:
            meta = int(meta)
        except:
            meta = 1
        return name.strip(), meta

    return ind.strip(), 1


# =======================================================
# 1️⃣ ESTRATEGIAS Y ACTIVIDADES (NOMBRES VALIDADOS <150 CHAR)
# =======================================================
ESTRATEGIAS_ACTIVIDADES = {

    "OPERATIVIZAR": [
        "DESARROLLAR LA METODOLOGÍA PARA LA PREVENCIÓN DE LOS RIESGOS DE VIOLENCIAS CONTRA LOS ANIMALES",
        "OPERATIVIZAR EL COMITÉ INTERDISCIPLINARIO PARA ASESORÍA Y ACOMPAÑAMIENTO EN LA POLÍTICA PÚBLICA",
        "IMPLEMENTAR EL OBSERVATORIO DEPARTAMENTAL DE POLÍTICA PÚBLICA DE PROTECCIÓN Y BIENESTAR ANIMAL",
    ],

    "DOTAR TRES CENTROS": [
        "Asesorar técnica y administrativamente los procesos desarrollados por los centros de bienestar animal regional",
        "Dotar los centros de bienestar animal regional con insumos definidos concertadamente",
    ],

    "ATENDER 10.000 ANIMALES": [
        "REALIZAR JORNADAS DE ATENCIÓN INTEGRAL PARA ANIMALES EN ESTADOS VULNERABLES",
        "ELABORAR DIAGNOSTICOS POBLACIONALES PARA IDENTIFICAR ZONAS PRIORITARIAS",
    ],

    "COFINANCIAR A 40 ACTORES": [
        "ACOMPAÑAR TÉCNICAMENTE LAS ACCIONES DE ACTORES QUE PROTEGEN ANIMALES",
        "SUMINISTRAR INSUMOS A LOS ACTORES VOLUNTARIOS",
    ],

    "CREAR Y SOSTENER 3 REDES": [
        "SUMINISTRAR INSUMOS A ACTORES VOLUNTARIOS QUE PROTEGEN ANIMALES",
        "ACOMPAÑAR TÉCNICAMENTE A LOS ACTORES DE LA RED",
    ],

    "CAPACITAR 10.000 PERSONAS EN BIENESTAR ANIMAL": [
        "CAPACITAR A LOS GRUPOS DE INTERÉS EN INCLUSIÓN Y RESPETO HACIA LOS ANIMALES",
        "ELABORAR DIAGNOSTICOS POBLACIONALES",
        "REALIZAR EVENTOS DE PROMOCIÓN DE EXPERIENCIAS EXITOSAS",
    ],
}


# =======================================================
# 2️⃣ COMPONENTES POR ESTRATEGIA (CORREGIDOS Y SIN NOMBRES LARGOS)
# =======================================================
ESTRATEGIA_COMPONENTES = {

    "OPERATIVIZAR": [
        "ANIMALES COMO EMBAJADORES DE PAZ",
        "EQUIPO MULTIDISCIPLINARIO",
        "RUTA DE ATENCION PLATAFORMA DENUNCIAS",
        "PROCESOS DE FORMACION",
        "ENFOQUE DIFERENCIAL",
        "OBSERVATORIO /PLATAFORMA",
    ],

    "DOTAR TRES CENTROS": [
        "ASISTENCIA TECNICA"
    ],

    "ATENDER 10.000 ANIMALES": [
        "ATENCION EN SALUD ANIMAL COMPAÑERO",
        "ATENCION PRIMARIA EN SALUD PARA PRODUCCION Y GRANJA",
        "PREVENCION EN SALUD FAUNA LIMINAL Y SILVESTRE",
        "EQUIPO URIA (VETERINARIOS - PSICOLOGO - ABOGADO)",
    ],

    "COFINANCIAR A 40 ACTORES": [
        "CLÚSTER EMPRESARIAL",
        "AUTOSOSTENIBILIDAD DE REFUGIOS",
        "EMPRENDIMIENTOS CONSCIENTES VALLEINN",
        "ALIANZAS ESTRATEGICAS",
    ],

    "CREAR Y SOSTENER 3 REDES": [
        "DONATON SALVANDO HUELLAS",
        "RED ANIMALIA",
        "ACOMPÁÑAMIENTO PSICOSOCIAL",
        "PROGRAMA DE ADOPCIONES",
        "JUNTAS DEFENSORAS DE ANIMALES",
    ],

    "CAPACITAR 10.000 PERSONAS EN BIENESTAR ANIMAL": [
        "PROMOTORES PYBA",
        "ALIANZAS ACADEMICAS",
    ],
}


# =======================================================
# 3️⃣ INDICADORES POR COMPONENTE
# =======================================================
COMPONENTES_INDICADORES = {

    "ANIMALES COMO EMBAJADORES DE PAZ": [
        "NO DE METODOLOGÍAS IMPLEMENTADAS, 2",
        "NO DE PERSONAS ASISTIDAS, 100%",
    ],

    "EQUIPO MULTIDISCIPLINARIO": [
        "NO DE ASISTENCIAS TECNICAS REALIZADAS, 43",
        "NO DE METODOLOGIAS IMPLEMENTADAS, 1",
        "NO DE ASISTENCIAS TECNICAS REALIZADAS, 100%",
        "NO DE DOCUMENTOS TÉCNICOS Y LINEAMIENTOS REALIZADOS, 1",
    ],

    "RUTA DE ATENCION PLATAFORMA DENUNCIAS": [
        "NO DE CASOS ATENDIDOS, 1000",
        "NO DE CASOS CON SEGUIMIENTO, 100%",
    ],

    "PROCESOS DE FORMACION": [
        "NO DE METODOLOGIA/ NO DE ALTERNATIVAS IMPLEMENTADAS, 1",
        "NO DE JOVENES INSCRITOS EN EL PROGRAMA, 100%",
        "NO GUIAS TURISTICOS CAPACITADOS, 20",
        "CARACTERIZACION DE RED DE TURISMO PETFRIENDLYEN EL VALLE DEL CAUCA, 1",
        "NO DE HERRAMIENTAS IMPLEMENTADAS DE LA METODOLOGIA, 1",
        "NO DE NNA IMPACTADOS, 3000",
    ],

    "ENFOQUE DIFERENCIAL": [
        "NO DE ANIMALES ATENDIDOS ENTORNO A LA RUTA DE VIOLENCIA CONTRA LA MUJER, 100%",
        "NO DE GUIAS NETODOLOGICAS, 1",
        "NO DE METODOLOGIAS IMPLEMENTADAS, 1",
        "NO DE ANIMALES EN EL MARO DEL CONFLICTO ARMADO, 100%",
        "NO DE PERSONAS FORMADAS, 100%",
        "NO DE METODOLOGIAS IMPLEMENTADAS, 1",
    ],

    "OBSERVATORIO /PLATAFORMA": [
        "NO DE PLATAFORMAS IMPLEMENTADAS, 1",
        "NO DE OBSERVATORIOS IMPLEMENTADOS, 1",
    ],

    "ASISTENCIA TECNICA": [
        "NO DE ASISTENCIAS TECNICAS REALIZADAS, 8",
        "NO DE CENTROS DE BIENESTAR ANIMAL DOTADOS, 1",
    ],

    "ATENCION EN SALUD ANIMAL COMPAÑERO": [
        "NO DE ANIMALES ATENDIDOS, 500",
        "NO DE ALBERGUES INSPECCIONADOS, 2500",
    ],

    "ATENCION PRIMARIA EN SALUD PARA PRODUCCION Y GRANJA": [
        "NO DE EVENTOS O JORNADAS APOYADAS, 10",
        "NO DE DOCUMENTOS DE LINEAMIENTOS TECNICOS ELABORADOS, 1",
    ],

    "PREVENCION EN SALUD FAUNA LIMINAL Y SILVESTRE": [
        "NO DE DOCUMENTOS DE LINEAMIENTOS TECNICOS ELABORADOS",
    ],

    "EQUIPO URIA (VETERINARIOS - PSICOLOGO - ABOGADO)": [
        "NO DE ANIMALES ATENDIDOS, 100%",
    ],

    "CLÚSTER EMPRESARIAL": [
        "NO DE CLÚSTER REALIZADOS, 1",
    ],

    "AUTOSOSTENIBILIDAD DE REFUGIOS": [
        "NO DE ACTORES COFINANCIADOS",
    ],

    "EMPRENDIMIENTOS CONSCIENTES VALLEINN": [
        "NO DE EMPRENDIMIENTOS COFINANCIADOS, 30",
    ],

    "ALIANZAS ESTRATEGICAS": [
        "NO DE ALIANZAS RELIZADAS, 5",
    ],

    "DONATON SALVANDO HUELLAS": [
        "NO DE REFUGIOS, FUNDACIONES O ACTORES CON ALIMENTO ENTREGADO, 50",
        "NO DE TONELADAS, 15",
    ],

    "RED ANIMALIA": [
        "NO DE ACOMPAÑAMIENTOS REALIZADOS, 10",
        "NO DE ACTORES INSCRITOS Y CARACTERIZADOS DE LA RED ANIMALIA, 300",
        "NO DE REDES CREADAS Y ACOMPAÑADAS, 3",
    ],

    "ACOMPÁÑAMIENTO PSICOSOCIAL": [
        "NO DE METODOLOGIAS IMPLEMENTADAS, 1",
        "NO DE CUIDADORES ATENDIDOS, 100",
    ],

    "PROGRAMA DE ADOPCIONES": [
        "NO DE ANIMALES ADOPTADOS, 100",
    ],

    "JUNTAS DEFENSORAS DE ANIMALES": [
        "NO DE ASISTENCIAS TÉCNICAS, 5",
    ],

    "PROMOTORES PYBA": [
        "NO. DE PERSONAS CAPACITADAS, 3000",
        "NO. DE TALLERES CAPACITACIONES FORMACION REALIZADOS, 3000",
        "NO. DE ORGANIZACIONES DE BASES INTERVENIDAS, 3000",
        "NO. DE DOCUMENTOS TECNICOS REALIZADOS, 1",
    ],

    "ALIANZAS ACADEMICAS": [
        "NO. DE EVENTOS REALIZADOS, 10",
        "NO. DE EVENTOS REALIZADOS, 4",
    ],
}


# =======================================================
# 🚀 SEED PRINCIPAL
# =======================================================
@click.command("seed")
@with_appcontext
def seed():
    click.echo("🚀 Iniciando SEED...")

    # ----------------------------
    # ROLES
    # ----------------------------
    for r in ["SuperAdmin", "Editor", "Viewer"]:
        if not Role.query.filter_by(name=r).first():
            db.session.add(Role(name=r, description=f"Rol {r}"))
    db.session.commit()

    # ----------------------------
    # SUPERADMIN
    # ----------------------------
    admin = User.query.filter_by(email="admin@gobernacion.gov.co").first()
    if not admin:
        admin = User(name="Administrador Sistema", email="admin@gobernacion.gov.co")
        admin.set_password("Gob2025*")
        db.session.add(admin)

    admin.role_id = Role.query.filter_by(name="SuperAdmin").first().id
    db.session.commit()

    # ----------------------------
    # ESTRATEGIAS + ACTIVIDADES
    # ----------------------------
    estrategia_objs = {}

    for estrategia, actividades in ESTRATEGIAS_ACTIVIDADES.items():
        est = Strategy.query.filter_by(name=estrategia).first()
        if not est:
            est = Strategy(name=estrategia, description=estrategia, active=True)
            db.session.add(est)
        db.session.commit()
        estrategia_objs[estrategia] = est

        for act_desc in actividades:
            if not Activity.query.filter_by(strategy_id=est.id, description=act_desc).first():
                db.session.add(Activity(strategy_id=est.id, description=act_desc, active=True))
        db.session.commit()

    # ----------------------------
    # COMPONENTES + INDICADORES
    # ----------------------------
    for estrategia, comps in ESTRATEGIA_COMPONENTES.items():

        estrategia_obj = estrategia_objs[estrategia]

        for comp_name in comps:
            comp = Component.query.filter_by(name=comp_name, strategy_id=estrategia_obj.id).first()

            if not comp:
                comp = Component(
                    name=comp_name,
                    description=f"Componente {comp_name}",
                    strategy_id=estrategia_obj.id,
                    active=True
                )
                db.session.add(comp)
            db.session.commit()

            # Indicadores
            for ind in COMPONENTES_INDICADORES.get(comp_name, []):
                nombre, meta = parse_indicator(ind)

                if not Indicator.query.filter_by(name=nombre, component_id=comp.id).first():
                    db.session.add(Indicator(
                        name=nombre,
                        description=f"Indicador {nombre}",
                        data_type="integer",
                        component_id=comp.id,
                        active=True,
                        meta=meta
                    ))

            db.session.commit()
            
                # ----------------------------
    # EDITORES (21 USUARIOS)
    # ----------------------------
    editor_role = Role.query.filter_by(name="Editor").first()

    for i in range(1, 22):
        email = f"editor{i}@gov.co"

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                name=f"Editor {i}",
                email=email
            )
            user.set_password("Ed1t0r1*")  # misma que usaste en Postman
            user.role_id = editor_role.id
            db.session.add(user)

    db.session.commit()
    click.echo("👥 21 usuarios Editor creados correctamente")


    click.echo("🎉 SEED COMPLETO Y CORRECTAMENTE AUTOMATIZADO 🚀")
