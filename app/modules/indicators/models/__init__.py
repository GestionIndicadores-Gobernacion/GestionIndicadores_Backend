from app.modules.indicators.models.Strategy.strategy import Strategy
from app.modules.indicators.models.Strategy.strategy_annual_goal import StrategyAnnualGoal

from app.shared.models.user import User
from app.shared.models.user_component import UserComponent
from app.shared.models.role import Role
# ── RBAC (Bloque 2): registrados aquí para que db.create_all() los
# considere también desde el módulo indicators. No hay uso en runtime aún.
from app.shared.models.permission import Permission
from app.shared.models.role_permission import RolePermission
from app.shared.models.user_permission import UserPermission

from app.modules.indicators.models.Component.component import Component
from app.modules.indicators.models.Component.component_objective import ComponentObjective
from app.modules.indicators.models.Component.component_indicator import ComponentIndicator
from app.modules.indicators.models.Component.component_mga_activity import ComponentMGAActivity
from app.modules.indicators.models.Component.component_indicator_target import ComponentIndicatorTarget
from app.modules.indicators.models.Component.component_public_policy import component_public_policies
from app.modules.indicators.models.PublicPolicy.public_policy import PublicPolicy

from app.modules.indicators.models.Report.report import Report
from app.modules.indicators.models.Report.report_indicator_value import ReportIndicatorValue

from app.shared.models.audit_log import AuditLog
