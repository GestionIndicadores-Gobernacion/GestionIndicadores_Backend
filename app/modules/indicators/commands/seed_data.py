# ==========================================================
# INDICADOR BASE (se aplica a todos los componentes)
# ==========================================================

def indicator():
    return {
        "name": "LOL",
        "field_type": "number",
        "is_required": True,
        "targets": [{"year": 2026, "target_value": 2}]
    }


# ==========================================================
# ESTRUCTURA MASIVA DE ESTRATEGIAS
# ==========================================================

STRATEGIES = [

# ==========================================================
# 1. PREVENCIÓN VIOLENCIA CONTRA ANIMALES
# ==========================================================
{
    "name": "ESTRATEGIA INTEGRAL PARA LA PREVENCIÓN DE LAS VIOLENCIA CONTRA LOS ANIMALES",
    "objective": """IMPLEMENTAR UNA ESTRATEGIA PEDAGÓGICA Y COMUNITARIA, BASADA EN GUÍAS METODOLÓGICAS CONSTRUIDAS DE FORMA PARTICIPATIVA DURANTE EL PROCESO DE FORMULACIÓN DE LA POLÍTICA PÚBLICA DE PROTECCIÓN Y BIENESTAR ANIMAL, QUE PERMITA PREVENIR Y ATENDER DE MANERA INTEGRAL LOS ESCENARIOS DE RIESGO ASOCIADOS A LAS VIOLENCIAS CONTRA LOS ANIMALES EN EL DEPARTAMENTO DEL VALLE DEL CAUCA.""",
    "product_goal_description": "OPERATIVIZAR 1 ESTRATEGIA QUE GARANTICE EL CUMPLIMIENTO DE LA POLÍTICA DE PROTECCIÓN Y BIENESTAR ANIMAL EN EL PERIODO DE GOBIERNO",
    "annual_goals": [{"year_number": 1, "value": 100}],
    "components": [
        {
            "name": "ANIMALES COMO EMBAJADORES DE PAZ",
            "objectives": ["CREAR ESCENARIOS DONDE LOS ANIMALES SON CLAVES PARA LA RECUPERAICON, REHABILITACION Y APOYO EMOCIONAL"],
            "mga": ["DESARROLLAR LA METODOLOGÍA PARA LA PREVENCIÓN DE LOS RIESGOS DE VIOLENCIAS CONTRA LOS ANIMALES"]
        },
        {
            "name": "ASISTENCIAS TECNICAS A ACTORES INSTITUCIONALES DE LA ADMINISTRACION PUBLICA",
            "objectives": ["BRINDAR ASISTENCIAS TÉCNICAS ESPECIALIZADAS A LAS ENTIDADES TERRITORIALES DEL DEPARTAMENTO"],
            "mga": ["OPERATIVIZAR EL COMITÉ INTERDISCIPLINARIO"]
        },
        {
            "name": "RUTA DE ATENCION",
            "objectives": ["FORTALECER LA RUTA DE ATENCIÓN PYBA"],
            "mga": ["IMPLEMENTACIÓN DE LA RUTA DE PROTECCIÓN Y ATENCIÓN ANIMAL"]
        },
        {
            "name": "TURISMO MULTIESPECIE",
            "objectives": ["CREAR UNA ESTARTEGIA DE TURIMO MULTIESPECIA DONDE SE GARANTICE EL RESPETO POR LOS ANIMALES"],
            "mga": ["DESARROLLAR LA METODOLOGÍA PARA LA PREVENCIÓN DE LOS RIESGOS"]
        },
        {
            "name": "ENFOQUE DIFERENCIAL",
            "objectives": [
                "IMPLEMENTAR PROGRAMA DE GUARDIANTES DE HUELLA",
                "IMPLEMENTAR PROGRAMA DE ANIMALES VICTIMAS DEL CONFLICTO"
            ],
            "mga": ["DESARROLLAR METODOLOGÍA DE PREVENCIÓN"]
        },
        {
            "name": "OBSERVATORIO/PLATAFORMA",
            "objectives": ["IMPLEMENTAR UNA PLATAFORMA VIRTUAL DE GESTIÓN DE INFORMACIÓN PYBA"],
            "mga": ["IMPLEMENTAR EL OBSERVATORIO DEPARTAMENTAL"]
        }
    ]
},

# ==========================================================
# 2. CENTROS DE BIENESTAR
# ==========================================================
{
    "name": "Centros de bienestar animal por microregiones",
    "objective": "FORTALECER LA OPERACIÓN Y CAPACIDAD TÉCNICA DE LOS CENTROS DE BIENESTAR ANIMAL",
    "product_goal_description": "DOTAR TRES CENTROS DE BIENESTAR ANIMAL REGIONAL",
    "annual_goals": [{"year_number": 1, "value": 100}],
    "components": [
        {
            "name": "CENTROS DE BIENESTAR ANIMAL",
            "objectives": [
                "FORTALECER LOS PROCESOS TÉCNICOS Y OPERATIVOS",
                "DOTAR CENTROS DE BIENESTAR ANIMAL REGIONALES"
            ],
            "mga": [
                "ASESORAR PROCESOS DE CENTROS",
                "DOTAR CENTROS CON INSUMOS"
            ]
        }
    ]
},

# ==========================================================
# 3. ATENCIÓN PRIMARIA EN SALUD
# ==========================================================
{
    "name": "ATENCION PRIMARIA EN SALUD",
    "objective": "IMPLEMENTAR UNA ESTRATEGIA INTEGRAL DE ATENCIÓN PRIMARIA EN SALUD ANIMAL",
    "product_goal_description": "ATENDER 10.000 ANIMALES",
    "annual_goals": [{"year_number": 1, "value": 100}],
    "components": [
        {"name": "ATENCION UNIDAD MOVIL", "objectives": ["JORNADAS DE SALUD ANIMAL"], "mga": ["ATENCION EN TERRITORIO"]},
        {"name": "ATENCION EQUIPO DE CAMPO", "objectives": ["ATENCION EN ALBERGUES"], "mga": ["JORNADAS DE ATENCION"]},
        {"name": "ANIMALES DE GRANJA", "objectives": ["FORTALECER BIENESTAR ANIMAL DE PRODUCCION"], "mga": ["DIAGNOSTICOS"]},
        {"name": "EQUIPO URIA", "objectives": ["ATENCION INMEDIATA"], "mga": ["JORNADAS DE ATENCION"]}
    ]
},

# ==========================================================
# 4. DESARROLLO ECONÓMICO
# ==========================================================
{
    "name": "ESTRATEGIA DE DESARROLLO ECONOMICO",
    "objective": "FORTALECER EL DESARROLLO ECONÓMICO DEL ECOSISTEMA PYBA",
    "product_goal_description": "COFINANCIAR 40 ACTORES",
    "annual_goals": [{"year_number": 1, "value": 100}],
    "components": [
        {"name": "CLÚSTER EMPRESARIAL", "objectives": ["RED EMPRESARIAL"], "mga": ["ACOMPAÑAMIENTO TECNICO"]},
        {"name": "AUTOSOSTENIBILIDAD REFUGIOS", "objectives": ["MODELOS DE INGRESO"], "mga": ["SUMINISTRO INSUMOS"]},
        {"name": "EMPRENDIMIENTOS CONSCIENTES", "objectives": ["COFINANCIACION"], "mga": ["SUMINISTRO INSUMOS"]},
        {"name": "ALIANZAS ESTRATEGICAS", "objectives": ["REDES DE ACTORES"], "mga": ["ACOMPAÑAMIENTO"]}
    ]
},

# ==========================================================
# 5. ARTICULACIÓN COMUNITARIA
# ==========================================================
{
    "name": "estrategia de articulacion comunitaria",
    "objective": "CREAR Y FORTALECER REDES DE ACTORES",
    "product_goal_description": "CREAR Y SOSTENER 3 REDES",
    "annual_goals": [{"year_number": 1, "value": 100}],
    "components": [
        {"name": "DONATON SALVANDO HUELLAS", "objectives": ["SUMINISTRAR ALIMENTO"], "mga": ["SUMINISTROS"]},
        {"name": "RED ANIMALIA", "objectives": ["FORTALECER RED"], "mga": ["ACOMPAÑAMIENTO"]},
        {"name": "ACOMPAÑAMIENTO PSICOSOCIAL", "objectives": ["SALUD MENTAL RESCATISTAS"], "mga": ["ACOMPAÑAMIENTO"]},
        {"name": "INSPECCION ALBERGUES", "objectives": ["DIAGNOSTICO"], "mga": ["DIAGNOSTICOS"]},
        {"name": "PROGRAMA ADOPCIONES", "objectives": ["ADOPCION RESPONSABLE"], "mga": ["ACOMPAÑAMIENTO"]},
        {"name": "JUNTAS DEFENSORAS", "objectives": ["CAPACITACION"], "mga": ["ACOMPAÑAMIENTO"]}
    ]
},

# ==========================================================
# 6. EDUCACIÓN PYBA
# ==========================================================
{
    "name": "ESTRATEGIA EDUACTIVA PYBA",
    "objective": "CAPACITAR POBLACIONES EN PROTECCIÓN ANIMAL",
    "product_goal_description": "CAPACITAR 10.000 PERSONAS",
    "annual_goals": [{"year_number": 1, "value": 100}],
    "components": [
        {"name": "PROMOTORES PYBA", "objectives": ["CAPACITACIÓN"], "mga": ["FORMACIÓN"]},
        {"name": "ESCUADRON BENJI", "objectives": ["PRIMERA INFANCIA"], "mga": ["FORMACIÓN"]},
        {"name": "SERVICIO SOCIAL DEJANDO HUELLA", "objectives": ["INTEGRAR ESTUDIANTES"], "mga": ["FORMACIÓN"]},
        {"name": "ALIANZAS ACADEMICAS", "objectives": ["INTERCAMBIO SABERES"], "mga": ["FORMACIÓN"]},
        {"name": "CULTURA Y EXPERIENCIAS", "objectives": ["PROMOVER RESPETO"], "mga": ["EVENTOS"]}
    ]
}

]
