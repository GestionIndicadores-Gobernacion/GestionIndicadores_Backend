"""Tests del shadow mode (Bloque 12).

Verifican:
- Cuando PERM_SHADOW_MODE es True y rol/permiso divergen → log warning.
- Cuando coinciden → no se loguea.
- Cuando PERM_SHADOW_MODE es False → nunca se loguea (default prod).
- La decisión efectiva sigue siendo la del rol (legacy autoritativo)
  durante todo el shadow mode.
"""
import logging
import json

import pytest

from app.core.extensions import db


def _seed(app):
    from app.modules.indicators.commands.seed_permissions import seed_permissions
    result = app.test_cli_runner().invoke(seed_permissions)
    assert result.exit_code == 0, result.output


def _make_user(app, role_name, email):
    from app.shared.models.user import User
    from app.shared.models.role import Role
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(first_name="T", last_name="T", email=email, role_id=role.id)
            u.set_password("pw")
            db.session.add(u)
            db.session.commit()
        return u.id


def _force_divergence(app, role_name, perm_code, expected_state):
    """Modifica el bundle del rol para que rol vs permiso difieran.

    `expected_state='has'` → asegura que el rol tiene el permiso.
    `expected_state='lacks'` → asegura que el rol NO tiene el permiso.
    """
    from app.shared.models.role import Role
    from app.shared.models.permission import Permission
    from app.shared.models.role_permission import RolePermission
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        perm = Permission.query.filter_by(code=perm_code).first()
        existing = RolePermission.query.filter_by(
            role_id=role.id, permission_id=perm.id,
        ).first()
        if expected_state == "has" and existing is None:
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
            db.session.commit()
        elif expected_state == "lacks" and existing is not None:
            db.session.delete(existing)
            db.session.commit()


def test_shadow_log_emitted_on_divergence(app, client, caplog):
    """Configuramos: monitor SIN audit.read en BD.
    El endpoint /audit-logs/ requiere rol 'admin' y permiso 'audit.read'.
    Como monitor no es admin, role_decision=False.
    Si forzáramos perm_decision=True para monitor, habría divergencia.
    Pero más simple: usar admin SIN 'audit.read' en BD.
    """
    _seed(app)
    # Admin debería tener audit.read en bundle inicial.
    # Para forzar divergencia, le QUITAMOS audit.read del bundle:
    _force_divergence(app, "admin", "audit.read", "lacks")
    uid = _make_user(app, "admin", "shadow-admin@x.co")

    # Activamos shadow mode en runtime.
    app.config["PERM_SHADOW_MODE"] = True

    from flask_jwt_extended import create_access_token
    with app.app_context():
        # Token SIN claim permissions → fallback a BD para perm decision.
        token = create_access_token(identity=str(uid))

    with caplog.at_level(logging.WARNING, logger=app.logger.name):
        resp = client.get(
            "/audit-logs/",
            headers={"Authorization": f"Bearer {token}"},
        )

    # role_decision=True (admin role), perm_decision=False (sin audit.read)
    # → divergencia, log WARNING emitido.
    divergence_logs = [
        r for r in caplog.records
        if "RBAC_SHADOW_DIVERGENCE" in r.getMessage()
    ]
    assert divergence_logs, (
        f"Esperaba log de divergencia. caplog={[r.getMessage() for r in caplog.records]}"
    )
    # Decisión efectiva sigue siendo role-based: admin → 200 (no 403).
    assert resp.status_code in (200, 404), resp.get_data(as_text=True)

    # Restauramos el bundle para no afectar tests siguientes.
    _force_divergence(app, "admin", "audit.read", "has")


def test_shadow_log_NOT_emitted_when_disabled(app, client, caplog):
    _seed(app)
    _force_divergence(app, "admin", "audit.read", "lacks")
    uid = _make_user(app, "admin", "shadow-disabled@x.co")

    app.config["PERM_SHADOW_MODE"] = False

    from flask_jwt_extended import create_access_token
    with app.app_context():
        token = create_access_token(identity=str(uid))

    with caplog.at_level(logging.WARNING, logger=app.logger.name):
        client.get(
            "/audit-logs/",
            headers={"Authorization": f"Bearer {token}"},
        )

    divergence_logs = [
        r for r in caplog.records
        if "RBAC_SHADOW_DIVERGENCE" in r.getMessage()
    ]
    assert not divergence_logs, (
        f"Shadow mode OFF, no debería loguear. Logs: "
        f"{[r.getMessage() for r in divergence_logs]}"
    )
    _force_divergence(app, "admin", "audit.read", "has")


def test_shadow_log_NOT_emitted_when_parity(app, client, caplog):
    """Si bundle coincide con rol esperado, no hay divergencia."""
    _seed(app)
    # Asegura bundle correcto.
    _force_divergence(app, "admin", "audit.read", "has")
    uid = _make_user(app, "admin", "shadow-parity@x.co")

    app.config["PERM_SHADOW_MODE"] = True

    from flask_jwt_extended import create_access_token
    with app.app_context():
        token = create_access_token(identity=str(uid))

    with caplog.at_level(logging.WARNING, logger=app.logger.name):
        client.get(
            "/audit-logs/",
            headers={"Authorization": f"Bearer {token}"},
        )

    divergence_logs = [
        r for r in caplog.records
        if "RBAC_SHADOW_DIVERGENCE" in r.getMessage()
    ]
    assert not divergence_logs, "Sin divergencia, no debería loguear nada"

    app.config["PERM_SHADOW_MODE"] = False
