from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from extensions import db
from domains.indicators.models.PublicPolicy.public_policy import PublicPolicy
from domains.indicators.schemas.public_policy_schema import PublicPolicySchema

blp = Blueprint(
    "public_policies",
    "public_policies",
    url_prefix="/public-policies",
    description="Public policy management"
)

# ─────────────────────────────────────────────────────────────────
# Las 29 acciones de la política pública de protección Animal
# Úsalas para hacer el seed inicial con: flask seed-public-policies
# ─────────────────────────────────────────────────────────────────
PUBLIC_POLICIES_SEED = [
    ("1.1",  "Implementar guías pedagógicas para los procesos educativos y de crianza que promuevan el reconocimiento y la inclusión de los Animales desde la visión del respeto y el reconocimiento como seres sintientes."),
    ("1.2",  "Implementar guías metodológicas para la transversalidad del respeto y el reconocimiento de los Animales como seres sintientes en procesos, políticas, planes, programas y proyectos del Departamento del Valle del Cauca."),
    ("1.3",  "Desarrollar procesos de formación que promuevan el reconocimiento y la inclusión de los Animales como seres sintientes."),
    ("1.4",  "Cualificar a los equipos de comunicación de diferentes sectores en temas de no violencia contra los Animales desde la visión del respeto y el reconocimiento como seres sintientes, en los Municipios y distritos del Valle del Cauca."),
    ("1.5",  "Asistir técnicamente a los entes territoriales para la creación e implementación de acciones en los Planes de Desarrollo y Plan de Ordenamiento Territorial en acciones que permitan fomentar el respeto y el reconocimiento de los Animales como seres sintientes."),
    ("1.6",  "Desarrollar espacios de discusión académica sobre la importancia de incluir la visión del respeto y el reconocimiento de los Animales como seres sintientes en las carreras profesionales y técnicas."),
    ("1.7",  "Desarrollar acciones artísticas y culturales masivas en espacios públicos con enfoque de reconocimiento e inclusión de los Animales como seres sintientes para la promoción de una cultura donde predomine el respeto."),
    ("1.8",  "Desarrollar campañas comunicativas masivas que promuevan el respeto y reconocimiento de los Animales como seres sintientes en los diferentes grupos poblacionales."),
    ("1.9",  "Fortalecer organizativamente las redes empresariales de productos y servicios conscientes."),
    ("1.10", "Fomentar los emprendimientos conscientes de las empresas enfocadas en la protección, el bienestar Animal, el turismo comunitario y de naturaleza, presentadas en las convocatorias de emprendimiento y demás programas que lo modifiquen, adicionen o sustituyan."),
    ("2.1",  "Implementar el observatorio Departamental de Protección y Bienestar Animal."),
    ("2.2",  "Realización de estudios diagnósticos y de caracterización de temas de interés de la Política Pública."),
    ("2.3",  "Implementar lineamientos para transversalizar el respeto y el reconocimiento de los Animales como seres sintientes a sectores de interés de la Política Pública."),
    ("2.4",  "Prevenir escenarios de riesgos y desastres para poblaciones silvestres, sinantrópicas o liminales, y domesticadas."),
    ("2.5",  "Fomentar espacios de discusión, con actores de interés, para la generación de alternativas de sustitución de la experimentación con Animales."),
    ("2.6",  "Asistir técnicamente en buenas prácticas, que prioricen la salud y el bienestar Animal, a los actores que hacen inspección, vigilancia y control a la cadena de comercialización, producción, reproducción, levante, transporte y sacrificio de los Animales Domesticados y los usados para el consumo."),
    ("2.7",  "Cualificar a los actores de las rutas de atención de los Animales, en la normatividad, jurisprudencia y lineamientos legales de protección Animal y su implementación."),
    ("2.8",  "Implementar metodologías y contenidos para sensibilizar los grupos de interés de la Política Pública, para la prevención de los riesgos de violencias contra los Animales."),
    ("2.9",  "Implementar un protocolo desde la visión del respeto y reconocimiento de los Animales como seres sintientes en los hogares de paso de habitante de calle y adulto mayor."),
    ("2.10", "Realizar jornadas integrales de salud Animal, que incluya esterilizaciones gratuitas, revisión general veterinaria, vacunación, desparasitación y vitaminización para los Animales ubicados en los estratos socioeconómicos más vulnerables en zonas urbanas y rurales o en situación de abandono."),
    ("2.11", "Implementar acciones para el fortalecimiento para la incidencia efectiva de las Juntas de Protección Animal."),
    ("3.1",  "Asistir técnicamente a las entidades territoriales y a los sectores de interés, para integrar la transversalidad desde la visión del respeto y reconocimiento de los Animales como seres sintientes."),
    ("3.2",  "Implementar programas de formación integral en temas de protección, bienestar Animal y de transversalidad desde la visión del respeto y reconocimiento de los Animales como seres sintientes."),
    ("3.3",  "Caracterizar las necesidades específicas de atención oportuna en los casos de fauna silvestre, desde la visión del respeto y reconocimiento de los Animales como seres sintientes."),
    ("3.4",  "Implementar lineamientos para la prevención del riesgo y de las violencias contra los Animales en la atención en situaciones de coyuntura y de las dinámicas culturales con enfoque territorial en los Municipios y Distritos."),
    ("3.5",  "Implementar el sistema de alertas tempranas de protección Animal."),
    ("3.6",  "Promover la creación un organismo técnico, encargado de liderar los temas de promoción, prevención, atención, articulación y seguimiento interinstitucional frente a las violencias contra los Animales y de la implementación de la Política Pública de protección Animal del Departamento del Valle del Cauca."),
    ("3.7",  "Implementar una propuesta Departamental de adopción responsable de Animales domesticados a través de la plataforma protección Animal de la Gobernación del Valle del Cauca."),
    ("3.8",  "Promover la creación de un grupo interdisciplinario, con saberes jurídicos, sociales y médico veterinario, para la asesoría y acompañamiento, a las entidades gubernamentales y organizaciones sociales y comunidad, en la aplicación de la ruta de atención a casos de maltrato Animal y realice el seguimiento a estos casos para la garantía de la protección y bienestar Animal."),
]


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@blp.route("/")
class PublicPolicyListResource(MethodView):

    @jwt_required()
    @blp.response(200, PublicPolicySchema(many=True))
    def get(self):
        """Listar todas las políticas públicas."""
        return PublicPolicy.query.order_by(PublicPolicy.code).all()

    @jwt_required()
    @blp.arguments(PublicPolicySchema)
    @blp.response(201, PublicPolicySchema)
    def post(self, data):
        """Crear una política pública."""
        existing = PublicPolicy.query.filter_by(code=data["code"]).first()
        if existing:
            return {"errors": {"code": "A policy with this code already exists"}}, 400

        policy = PublicPolicy(code=data["code"], description=data["description"])
        db.session.add(policy)
        db.session.commit()
        return policy


@blp.route("/<int:policy_id>")
class PublicPolicyResource(MethodView):

    @jwt_required()
    @blp.response(200, PublicPolicySchema)
    def get(self, policy_id):
        """Obtener una política pública por ID."""
        policy = PublicPolicy.query.get(policy_id)
        if not policy:
            return {"message": "Public policy not found"}, 404
        return policy

    @jwt_required()
    @blp.arguments(PublicPolicySchema)
    @blp.response(200, PublicPolicySchema)
    def put(self, data, policy_id):
        """Actualizar una política pública."""
        policy = PublicPolicy.query.get(policy_id)
        if not policy:
            return {"message": "Public policy not found"}, 404

        # Verificar unicidad del código si cambió
        if data["code"] != policy.code:
            existing = PublicPolicy.query.filter_by(code=data["code"]).first()
            if existing:
                return {"errors": {"code": "A policy with this code already exists"}}, 400

        policy.code        = data["code"]
        policy.description = data["description"]
        db.session.commit()
        return policy

    @jwt_required()
    @blp.response(204)
    def delete(self, policy_id):
        """Eliminar una política pública."""
        policy = PublicPolicy.query.get(policy_id)
        if not policy:
            return {"message": "Public policy not found"}, 404

        db.session.delete(policy)
        db.session.commit()


# ─────────────────────────────────────────────────────────────────
# CLI COMMAND: flask seed-public-policies
# Registrarlo en app.py o donde configures los comandos CLI:
#
#   from domains.indicators.routes.public_policy_routes import seed_public_policies_command
#   app.cli.add_command(seed_public_policies_command)
# ─────────────────────────────────────────────────────────────────

import click
from flask.cli import with_appcontext


@click.command("seed-public-policies")
@with_appcontext
def seed_public_policies_command():
    """Inserta las 29 acciones de la política pública si no existen."""
    inserted = 0
    for code, description in PUBLIC_POLICIES_SEED:
        exists = PublicPolicy.query.filter_by(code=code).first()
        if not exists:
            db.session.add(PublicPolicy(code=code, description=description))
            inserted += 1

    db.session.commit()
    click.echo(f"✅  Seed completado: {inserted} políticas insertadas ({len(PUBLIC_POLICIES_SEED) - inserted} ya existían).")