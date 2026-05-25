# Re-exporta el catálogo para que el resto del backend pueda hacer:
#     from app.shared.permissions import PERM_USERS_MANAGE, BY_CODE
# y evitar strings literales sueltos. La fuente de verdad sigue siendo
# `app.shared.permissions.catalog` — este archivo es solo conveniencia.
from app.shared.permissions.catalog import (  # noqa: F401
    # Estructura
    PermissionDef,
    ALL_PERMISSIONS,
    BY_CODE,
    permissions_by_module,
    # Módulos
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
    ALL_MODULES,
    # Constantes — users
    PERM_USERS_READ_BASIC,
    PERM_USERS_READ,
    PERM_USERS_MANAGE,
    PERM_USERS_ASSIGN_COMPONENTS,
    PERM_USERS_MANAGE_PERMISSIONS,
    # Constantes — roles
    PERM_ROLES_READ,
    PERM_ROLES_MANAGE,
    # Constantes — audit
    PERM_AUDIT_READ,
    # Constantes — strategies / components / metrics / public_policies
    PERM_STRATEGIES_MANAGE,
    PERM_COMPONENTS_MANAGE,
    PERM_STRATEGY_METRICS_MANAGE,
    PERM_PUBLIC_POLICIES_MANAGE,
    # Constantes — datasets
    PERM_DATASETS_READ,
    PERM_DATASETS_MANAGE,
    PERM_DATASETS_IMPORT,
    # Constantes — reports
    PERM_REPORTS_CREATE,
    PERM_REPORTS_READ,
    PERM_REPORTS_UPDATE_OWN,
    PERM_REPORTS_UPDATE_ANY,
    PERM_REPORTS_DELETE_OWN,
    PERM_REPORTS_DELETE_ANY,
    # Constantes — action_plans
    PERM_ACTION_PLANS_CREATE,
    PERM_ACTION_PLANS_READ,
    PERM_ACTION_PLANS_UPDATE_OWN,
    PERM_ACTION_PLANS_UPDATE_ANY,
    PERM_ACTION_PLANS_DELETE_OWN,
    PERM_ACTION_PLANS_DELETE_ANY,
    PERM_ACTION_PLANS_REPORT_ACTIVITY,
    PERM_ACTION_PLANS_ADD_EVIDENCE,
    PERM_ACTION_PLANS_DASHBOARD,
)
