# PRD — Sistema PYBA de Gestión de Indicadores

**Versión:** 1.0
**Fecha:** 2026-05-23
**Owner del producto:** Gobernación — Programa PYBA (Protección y Bienestar Animal)
**Equipo técnico:** Desarrollo Backend (Flask) + Frontend (Angular)
**Estado:** En producción — iteración continua

---

## 1. Resumen ejecutivo

PYBA es un **sistema web de gestión, ejecución y análisis de indicadores estratégicos** de la Gobernación. Permite planificar la estrategia institucional (estrategia → componentes → objetivos → actividades MGA → indicadores), capturar la ejecución real mediante reportes y datasets externos (Excel), y monitorear el avance a través de dashboards, planes de acción y trazabilidad de auditoría.

El sistema reemplaza el flujo manual basado en hojas de cálculo dispersas por una **fuente única de verdad** auditable, con control de acceso por roles y permisos, y visualizaciones gerenciales en tiempo real.

---

## 2. Problema y oportunidad

### Problema
- La planificación estratégica y su ejecución viven en archivos Excel separados, sin trazabilidad, sin control de versiones y sin validaciones de negocio.
- No existe una vista consolidada del avance de indicadores ni de los planes de acción asociados.
- La asignación de responsabilidades (quién reporta qué, cuándo y con qué evidencia) es informal.
- Los datos de fuentes externas (presupuesto, censo animal, denuncias, donatón, personas capacitadas) llegan en formatos heterogéneos y no se cruzan con los indicadores.

### Oportunidad
Centralizar la gestión de indicadores en una plataforma única que:
- Garantice integridad de datos mediante un modelo jerárquico validado.
- Importe datasets externos (Excel) y los exponga como dashboards tipados.
- Soporte planes de acción colaborativos con responsables, evidencias y ventana de carga.
- Habilite reportes RBAC con auditoría completa.

---

## 3. Objetivos y métricas de éxito

| Objetivo | Métrica | Meta |
|---|---|---|
| Centralizar la captura de ejecución | % de indicadores con reportes mensuales | ≥ 90% |
| Cumplimiento de planes de acción | % de actividades reportadas en plazo (con evidencia ≤ 8 días) | ≥ 85% |
| Trazabilidad operativa | Cobertura de auditoría (acciones críticas con log) | 100% |
| Auto-servicio para áreas | Datasets cargados por usuarios sin soporte de TI | ≥ 80% |
| Disponibilidad | Uptime mensual del backend en producción | ≥ 99.5% |

---

## 4. Usuarios y roles

El sistema usa un **modelo RBAC híbrido**: roles + permisos granulares + overrides por usuario (`permisos(user) = permisos(rol) ∪ grants − revokes`). Actualmente la decisión por rol es autoritativa y los permisos corren en *shadow mode* para validar paridad.

| Rol | Permisos clave | Usuarios típicos |
|---|---|---|
| **admin** | Acceso total (30/30 permisos): usuarios, roles, datasets, estrategia, reportes, planes de acción, auditoría | Coordinador del programa, TI |
| **monitor** | Lectura amplia + reportes + planes de acción + dashboard (14 permisos) | Supervisores, dirección |
| **editor** | Escritura *scoped* en reportes y planes de acción + lectura de datasets (12 permisos) | Profesionales operativos, promotores |
| **viewer** | Solo `reports.read` (1 permiso) | Consultas externas, observadores |

**Reglas operacionales (invariantes):**
- Los 4 roles del sistema (`admin`, `monitor`, `editor`, `viewer`) son `is_system=True` y no se pueden eliminar.
- Permisos críticos no se pueden revocar al *main admin*.
- Un usuario no puede auto-degradarse de admin.

---

## 5. Alcance funcional

### 5.1 Autenticación y gestión de identidad
- Login con email + contraseña (bcrypt).
- JWT con *access* y *refresh tokens*; claim `permissions` embebido para evitar lookups en cada request.
- Endpoint `GET /users/me/permissions` para refrescar el set sin reemitir tokens.
- Endpoint `GET /users/me` con perfil + permisos del usuario activo.
- ABM de usuarios y asignación de roles (solo admin).
- Asignación de componentes a usuarios (`users.assign_components`) para limitar el scope visible.
- Overrides granulares (`grant` / `revoke`) por usuario sin necesidad de clonar roles.

### 5.2 Modelo estratégico (jerárquico)
```
Estrategia
 └── Componentes Estratégicos
      ├── Objetivos del Componente
      ├── Actividades MGA
      ├── Indicadores del Componente (con targets anuales)
      └── Políticas Públicas
```
- ABM de estrategias, componentes, objetivos, actividades MGA, indicadores y metas anuales (admin).
- Métricas de estrategia (`strategy_metrics`) configurables (admin).
- Asociación de políticas públicas a componentes.

### 5.3 Reportes (ejecución real)
- Entidad transaccional única: un reporte = una ejecución medible en un municipio en una fecha.
- Campos clave: `strategy_id`, `component_id`, `activity_id`, `municipality`, `report_date`, `detail_population` (JSON con desagregación de indicadores y población por sexo).
- Permisos diferenciados: `create`, `read`, `update_own`, `update_any`, `delete_own`, `delete_any`.
- Adjuntos / metadata flexibles vía JSON.
- Auditoría completa por usuario que crea/edita/elimina.

### 5.4 Planes de Acción
- Creación de planes con actividades asignadas a responsables y apoyos (incluyendo personas del dataset `PERSONAS PROMOTORES PYBA`).
- Estados: `Pendiente` | `En Ejecución` | `Realizado` | `Pendiente de Evidencia`.
- **Flujo de evidencia opcional** (ventana de 8 días):
  - Al reportar la actividad, `evidence_url` es opcional → estado pasa a `Pendiente de Evidencia` si no se adjunta.
  - Endpoint `PUT /action-plans/activities/{id}/evidence` permite subir/editar la evidencia dentro de los 8 días desde la entrega, solo por el responsable (admin/monitor pueden siempre).
- Score computado por actividad (5 con evidencia, 7 si está vinculada a reporte, −1 si vencida sin reportar).
- Calendario visual de actividades.
- Dashboard por plan con KPIs.
- Auditoría dedicada del plan.

### 5.5 Datasets (importación Excel y visualización tipada)
- Modelo: `Dataset` → `Table` → `Field` → `Record`.
- Importación de Excel vía pandas con normalización automática de nombres (`normalize_name()`).
- Detección automática del tipo de dataset por campos presentes (`analyzer.py`).
- **Tipos soportados** (cada uno con dashboard especializado):
  - `presupuesto` — KPIs presupuestales (apropiación, compromiso, ejecución, % avance) en formato 2026.
  - `censo_animal` — datos del censo animal por territorio.
  - `donaton` — recolección y trazabilidad de donatones.
  - `denuncias` — KPIs y secciones de denuncias procesadas.
  - `personas_capacitadas` — consolidado que alimenta el avance del indicador 76.
  - `animales`, `red_animalia`, `generico` — pipeline genérico.
- Visor de registros configurable por tipo (`RECORDS_CONFIG`).
- ABM completo de datasets, tablas, campos y registros (admin).
- Endpoints `viewer` (lectura) y `import` (carga masiva) separados por permiso.

### 5.6 Dashboards
- Dashboard principal con agregaciones de reportes:
  - Por estrategia, componente, municipio, fecha.
  - Indicadores acumulados y por condicional.
- Dashboards específicos por tipo de dataset (orquestados desde `dashboard/orchestrator.py`).
- Gráficos mixtos: `chart.js` (ng2-charts) + `apexcharts` (ngx-apexcharts).
- Mapas con Leaflet.
- Exportación a Excel (`xlsx` + `file-saver`).

### 5.7 Notificaciones
- Módulo `notifications/` con modelos, servicios y endpoints REST.
- Notificación de eventos críticos (reportes nuevos, actividades vencidas, evidencia pendiente).

### 5.8 Auditoría
- Log de acciones críticas (usuarios, roles, permisos, reportes, planes de acción).
- Vista de historial accesible solo a admin (`/audit-history`).
- Comando de retención: `flask purge-audit-logs --days 90`.

---

## 6. Requerimientos no funcionales

### 6.1 Performance
- Eager-load consolidado para evitar N+1: máximo 3 queries para cargar `user + role + permisos + overrides`.
- Cache por request en `flask.g` para evaluadores de permisos.
- Tests garantizan que endpoints con múltiples `has_permission` no disparan más de 1 SELECT a `users`.

### 6.2 Seguridad
- JWT bearer obligatorio en todos los endpoints (excepto login/refresh).
- Rate limiting en login (`8/min; 30/hora`) — deshabilitado solo en tests.
- CORS restrictivo: `localhost:4200`, `127.0.0.1:4200`, prod Netlify y *deploy previews* (`^https://[a-z0-9-]+--gestionindicadoresgov\.netlify\.app$`).
- Short-circuit de `OPTIONS` preflight a 204 antes de routing (compatible con `decorators = [jwt_required()]` a nivel de clase).
- SSL en Postgres obligatorio en producción (`RENDER` o `FLASK_ENV=production`).
- Header `Authorization → HTTP_AUTHORIZATION` espejado para proxies (Render/Cloudflare).
- Bcrypt para passwords; tokens con expiración.
- Validación fail-fast del catálogo de permisos al importar (unicidad, formato, sincronización constantes ↔ entradas).

### 6.3 Calidad / Testabilidad
- Suite pytest con guardas `pytest.exit()` que impiden ejecutar tests contra DB que no sea `sqlite:///:memory:`.
- `TestConfig` hardcoded e inmune a leakage de variables de entorno.
- Tests dedicados a invariantes RBAC, evaluador de permisos, paridad dual-mode, shadow telemetry, seeders y endpoints de auth.
- Frontend: `ng test` (Karma) + vitest disponible para pruebas modernas.

### 6.4 Disponibilidad / Despliegue
- Backend desplegable en Render (detección automática de `RENDER` env var).
- Frontend desplegado en Netlify con *deploy previews* por branch.
- Migraciones versionadas con Flask-Migrate (`flask db upgrade`).
- Seeders idempotentes (`flask seed`, `flask seed_permissions`, `flask seed_users`).

### 6.5 Internacionalización
- Idioma: Español (Colombia). No se contempla i18n multi-idioma en esta versión.

---

## 7. Arquitectura técnica

### 7.1 Stack
| Capa | Tecnología |
|---|---|
| Backend | Python 3.11, Flask 3, Flask-Smorest (OpenAPI), SQLAlchemy, Flask-Migrate, JWT, Bcrypt |
| Base de datos | PostgreSQL (prod) / SQLite in-memory (tests) |
| Frontend | Angular 21 standalone components, RxJS, Tailwind v4 |
| Visualización | chart.js + ng2-charts, apexcharts + ngx-apexcharts, Leaflet |
| UX | ngx-toastr, sweetalert2, lucide-angular, xlsx + file-saver |
| Despliegue | Render (backend), Netlify (frontend) |

### 7.2 Estructura modular (backend)
```
app/
 ├── main.py                  # Flask factory create_app()
 ├── api/router.py            # Registro Flask-Smorest con schema_name_resolver
 ├── core/                    # config, database, security, extensions
 ├── shared/permissions/      # Catálogo PERM_* + validación
 ├── utils/                   # permissions, rbac_invariants, normalizers
 └── modules/
      ├── indicators/         # Estrategia, componentes, indicadores, reportes
      ├── datasets/           # Datasets, tablas, campos, registros, dashboards tipados
      ├── action_plans/       # Planes de acción y actividades
      └── notifications/      # Sistema de notificaciones
```

Cada módulo de dominio sigue la convención:
```
<module>/
 ├── models/      # ORM SQLAlchemy
 ├── schemas/     # Marshmallow serialization
 ├── validators/  # Reglas de negocio
 ├── services/    # Lógica de aplicación
 └── routes/      # MethodView blueprints (Flask-Smorest)
```

### 7.3 Estructura frontend
```
src/app/
 ├── app.routes.ts            # Routing con guards (auth, guest, admin, viewer)
 ├── core/                    # guards, interceptors, models, services
 ├── layout/                  # AuthLayout, DashboardLayout
 ├── shared/                  # Componentes reutilizables
 └── features/
      ├── auth/               # Login
      ├── dashboard/          # Dashboard principal
      ├── datasets/           # Datasets (solo admin)
      ├── report/             # Reportes
      ├── action-plans/       # Planes de acción
      ├── user/               # ABM usuarios + perfil propio
      └── audit-history/      # Historial de auditoría (solo admin)
```

### 7.4 Integración Frontend ↔ Backend
- Frontend dev server (puerto 4200) proxea `/api` → `http://localhost:5000` vía `proxy.conf.json`.
- Documentación OpenAPI auto-generada: `/swagger-ui` y `/api-spec.json`.

---

## 8. Flujos clave

### 8.1 Flujo de reporte de actividad de Plan de Acción
1. Editor entra al plan asignado, ve sus actividades pendientes.
2. Selecciona "Reportar actividad" → marca como ejecutada, opcionalmente sube evidencia.
3. Sin evidencia → estado = `Pendiente de Evidencia` (color ámbar).
4. Tiene 8 días para subir la evidencia desde `PUT /activities/{id}/evidence`.
5. Score y dashboard del plan se actualizan automáticamente.

### 8.2 Flujo de importación de dataset
1. Admin entra a `/datasets`, crea un nuevo Dataset.
2. Sube un archivo Excel; el sistema lo parsea con pandas y crea Tables/Fields/Records.
3. `analyzer.py` detecta el `dataset_type` por los campos presentes.
4. Si es un tipo conocido, el orchestrator dispara el builder específico al consultar el dashboard.
5. Usuarios con permiso `datasets.read` visualizan el dashboard tipado en `/datasets/<id>`.

### 8.3 Flujo de gestión de permisos
1. Equipo de desarrollo agrega permiso en `app/shared/permissions/catalog.py` (constante `PERM_*` + entrada en `ALL_PERMISSIONS`).
2. Re-exporta desde `app/shared/permissions/__init__.py`.
3. Corre `pytest tests/test_permissions_catalog.py` (fail-fast).
4. Ejecuta `flask seed_permissions` (upsert idempotente, no asigna a roles).
5. Asigna desde UI admin (Fase D) o SQL.
6. Decora endpoint con `@dual_required(roles=(...), perms=(PERM_X,))`.

---

## 9. Roadmap (fases)

| Fase | Estado | Alcance |
|---|---|---|
| **Fase A** — Catálogo de permisos + seeders | ✅ Completa | Catálogo validado, seeders idempotentes |
| **Fase B parcial** — Dual mode | ✅ En curso | `dual_required` con shadow mode activo, rol = autoritativo |
| **Fase B completa** — Paridad rol/permiso | 🟡 Pendiente | 0 divergencias en staging → permisos = autoritativos |
| **Fase C** — Retirar `role_required` | ⏳ Planeada | Reemplazo total por `require_permission` |
| **Fase D** — UI admin de roles/permisos | ⏳ Planeada | Asignación de permisos desde frontend |
| **Mejoras datasets 2026** | 🟡 En curso | Nuevo formato presupuestal, dataset Denuncias, Personas Capacitadas consolidado |

---

## 10. Restricciones y supuestos

### Restricciones
- Stack tecnológico cerrado: no se considera migrar de Flask/Angular en este horizonte.
- PostgreSQL como único motor de producción (SSL obligatorio).
- Idioma: español; UI exclusivamente para usuarios de la Gobernación.

### Supuestos
- Los usuarios cuentan con acceso institucional (correo `@gobernacion.gov.co` u otro autorizado).
- Excel sigue siendo el formato dominante de intercambio con áreas externas.
- La granularidad temporal mínima de reportes es el día.

---

## 11. Riesgos

| Riesgo | Mitigación |
|---|---|
| Datos heterogéneos en Excel rompen el importador | `normalize_name()`, builder genérico de fallback, validadores por tipo |
| Divergencia rol vs permiso en producción | Shadow mode + telemetría `RBAC_SHADOW_DIVERGENCE` antes de cambiar autoritativa |
| Pérdida accidental de evidencia de actividades | Ventana cerrada de 8 días + auditoría + responsable identificado |
| Tests corriendo contra DB real | `pytest.exit()` guards en `conftest.py` con doble validación |
| JWT antiguo sin claim `permissions` | Fallback automático a lookup en BD |
| Permisos huérfanos en BD | `flask seed_permissions` idempotente con limpieza de orphans |

---

## 12. Métricas operacionales / Observabilidad

- Log estructurado `RBAC_SHADOW_DIVERGENCE` para divergencias rol/permiso.
- Tabla de auditoría con retención configurable (`purge-audit-logs --days N`).
- Swagger UI siempre disponible en `/swagger-ui` para diagnóstico de contratos.
- (Pendiente) Dashboard de salud del sistema con métricas de Render.

---

## 13. Glosario

- **MGA**: Metodología General Ajustada (Colombia) para formulación de proyectos públicos.
- **PYBA**: Programa de Protección y Bienestar Animal de la Gobernación.
- **Dataset**: Conjunto de datos importado desde Excel, con tipo detectado para dashboards especializados.
- **Plan de Acción**: Conjunto de actividades operativas con responsables, fechas y evidencias.
- **Indicador**: Métrica asociada a un componente estratégico, con metas anuales y reportes de ejecución.
- **Reporte**: Única entidad transaccional; representa una ejecución real medible (municipio + fecha + indicadores).
- **Shadow mode**: Modo operativo donde una decisión de autorización se computa pero no se aplica; sirve para validar paridad.
- **Override de permiso**: `grant` o `revoke` aplicado a un usuario específico, encima de los permisos heredados de su rol.

---

## 14. Referencias

- `CLAUDE.md` — Guía operativa para el agente y convenciones del repo.
- `GestionIndicadores_Backend/docs/RBAC.md` — Documentación detallada del modelo RBAC.
- `GestionIndicadores_Backend/README.md` — Setup y comandos del backend.
- Swagger UI en runtime: `http://localhost:5000/swagger-ui`.
