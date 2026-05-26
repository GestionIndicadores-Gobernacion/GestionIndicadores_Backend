"""Tests de paridad rol vs permiso para endpoints con `dual_required`.

Verifica que la matriz [admin, monitor, editor, viewer] × endpoint dual
produce el mismo veredicto antes y después del Bloque 8/10. Si el bundle
inicial del seeder se desfasara, este test detecta divergencias.
"""
import json

import pytest

from app.core.extensions import db


def _seed(app):
    from app.modules.indicators.commands.seed_permissions import seed_permissions
    result = app.test_cli_runner().invoke(seed_permissions)
    assert result.exit_code == 0, result.output


def _ensure_user(app, role_name, email, password="pw"):
    from app.shared.models.user import User
    from app.shared.models.role import Role
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(first_name="T", last_name="T", email=email, role_id=role.id)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
        return u.id


def _token_for(client, app, role_name):
    """Garantiza usuario con rol, hace login y devuelve access_token."""
    email = f"parity-{role_name}@x.co"
    _ensure_user(app, role_name, email)
    resp = client.post(
        "/auth/login",
        data=json.dumps({"email": email, "password": "pw"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()["access_token"]


# (path, method, allowed_roles)
# Nota PUT D2/D3: el test sólo valida que el rol no permitido reciba 403
# (auth se evalúa ANTES del schema/body), así que enviarlos sin body es OK
# — un 422 para admin sigue cumpliendo "≠ 403". Lo único que prueba es la
# paridad rol↔perm de `dual_required`, no la validación de payload.
DUAL_ENDPOINTS = [
    ("/roles/",                              "GET", {"admin"}),
    ("/roles/1",                             "GET", {"admin"}),
    ("/audit-logs/",                         "GET", {"admin", "monitor"}),
    ("/roles/1/permissions",                 "PUT", {"admin"}),
    ("/users/1/permissions/overrides",       "PUT", {"admin"}),
]


@pytest.mark.parametrize("path,method,allowed", DUAL_ENDPOINTS)
@pytest.mark.parametrize("role", ["admin", "monitor", "editor", "viewer"])
def test_dual_endpoint_matches_role_matrix(app, client, role, path, method, allowed):
    _seed(app)
    token = _token_for(client, app, role)
    fn = getattr(client, method.lower())
    resp = fn(path, headers={"Authorization": f"Bearer {token}"})
    if role in allowed:
        # Cualquier código 2xx o 4xx por datos faltantes (ej. 404) está OK,
        # lo que importa es que NO sea 403.
        assert resp.status_code != 403, (
            f"{role} debería poder acceder a {method} {path} pero recibió 403"
        )
    else:
        assert resp.status_code == 403, (
            f"{role} NO debería poder acceder a {method} {path}, "
            f"pero recibió {resp.status_code}"
        )
