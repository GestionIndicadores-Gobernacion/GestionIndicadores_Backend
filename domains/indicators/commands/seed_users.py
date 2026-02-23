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
        },
        # ===================================================
        # USUARIOS NUEVOS — ROL EDITOR
        # ===================================================
        {
            "first_name": "María Cristina",
            "last_name": "Londoño Alzate",
            "email": "mcristinalondono@hotmail.com",
            "password": "66725313",
            "role": "editor"
        },
        {
            "first_name": "Angi Tatiana",
            "last_name": "Silva Hurtado",
            "email": "angitsh2305@hotmail.com",
            "password": "1143843843",
            "role": "editor"
        },
        {
            "first_name": "Steven Alejandro",
            "last_name": "Murillo Muñoz",
            "email": "stevenmurillo0516@gmail.com",
            "password": "1005969075",
            "role": "editor"
        },
        {
            "first_name": "Lina María",
            "last_name": "Vega Guerrero",
            "email": "linavega217@gmail.com",
            "password": "38670140",
            "role": "editor"
        },
        {
            "first_name": "Ana María",
            "last_name": "González Rojas",
            "email": "gonzalezrojasanamaria118@gmail.com",
            "password": "1113036799",
            "role": "editor"
        },
        {
            "first_name": "Daniel Sebastian",
            "last_name": "Zuñiga Bohorquez",
            "email": "danielsvale15@gmail.com",
            "password": "1144077625",
            "role": "editor"
        },
        {
            "first_name": "Santiago",
            "last_name": "Coral Zuñiga",
            "email": "santiago.cz20@gmail.com",
            "password": "1144067024",
            "role": "editor"
        },
        {
            "first_name": "María Magdalena",
            "last_name": "Perlaza Arredondo",
            "email": "magdalenaarredo@gmail.com",
            "password": "30399696",
            "role": "editor"
        },
        {
            "first_name": "Sandra",
            "last_name": "Ricaurte Gomez",
            "email": "sanricaurte_19@hotmail.com",
            "password": "66829743",
            "role": "editor"
        },
        {
            "first_name": "Heidy",
            "last_name": "Diaz Mora",
            "email": "heidydice@yahoo.com",
            "password": "31932528",
            "role": "editor"
        },
        {
            "first_name": "Yinela",
            "last_name": "Zapata",
            "email": "yinelazm@gmail.com",
            "password": "1116448352",
            "role": "editor"
        },
        {
            "first_name": "Mayra Yadira",
            "last_name": "Serna Riascos",
            "email": "mairayadira20@gmail.com",
            "password": "1130607021",
            "role": "editor"
        },
        {
            "first_name": "Juan José",
            "last_name": "Olave Campo",
            "email": "juanjolavecampo@gmail.com",
            "password": "1335280909",
            "role": "editor"
        },
        {
            "first_name": "Erik Daniel",
            "last_name": "Estrada Castro",
            "email": "erikdaniel940615@hotmail.com",
            "password": "1116263429",
            "role": "editor"
        },
        {
            "first_name": "Cesar Augusto",
            "last_name": "Varela Giron",
            "email": "cvarela@valledelcauca.gov.co",
            "password": "1114210695",
            "role": "editor"
        },
        {
            "first_name": "Daniela",
            "last_name": "Jiménez Zarta",
            "email": "danielagram35@gmail.com",
            "password": "1143861015",
            "role": "editor"
        },
        {
            "first_name": "María Fernanda",
            "last_name": "Arbelaez Valencia",
            "email": "arbelaezvalenciamariafernanda@gmail.com",
            "password": "29832260",
            "role": "editor"
        },
        {
            "first_name": "Jhon Mauricio",
            "last_name": "Rodríguez Gallego",
            "email": "mauroneruda72@gmail.com",
            "password": "1116263765",
            "role": "editor"
        },
        {
            "first_name": "Jakeline",
            "last_name": "Espinal Vargas",
            "email": "jakelineespinal78@hotmail.com",
            "password": "29873758",
            "role": "editor"
        },
        {
            "first_name": "Erika Alejandra",
            "last_name": "Rodríguez Jaramillo",
            "email": "erikarodriguezjaramillo@gmail.com",
            "password": "1053801387",
            "role": "editor"
        },
        {
            "first_name": "Diana Fernanda",
            "last_name": "Ortega Borja",
            "email": "dianaortega1997@gmail.com",
            "password": "1113538042",
            "role": "editor"
        },
        {
            "first_name": "Andres Mauricio",
            "last_name": "Gómez Obando",
            "email": "amgo252002@gmail.com",
            "password": "1006433668",
            "role": "editor"
        },
        {
            "first_name": "Mónica Liliana",
            "last_name": "Andrade Dirak",
            "email": "andradedirakmonica74@gmai.com",
            "password": "66928934",
            "role": "editor"
        },
        {
            "first_name": "Cristian Alejandro",
            "last_name": "Estrada Ruiz",
            "email": "cristianestradamovil@gmail.com",
            "password": "1085324643",
            "role": "editor"
        },
        {
            "first_name": "Maria Alejandra",
            "last_name": "Benitez Ruiz",
            "email": "mabenitez@valledelcauca.gov.co",
            "password": "1127351336",
            "role": "editor"
        },
        {
            "first_name": "Isabel Cristina",
            "last_name": "Fory Cordoba",
            "email": "isaforycordoba@gmail.com",
            "password": "1010077355",
            "role": "editor"
        },
        {
            "first_name": "Maryeli Eunice",
            "last_name": "Perez Caicedo",
            "email": "maryeliperez3467@gmail.com",
            "password": "34675793",
            "role": "editor"
        },
        {
            "first_name": "Ramón",
            "last_name": "Taborda Ocampo",
            "email": "rnto5824@gmail.com",
            "password": "16262314",
            "role": "editor"
        },
        {
            "first_name": "Estefania",
            "last_name": "Patiño Valencia",
            "email": "estefania2218@gmail.com",
            "password": "1151943208",
            "role": "editor"
        },
        {
            "first_name": "Sandra Patricia",
            "last_name": "Perez",
            "email": "sandris2101@gmail.com",
            "password": "1130669601",
            "role": "editor"
        },
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
