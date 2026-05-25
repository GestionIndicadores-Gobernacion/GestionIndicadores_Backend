# TestSprite AI Testing Report (MCP)

---

## 1️⃣ Document Metadata
- **Project Name:** GestionIndicadores_Backend
- **Date:** 2026-05-23
- **Prepared by:** TestSprite AI Team
- **Plan / Credits:** Free (150 créditos)
- **Local endpoint bajo prueba:** http://localhost:5000
- **Modo del servidor:** development
- **Alcance:** codebase completo (testScope = codebase)

---

## 2️⃣ Requirement Validation Summary

### Requirement: Autenticación JWT
> Login con email/password debe devolver `access_token` y `refresh_token` con los claims `permissions`, `role_id` y `role`.

#### Test TC001 — POST /auth/login con credenciales válidas
- **Test Code:** [TC001_post_auth_login_with_valid_credentials.py](./TC001_post_auth_login_with_valid_credentials.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9cb197ca-4202-467a-afaf-5902afe63fba/f0b5cc84-3530-4be6-a5ef-222838d5d31d
- **Status:** ❌ Failed
- **Test Error:**
  ```
  ModuleNotFoundError: No module named 'jwt'
  ```
- **Analysis / Findings:**
  El test es funcionalmente correcto: hace `POST /auth/login` contra `localhost:5000` con `admin@gobernacion.gov.co / Gob2025*`, espera `200`, parsea la respuesta y decodifica el JWT sin verificar firma para inspeccionar claims (`permissions`, `role|role_id`). El fallo NO es del backend: es del sandbox de ejecución de TestSprite, que no tiene `PyJWT` instalado para hacer `jwt.decode(...)`. El endpoint del backend probablemente responde bien (el flujo de request previo no produjo error). Acción recomendada: ejecutar este mismo script desde un entorno local con `pip install PyJWT requests` para validar la API real; o pedir a TestSprite que añada PyJWT a su image de ejecución.

---

## 3️⃣ Coverage & Matching Metrics

- **0/1** tests pasaron (0%) — falla por entorno de TestSprite, no por defecto del backend
- **Tests generados:** 1 (TC001 — login)
- **Cobertura del plan Free:** muy reducida; el codebase tiene ~50 endpoints distribuidos en 10 features, pero TestSprite Free solo generó 1 caso para autenticación

| Requirement                                | Total Tests | ✅ Passed | ❌ Failed |
|--------------------------------------------|-------------|-----------|------------|
| Autenticación JWT                          | 1           | 0         | 1          |
| Gestión de usuarios y RBAC                 | 0           | 0         | 0          |
| Estrategias y componentes                  | 0           | 0         | 0          |
| Reportes de avance de indicadores          | 0           | 0         | 0          |
| KPIs                                       | 0           | 0         | 0          |
| Datasets y tablas (CRUD + Excel import)    | 0           | 0         | 0          |
| Dashboards de datasets (por dataset_type)  | 0           | 0         | 0          |
| Planes de acción y evidencias              | 0           | 0         | 0          |
| Notificaciones                             | 0           | 0         | 0          |
| Auditoría                                  | 0           | 0         | 0          |

---

## 4️⃣ Key Gaps / Risks

1. **Cobertura crítica insuficiente.** Con sólo 1 test para autenticación, no se evalúan los flujos que el equipo identificó como sensibles: RBAC en modo shadow (`dual_required`), importador de Excel para datasets, dashboard dispatcher por `dataset_type`, ventana de 8 días para evidencias de plan de acción, agregaciones de reportes. Para cubrirlos se necesita un plan de pago de TestSprite o complementar con `pytest` local (la suite existe en `tests/` y arranca con `pytest`).
2. **Falla por entorno externo, no por código del backend.** El `ModuleNotFoundError: No module named 'jwt'` indica que el sandbox remoto de TestSprite no resuelve `PyJWT`. Antes de tomar el reporte como evidencia de bug, ejecutar TC001 en local — donde sí está instalado — para confirmar que `/auth/login` responde 200 con los claims esperados.
3. **Rate limit en `/auth/login` (8/min) puede generar 429 en suites mayores.** Si se amplía la batería, intercalar pausas o desactivar limiter en `TestConfig` (`RATELIMIT_ENABLED = False` ya está en el suite oficial).
4. **RBAC shadow mode.** Cualquier test futuro que asuma que la API rechaza por permisos puros va a fallar: hoy gana el rol. Documentar en el `additionalInstruction` cuando se generen más tests.
5. **No hay tests sobre el flujo de subida de archivos** (`/files/upload`, `/action-plans/.../evidence`), que son operaciones con efecto colateral (filesystem) — riesgo medio si en producción esos handlers cambian.

---
