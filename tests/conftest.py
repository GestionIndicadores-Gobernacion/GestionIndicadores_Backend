"""
Fixtures pytest para la app Flask.

✅ Aislamiento total de testing ↔ desarrollo:

- NO tocamos `os.environ`. La BD de tests viene de `TestConfig`
  (literalmente `sqlite:///:memory:`) — es **imposible** que el fixture
  apunte por accidente a PostgreSQL.
- Hay un guard defensivo que aborta el proceso si la URI resultante no
  es SQLite en memoria; cualquier cambio futuro que rompa el aislamiento
  falla ruidoso en lugar de borrar datos.
- `db.drop_all()` solo se ejecuta contra la conexión SQLite efímera del
  proceso de test.
"""

import sys
import pytest


@pytest.fixture(scope="session")
def app():
    # Import tardío: la clase Config se evalúa al importarse, pero
    # TestConfig fija SQLALCHEMY_DATABASE_URI de forma literal y no
    # depende de os.environ.
    from app.core.config import TestConfig
    from app.main import create_app
    from app.core.extensions import db

    # ─── Guard defensivo de aislamiento ─────────────────────────────────
    # Si por cualquier razón (import order, subclase mal hecha, monkey
    # patch) la URI no es SQLite efímera, abortamos el proceso ANTES de
    # crear la app. Preferimos un fallo ruidoso a riesgo de borrar la BD
    # de desarrollo/producción con db.drop_all().
    expected_uri = "sqlite:///:memory:"
    if TestConfig.SQLALCHEMY_DATABASE_URI != expected_uri:
        pytest.exit(
            f"[SEGURIDAD] TestConfig.SQLALCHEMY_DATABASE_URI = "
            f"{TestConfig.SQLALCHEMY_DATABASE_URI!r}; debe ser "
            f"{expected_uri!r}. Abortando para no tocar la BD real.",
            returncode=2,
        )

    flask_app = create_app(TestConfig)

    # Segundo guard, ya con la app creada, sobre la config efectiva.
    effective_uri = flask_app.config.get("SQLALCHEMY_DATABASE_URI")
    if effective_uri != expected_uri:
        pytest.exit(
            f"[SEGURIDAD] app.config['SQLALCHEMY_DATABASE_URI'] = "
            f"{effective_uri!r}; debe ser {expected_uri!r}. Abortando.",
            returncode=2,
        )
    if not flask_app.config.get("TESTING"):
        pytest.exit("[SEGURIDAD] app.config['TESTING'] debe ser True.", returncode=2)

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        # Seguro: el engine está bound a sqlite:///:memory: — drop_all
        # solo afecta a esta instancia efímera, nunca a PostgreSQL.
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _isolate_jwt_blocklist():
    """
    Limpia el set in-memory del blocklist JWT entre tests para que un
    token revocado en un test no afecte al siguiente.
    """
    from app.modules.indicators.services.token_blocklist import clear_all
    clear_all()
    yield
    clear_all()
