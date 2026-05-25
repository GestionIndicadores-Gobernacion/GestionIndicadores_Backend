# RBAC — Roles + Permisos + Overrides

Modelo híbrido para autorización del backend. Coexiste con `role_required`
en **modo dual** durante toda la Fase A/B parcial: la decisión por rol
sigue siendo la autoritativa; los permisos son sombra hasta validar paridad
en producción.

---

## Conceptos

- **Rol** (`roles`): contenedor con nombre + descripción + flag `is_system`.
  Los 4 canónicos (`admin`, `monitor`, `editor`, `viewer`) son `is_system=True`
  y no se pueden eliminar desde la UI admin.
- **Permiso** (`permissions`): code estable de la forma `<modulo>.<accion>[_<scope>]`
  definido en código (`app/shared/permissions/catalog.py`). Solo el equipo de
  desarrollo crea permisos — no la UI.
- **Bundle** (`role_permissions`): conjunto de permisos asociados a un rol.
- **Override por usuario** (`user_permissions`): `effect ∈ {grant, revoke}`
  para personalizar sin clonar roles.

Cálculo del set efectivo:

```
permisos(user) = permisos(user.role) ∪ grants(user) − revokes(user)
```

---

## Catálogo (30 permisos en 10 módulos)

Fuente única: `app/shared/permissions/catalog.py`. Constantes `PERM_*` —
**nunca strings literales** en los checks.

| Módulo | Permisos |
|---|---|
| users | read_basic, read, manage, assign_components, manage_permissions |
| roles | read, manage |
| audit | read |
| strategies | manage |
| components | manage |
| strategy_metrics | manage |
| public_policies | manage |
| datasets | read, manage, import |
| reports | create, read, update_own, update_any, delete_own, delete_any |
| action_plans | create, read, update_own, update_any, delete_own, delete_any, report_activity, add_evidence, dashboard |

Validaciones que corren al importar el módulo (fail-fast):
- Codes únicos.
- Módulos válidos.
- Constante ↔ entrada en `ALL_PERMISSIONS` sincronizadas en ambos sentidos.
- Codes cumplen la convención `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$`.

---

## Bundles iniciales

Se aplican vía `flask seed_permissions`. **Solo si el rol está vacío** —
no sobrescriben ediciones admin posteriores.

| Rol | # | Resumen |
|---:|---:|---|
| admin | 30 | todo |
| monitor | 14 | lectura amplia, reports, action_plans, dashboard |
| editor | 12 | escritura scoped en reports y action_plans + datasets.read |
| viewer | 1 | `reports.read` |

---

## API para developers

### Decoradores

```python
from app.utils.permissions import dual_required, require_permission
from app.shared.permissions import PERM_REPORTS_CREATE

@dual_required(roles=("admin","monitor","editor"), perms=(PERM_REPORTS_CREATE,))
def post(self, data):
    ...
```

- `dual_required(*, roles=(), perms=(), all_perms=False)` —
  el decorador estándar. Computa decisión por rol y por permisos; loguea
  divergencias si `PERM_SHADOW_MODE` está activo; devuelve 403 según
  la decisión autoritativa (rol-based mientras Fase A/B parcial siga).
- `require_permission(*codes, all_of=False)` — chequeo puro por permisos,
  útil cuando ya no se quiera dual mode. Hoy no se usa en endpoints.

### Evaluadores

```python
from app.utils.permissions import (
    current_user_permissions,  # set[str], cacheado por request
    has_permission,            # bool
    has_any_permission,
    has_all_permissions,
    current_user,              # User cargado eager + cacheado
    is_admin, is_viewer,       # checks por rol (cuando ownership los exige)
)
```

### Invariantes

```python
from app.utils.rbac_invariants import (
    RBACInvariantError,
    assert_can_delete_role,
    assert_can_modify_user_permissions,
    assert_can_change_user_role,
    CRITICAL_PERMISSIONS,
)
```

Lanzan `RBACInvariantError` si la operación rompe alguna regla operacional
(borrar rol del sistema, revocar permisos críticos al main admin,
auto-degradación).

---

## JWT y respuestas API

- **Login** y **refresh** emiten claim `permissions: list[str]` además
  de `role_id` y `role`.
- `/users/me` y la response de login incluyen `user.permissions` para el
  usuario activo.
- `/users/` list devuelve `permissions: null` para usuarios ajenos (sin leak).
- **JWT viejo sin claim** sigue siendo aceptado: el evaluador hace fallback
  a BD (`current_user_permissions` lo gestiona).
- **Nuevo endpoint** `GET /users/me/permissions` → `{ role, permissions }`
  para refrescar el set sin reemitir tokens.

---

## Shadow mode

`PERM_SHADOW_MODE` (env var, default `false` en prod). Cuando está activo:

- Cada llamada a `dual_required` compara la decisión por rol vs la decisión
  por permiso.
- Si divergen, se emite:

```
RBAC_SHADOW_DIVERGENCE endpoint=<...> user_id=<n> role=<name>
  role_allows=<bool> perm_allows=<bool> expected_roles=<...> expected_perms=<...>
```

- La respuesta HTTP NO cambia — la decisión rol-based sigue siendo
  autoritativa durante Fase A/B parcial.

Procedimiento para retirar `role_required`:
1. Activar shadow mode en staging.
2. Correr suite + tráfico real durante 24-48h.
3. Cero divergencias → cambiar `dual_required` para hacer autoritativa la
   decisión por permisos.
4. Eliminar `role_required` y reemplazar todas las llamadas.

---

## Cómo agregar un permiso nuevo

1. Editar `app/shared/permissions/catalog.py`:
   - Agregar constante `PERM_X = "modulo.accion"`.
   - Agregar entrada `PermissionDef(PERM_X, "...", MODULE_X)`.
2. Re-exportar la constante en `app/shared/permissions/__init__.py`.
3. Correr `pytest tests/test_permissions_catalog.py` — falla si hay typos.
4. Correr `flask seed_permissions` → upsert idempotente. El permiso queda
   en BD pero sin asignar a roles (decisión consciente, no autoasignar).
5. Asignar manualmente desde la UI admin (Fase D) o vía script si urgente.
6. Usar `PERM_X` en `dual_required(perms=(PERM_X,))` o en checks inline.

---

## Cómo agregar un rol custom

1. Crear rol vía UI admin (Fase D) o SQL: `INSERT INTO roles(name,is_system) VALUES ('contractor', false)`.
2. Asignarle permisos desde la UI admin.
3. Crear/editar usuarios con ese rol.

Los roles `is_system=true` (admin, monitor, editor, viewer) no se pueden
eliminar — el invariante `assert_can_delete_role` lo bloquea.

---

## Cache por request

- `current_user`, `current_user_permissions`, `has_permission` están
  cacheados en `flask.g` por user_id.
- Eager-load consolidado: 3 queries máximo para cargar user + role +
  role_permissions + permission_overrides.
- Tests verifican que un endpoint con múltiples `has_permission` no
  dispara más de 1 SELECT a `users`.

---

## Tests asociados

| Archivo | Cubre |
|---|---|
| `test_permissions_catalog.py` | Catálogo: unicidad, módulos válidos, sincronización constantes |
| `test_seed_permissions.py` | Seeder: idempotencia, monitor auto, no overwrite, orphans |
| `test_permissions_evaluator.py` | Evaluador: matriz role × overrides, cache, JWT vs BD |
| `test_auth_permissions_claim.py` | Login/refresh emiten claim; UserSchema.permissions; compat JWT viejo |
| `test_users_me_permissions.py` | Endpoint `/users/me/permissions` |
| `test_dual_required_parity.py` | Paridad rol vs permiso en endpoints duales |
| `test_rbac_invariants.py` | is_main_admin, bloqueo borrar roles, auto-degradación |
| `test_shadow_mode.py` | Telemetría de divergencias rol vs permiso |
