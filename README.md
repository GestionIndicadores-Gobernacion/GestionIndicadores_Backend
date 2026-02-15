# PYBA – Sistema de Gestión de Indicadores

Backend del sistema PYBA para la planificación, ejecución y análisis de indicadores
de la Gobernación.

---

## 🧱 Stack Tecnológico

- Python 3.11
- Flask
- Flask-Smorest (OpenAPI / Swagger)
- SQLAlchemy + Flask-Migrate
- PostgreSQL
- JWT (Access + Refresh)
- Bcrypt

---

## 🏗️ Arquitectura

Arquitectura en capas:

- models/        → Modelos ORM  
- schemas/       → Serialización (Marshmallow)  
- validators/    → Reglas de negocio  
- handlers/      → Lógica de aplicación  
- routes/        → Endpoints REST  
- commands/      → Seed y CLI  
- extensions.py  → Extensiones Flask  
- app.py         → Factory principal  

---

## 🔐 Autenticación

La API utiliza **JWT (Bearer Token)**.

### Login
```
POST /auth/login
```

```json
{
  "email": "admin@gobernacion.gov.co",
  "password": "Gob2025*"
}
```

Respuesta:
```json
{
  "access_token": "JWT_TOKEN",
  "refresh_token": "REFRESH_TOKEN",
  "user": { }
}
```

Usar el token en cada request:
```
Authorization: Bearer <access_token>
```

---

## 👥 Roles del Sistema

- **viewer** → solo lectura  
- **editor** → crea y gestiona reportes  
- **admin**  → administración total  

Los roles se cargan automáticamente vía **seed**.

---

## 🧩 Modelo del Sistema (Jerarquía)

Estrategia  
→ Componentes Estratégicos  
→ Objetivos del Componente  
→ Actividades MGA  
→ Indicadores  
→ **Reporte (ejecución real)**  

📌 El **Reporte** es la única entidad transaccional.

---

## 🧾 Reportes

Campos clave:
- strategy_id  
- component_id  
- activity_id  
- municipality  
- report_date  
- detail_population (JSON)  
- created_by  

Ejemplo de `detail_population`:

```json
{
  "indicators": [
    {
      "indicator_id": 3,
      "value": 12,
      "conditional": "Formal"
    }
  ],
  "population": {
    "women": 20,
    "men": 15
  }
}
```

---

## 📈 Dashboard

Endpoints agregados:
- Reportes por estrategia  
- Reportes por municipio  
- Reportes por fechas  
- Indicadores acumulados  
- Indicadores por condicional  

---

## 🌱 Seed (Datos iniciales)

Ejecutar:

```
flask seed
```

Crea:
- Roles
- Usuarios de prueba

### Usuarios de prueba

| Rol   | Email                         | Password |
|------|-------------------------------|----------|
| admin | admin@gobernacion.gov.co     | Gob2025* |
| editor | editor@gobernacion.gov.co   | Gob2025* |
| viewer | viewer@gobernacion.gov.co   | Gob2025* |

---

## 📚 Documentación API

- Swagger UI: `/swagger-ui`
- OpenAPI JSON: `/api-spec.json`

---

## 🚀 Ejecución local

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

flask db upgrade
flask seed
flask run
```

---

## 📌 Estado del proyecto

✔️ Backend completo  
✔️ Seguridad aplicada  
✔️ Trazabilidad por usuario  
✔️ Listo para frontend y despliegue  
