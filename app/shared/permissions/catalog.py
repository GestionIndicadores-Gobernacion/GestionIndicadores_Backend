"""Catálogo canónico de permisos del sistema RBAC.

Esta es la **única fuente de verdad** para qué permisos existen. Todo
chequeo del backend usa las constantes `PERM_*` definidas aquí (nunca
strings literales). El comando `flask seed_permissions` (Bloque 4) hace
upsert en la tabla `permissions` a partir de este catálogo.

Reglas de diseño:
- Los `code` son estables, cortos, en minúsculas, formato `<modulo>.<accion>`
  o `<modulo>.<accion>_<scope>`. Cambiar un code después de haberse
  publicado rompe JWTs vigentes, logs, auditoría y eventual config en
  frontend — tratar como contrato público.
- Granularidad CRUD + manage + scope (`_own`/`_any`) cuando aplica.
  Evitar permisos visuales (botones/modales) o por sub-operación.
- Las descripciones son legibles para humanos — sirven a la UI admin.
- El módulo agrupa para la UI y para razonamiento mental; no tiene
  semántica de runtime.

Validaciones automáticas (corren al importar el módulo):
- No hay codes duplicados.
- Cada entrada tiene `module` válido.
- Cada constante `PERM_*` corresponde a una entrada (sin huérfanos).
- Cada entrada del catálogo tiene su constante (sin desincronización).

Permisos huérfanos en BD (filas en `permissions` cuyo code ya no está
aquí) se detectan en el seeder, no en este módulo.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple


# ── Módulos (constantes para evitar typos en `module=` de cada entrada) ──
MODULE_USERS             = "users"
MODULE_ROLES             = "roles"
MODULE_AUDIT             = "audit"
MODULE_STRATEGIES        = "strategies"
MODULE_COMPONENTS        = "components"
MODULE_STRATEGY_METRICS  = "strategy_metrics"
MODULE_PUBLIC_POLICIES   = "public_policies"
MODULE_DATASETS          = "datasets"
MODULE_REPORTS           = "reports"
MODULE_ACTION_PLANS      = "action_plans"

ALL_MODULES: frozenset[str] = frozenset({
    MODULE_USERS,
    MODULE_ROLES,
    MODULE_AUDIT,
    MODULE_STRATEGIES,
    MODULE_COMPONENTS,
    MODULE_STRATEGY_METRICS,
    MODULE_PUBLIC_POLICIES,
    MODULE_DATASETS,
    MODULE_REPORTS,
    MODULE_ACTION_PLANS,
})


@dataclass(frozen=True)
class PermissionDef:
    """Definición declarativa de un permiso en el catálogo."""
    code: str
    description: str
    module: str


# ── Constantes PERM_* — todo el backend debe importar desde aquí ─────────
# users
PERM_USERS_READ_BASIC           = "users.read_basic"
PERM_USERS_READ                 = "users.read"
PERM_USERS_MANAGE               = "users.manage"
PERM_USERS_ASSIGN_COMPONENTS    = "users.assign_components"
PERM_USERS_MANAGE_PERMISSIONS   = "users.manage_permissions"

# roles
PERM_ROLES_READ                 = "roles.read"
PERM_ROLES_MANAGE               = "roles.manage"

# audit
PERM_AUDIT_READ                 = "audit.read"

# strategies / components / metrics / public_policies
# (solo escritura — lectura permanece abierta a todo autenticado por ahora)
PERM_STRATEGIES_MANAGE          = "strategies.manage"
PERM_COMPONENTS_MANAGE          = "components.manage"
PERM_STRATEGY_METRICS_MANAGE    = "strategy_metrics.manage"
PERM_PUBLIC_POLICIES_MANAGE     = "public_policies.manage"

# datasets
PERM_DATASETS_READ              = "datasets.read"
PERM_DATASETS_MANAGE            = "datasets.manage"
PERM_DATASETS_IMPORT            = "datasets.import"

# reports
PERM_REPORTS_CREATE             = "reports.create"
PERM_REPORTS_READ               = "reports.read"
PERM_REPORTS_UPDATE_OWN         = "reports.update_own"
PERM_REPORTS_UPDATE_ANY         = "reports.update_any"
PERM_REPORTS_DELETE_OWN         = "reports.delete_own"
PERM_REPORTS_DELETE_ANY         = "reports.delete_any"

# action_plans
PERM_ACTION_PLANS_CREATE            = "action_plans.create"
PERM_ACTION_PLANS_READ              = "action_plans.read"
PERM_ACTION_PLANS_UPDATE_OWN        = "action_plans.update_own"
PERM_ACTION_PLANS_UPDATE_ANY        = "action_plans.update_any"
PERM_ACTION_PLANS_DELETE_OWN        = "action_plans.delete_own"
PERM_ACTION_PLANS_DELETE_ANY        = "action_plans.delete_any"
PERM_ACTION_PLANS_REPORT_ACTIVITY   = "action_plans.report_activity"
PERM_ACTION_PLANS_ADD_EVIDENCE      = "action_plans.add_evidence"
PERM_ACTION_PLANS_DASHBOARD         = "action_plans.dashboard"


# ── Catálogo canónico ────────────────────────────────────────────────────
# El orden refleja el orden de presentación esperado en la UI admin.
ALL_PERMISSIONS: Tuple[PermissionDef, ...] = (
    # users
    PermissionDef(PERM_USERS_READ_BASIC,         "Listar usuarios con datos mínimos (para selects)", MODULE_USERS),
    PermissionDef(PERM_USERS_READ,               "Ver datos completos de usuarios",                  MODULE_USERS),
    PermissionDef(PERM_USERS_MANAGE,             "Crear, editar y desactivar usuarios",              MODULE_USERS),
    PermissionDef(PERM_USERS_ASSIGN_COMPONENTS,  "Asignar componentes a usuarios",                   MODULE_USERS),
    PermissionDef(PERM_USERS_MANAGE_PERMISSIONS, "Otorgar y revocar permisos a usuarios",            MODULE_USERS),

    # roles
    PermissionDef(PERM_ROLES_READ,               "Listar y ver roles",                               MODULE_ROLES),
    PermissionDef(PERM_ROLES_MANAGE,             "Crear, editar y eliminar roles",                   MODULE_ROLES),

    # audit
    PermissionDef(PERM_AUDIT_READ,               "Ver el historial de auditoría",                    MODULE_AUDIT),

    # strategies
    PermissionDef(PERM_STRATEGIES_MANAGE,        "Crear, editar y eliminar estrategias",             MODULE_STRATEGIES),

    # components
    PermissionDef(PERM_COMPONENTS_MANAGE,        "Crear, editar y eliminar componentes",             MODULE_COMPONENTS),

    # strategy_metrics
    PermissionDef(PERM_STRATEGY_METRICS_MANAGE,  "Crear, editar y eliminar métricas de estrategia",  MODULE_STRATEGY_METRICS),

    # public_policies
    PermissionDef(PERM_PUBLIC_POLICIES_MANAGE,   "Crear, editar y eliminar políticas públicas",      MODULE_PUBLIC_POLICIES),

    # datasets
    PermissionDef(PERM_DATASETS_READ,            "Leer datasets y tablas",                            MODULE_DATASETS),
    PermissionDef(PERM_DATASETS_MANAGE,          "Crear, editar y eliminar datasets/tablas",          MODULE_DATASETS),
    PermissionDef(PERM_DATASETS_IMPORT,          "Importar datasets desde Excel",                     MODULE_DATASETS),

    # reports
    PermissionDef(PERM_REPORTS_CREATE,           "Crear reportes",                                    MODULE_REPORTS),
    PermissionDef(PERM_REPORTS_READ,             "Listar y leer reportes",                            MODULE_REPORTS),
    PermissionDef(PERM_REPORTS_UPDATE_OWN,       "Editar los reportes propios",                       MODULE_REPORTS),
    PermissionDef(PERM_REPORTS_UPDATE_ANY,       "Editar cualquier reporte",                          MODULE_REPORTS),
    PermissionDef(PERM_REPORTS_DELETE_OWN,       "Eliminar los reportes propios",                     MODULE_REPORTS),
    PermissionDef(PERM_REPORTS_DELETE_ANY,       "Eliminar cualquier reporte",                        MODULE_REPORTS),

    # action_plans
    PermissionDef(PERM_ACTION_PLANS_CREATE,          "Crear planes de acción",                       MODULE_ACTION_PLANS),
    PermissionDef(PERM_ACTION_PLANS_READ,            "Listar y leer planes de acción",               MODULE_ACTION_PLANS),
    PermissionDef(PERM_ACTION_PLANS_UPDATE_OWN,      "Editar planes de acción propios",              MODULE_ACTION_PLANS),
    PermissionDef(PERM_ACTION_PLANS_UPDATE_ANY,      "Editar cualquier plan de acción",              MODULE_ACTION_PLANS),
    PermissionDef(PERM_ACTION_PLANS_DELETE_OWN,      "Eliminar planes de acción propios",            MODULE_ACTION_PLANS),
    PermissionDef(PERM_ACTION_PLANS_DELETE_ANY,      "Eliminar cualquier plan de acción",            MODULE_ACTION_PLANS),
    PermissionDef(PERM_ACTION_PLANS_REPORT_ACTIVITY, "Reportar una actividad asignada",              MODULE_ACTION_PLANS),
    PermissionDef(PERM_ACTION_PLANS_ADD_EVIDENCE,    "Agregar evidencia a una actividad reportada",  MODULE_ACTION_PLANS),
    PermissionDef(PERM_ACTION_PLANS_DASHBOARD,       "Ver dashboard agregado por responsable",       MODULE_ACTION_PLANS),
)


# ── Índices derivados ────────────────────────────────────────────────────
BY_CODE: Dict[str, PermissionDef] = {p.code: p for p in ALL_PERMISSIONS}


def permissions_by_module() -> Dict[str, List[PermissionDef]]:
    """Agrupa permisos por módulo en el orden del catálogo.

    Útil para la UI admin (renderizar checkboxes por sección) y para
    inspección. Devuelve un dict nuevo cada vez — no mutar el resultado.
    """
    grouped: Dict[str, List[PermissionDef]] = {}
    for p in ALL_PERMISSIONS:
        grouped.setdefault(p.module, []).append(p)
    return grouped


# ── Validaciones (fail-fast al importar) ─────────────────────────────────
def _validate_catalog() -> None:
    # 1) Códigos únicos
    codes = [p.code for p in ALL_PERMISSIONS]
    if len(codes) != len(set(codes)):
        dups = [c for c, n in Counter(codes).items() if n > 1]
        raise RuntimeError(f"[catalog] Permisos duplicados: {dups}")

    # 2) Módulos válidos
    invalid = {p.module for p in ALL_PERMISSIONS if p.module not in ALL_MODULES}
    if invalid:
        raise RuntimeError(f"[catalog] Módulos inválidos en catálogo: {sorted(invalid)}")

    # 3) Sincronización constantes PERM_* ↔ entradas del catálogo.
    #    Cualquier asimetría es bug — falla ruidoso para que se vea en CI.
    import sys
    this_module = sys.modules[__name__]
    perm_constants = {
        val for name, val in vars(this_module).items()
        if name.startswith("PERM_") and isinstance(val, str)
    }
    catalog_codes = set(codes)

    only_in_constants = perm_constants - catalog_codes
    only_in_catalog   = catalog_codes - perm_constants
    if only_in_constants:
        raise RuntimeError(
            f"[catalog] Constantes PERM_* sin entrada en ALL_PERMISSIONS: "
            f"{sorted(only_in_constants)}"
        )
    if only_in_catalog:
        raise RuntimeError(
            f"[catalog] Entradas en ALL_PERMISSIONS sin constante PERM_*: "
            f"{sorted(only_in_catalog)}"
        )


_validate_catalog()
