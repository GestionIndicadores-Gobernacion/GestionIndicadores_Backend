import json
import sqlite3
import unicodedata
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
RUTA_DB = BASE_DIR / "auxilio_animal.db"

app = Flask(__name__)
CORS(app)  # Permite peticiones externas desde Netlify

# Coordenadas de referencia de los municipios del Valle del Cauca
COORDENADAS_MUNICIPIOS = {
    "CALI": [3.4516, -76.5320], "SANTIAGO DE CALI": [3.4516, -76.5320], "PALMIRA": [3.5394, -76.3036], "YUMBO": [3.5824, -76.4957],
    "JAMUNDÍ": [3.2606, -76.5414], "JAMUNDI": [3.2606, -76.5414], "CANDELARIA": [3.4061, -76.3478],
    "DAGUA": [3.6582, -76.6872], "BUGA": [3.9009, -76.2978], "GUADALAJARA DE BUGA": [3.9009, -76.2978], "TULUÁ": [4.0847, -76.1954],
    "TULUA": [4.0847, -76.1954], "RIOFRÍO": [4.1575, -76.2889], "RIOFRIO": [4.1575, -76.2889],
    "ZARZAL": [4.3944, -76.0792], "ROLDANILLO": [4.4144, -76.1558], "SEVILLA": [4.2678, -75.9325],
    "BOLÍVAR": [4.3392, -76.1856], "BOLIVAR": [4.3392, -76.1856], "EL DOVIO": [4.5097, -76.2369],
    "EL ÁGUILA": [4.9142, -75.9928], "EL AGUILA": [4.9142, -75.9928], "VERSALLES": [4.5828, -76.2025],
    "TORO": [4.6108, -76.0811], "LA CUMBRE": [3.6492, -76.5656], "VIJES": [3.6936, -76.4389],
    "RESTREPO": [3.8236, -76.5233], "GINEBRA": [3.7258, -76.2678], "GUACARÍ": [3.7656, -76.3317],
    "GUACARI": [3.7656, -76.3317], "FLORIDA": [3.3222, -76.2344], "PRADERA": [3.4192, -76.2442],
    "BUENAVENTURA": [3.8801, -77.0312], "CARTAGO": [4.7464, -75.9117], "ALCALÁ": [4.6747, -75.7819],
    "ALCALA": [4.6747, -75.7819], "ULLOA": [4.7042, -75.7397], "BUGALAGRANDE": [4.2128, -76.1561],
    "ANDALUCÍA": [4.1728, -76.1661], "ANDALUCIA": [4.1728, -76.1661], "TRUJILLO": [4.2236, -76.3214],
    "EL CAIRO": [4.7617, -76.2206], "LA UNIÓN": [4.5328, -76.1036], "LA UNION": [4.5328, -76.1036],
    "YOTOCO": [3.8617, -76.3836], "CALIMA - EL DARIÉN": [3.9317, -76.4864], "CALIMA": [3.9317, -76.4864],
    "SAN PEDRO": [4.0000, -76.2300], "EL CERRITO": [3.6850, -76.3130], "CAICEDONIA": [4.3325, -75.8322],
    "LA VICTORIA": [4.5222, -76.0372], "OBANDO": [4.5750, -75.9736], "ARGELIA": [4.7289, -76.1264],
    "CHOCÓ": [5.6919, -76.6583], "CHOCO": [5.6919, -76.6583], "MONTENEGRO": [4.5667, -75.7500]
}

def normalizar_texto(texto: str) -> str:
    if not texto: return ""
    t = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").strip().upper()

def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def get_db():
    conn = sqlite3.connect(RUTA_DB)
    conn.row_factory = dict_factory
    return conn

# Health Check / Comprobación de estado
@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "service": "API Auxilio Animal - Sismo 2026",
        "database": RUTA_DB.name
    })

# ==============================================================================
# SERVICIO DE ARCHIVOS (FOTOS Y PLANILLAS ESCANEADAS)
# ==============================================================================

@app.route("/foto/<path:filepath>")
def servir_foto(filepath):
    rutas_busqueda = [
        BASE_DIR / filepath,
        BASE_DIR / "salida_confirmación" / "actas" / "procesadas" / Path(filepath).name,
        BASE_DIR / "salida_confirmacion" / "actas" / "procesadas" / Path(filepath).name,
        BASE_DIR / "salida_confirmación" / "actas" / "procesadas_medicamentos" / Path(filepath).name,
        BASE_DIR / "salida_confirmacion" / "actas" / "procesadas_medicamentos" / Path(filepath).name,
        BASE_DIR / "voluntarios_donaciones" / "fotos" / Path(filepath).name,
        BASE_DIR / "voluntarios_operativos" / "fotos" / Path(filepath).name,
        BASE_DIR / "ingreso" / "actas" / "terminadas" / Path(filepath).name
    ]
    for r in rutas_busqueda:
        if r.exists() and r.is_file():
            return send_from_directory(r.parent, r.name)
    return jsonify({"error": "Foto no encontrada"}), 404

# ==============================================================================
# SUBMENÚ 1: RESUMEN Y CARTOGRAFÍA
# ==============================================================================

@app.route("/api/resumen-general")
def api_resumen_general():
    fecha_filtro = request.args.get("fecha", "").strip()
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT concepto, total_ingresado, total_entregado, stock_disponible FROM vista_balance_alimentos")
    balance_filas = c.fetchall()

    filtro_fecha = "WHERE fecha_lote = ?" if fecha_filtro else ""
    params_fecha = [fecha_filtro] if fecha_filtro else []

    c.execute(f"""
        SELECT 
            SUM(alimento_perro_kg) AS perro_kg,
            SUM(alimento_gato_kg) AS gato_kg,
            SUM(total_alimento_seco_kg) AS total_kg,
            SUM(comida_humeda_total_und) AS total_humeda,
            SUM(arena_kg) AS total_arena,
            COUNT(*) AS total_actas
        FROM salidas_alimentos
        {filtro_fecha}
    """, params_fecha)
    kpis = c.fetchone() or {}

    filtro_mun = "WHERE municipio != '' AND municipio IS NOT NULL"
    if fecha_filtro:
        filtro_mun += " AND fecha_lote = ?"

    c.execute(f"""
        SELECT 
            municipio,
            SUM(alimento_perro_kg) AS perro_kg,
            SUM(alimento_gato_kg) AS gato_kg,
            SUM(total_alimento_seco_kg) AS total_kg,
            COUNT(*) AS actas_count
        FROM salidas_alimentos
        {filtro_mun}
        GROUP BY municipio
        ORDER BY total_kg DESC
    """, params_fecha)
    municipios_raw = c.fetchall()

    c.execute("SELECT COUNT(*) AS c_despachos, SUM(total_alimento_seco_kg) AS kg_desp FROM salidas_alimentos")
    m_desp = c.fetchone()
    c.execute("SELECT COUNT(DISTINCT codigo_acta_vinculante) AS c_actas FROM salidas_alimentos WHERE codigo_acta_vinculante != 'SIN_NUMERO'")
    m_actas = c.fetchone()
    c.execute("SELECT COUNT(*) AS c_meds, SUM(cantidad) AS und_meds FROM salidas_medicamentos")
    m_meds = c.fetchone()
    c.execute("SELECT COUNT(*) AS c_refugios, SUM(total_animales_censados) AS anim_censados FROM censo_emergencias_refugios")
    m_censo = c.fetchone()
    c.execute("SELECT (SELECT COUNT(*) FROM donaciones_voluntarios) AS c_don, (SELECT COUNT(*) FROM voluntarios_operativos) AS c_ope, (SELECT COUNT(*) FROM voluntarios_transporte) AS c_trans")
    m_vol = c.fetchone()

    conn.close()

    municipios_mapa = []
    fuera_del_valle = []

    for m in municipios_raw:
        nom = m["municipio"].strip()
        nom_norm = normalizar_texto(nom)
        coords = COORDENADAS_MUNICIPIOS.get(nom_norm, [3.4516, -76.5320])
        es_externo = nom_norm in ["CHOCO", "MONTENEGRO", "VALLE DEL CAUCA", "NORTE DEL VALLE", "OTRO DEPARTAMENTO"]
        
        info = {
            "nombre": nom,
            "perro_kg": round(m["perro_kg"] or 0, 1),
            "gato_kg": round(m["gato_kg"] or 0, 1),
            "total_kg": round(m["total_kg"] or 0, 1),
            "actas": m["actas_count"],
            "lat": coords[0],
            "lng": coords[1],
            "externo": es_externo
        }
        if es_externo:
            fuera_del_valle.append(info)
        else:
            municipios_mapa.append(info)

    return jsonify({
        "balance": balance_filas,
        "kpis": {
            "perro_kg": round(kpis.get("perro_kg") or 0, 1),
            "gato_kg": round(kpis.get("gato_kg") or 0, 1),
            "total_kg": round(kpis.get("total_kg") or 0, 1),
            "humeda_und": kpis.get("total_humeda") or 0,
            "arena_kg": round(kpis.get("total_arena") or 0, 1),
            "actas_count": kpis.get("total_actas") or 0
        },
        "municipios": municipios_mapa,
        "externos": fuera_del_valle,
        "dock_resumen": {
            "despachos": f"{m_desp['c_despachos']} actas ({round(m_desp['kg_desp'] or 0, 1):,} Kg concentrado)",
            "actas": f"{m_desp['c_despachos']} escaneos con foto y firmas",
            "farmacologia": f"{m_meds['c_meds']:,} fármacos ({int(m_meds['und_meds'] or 0):,} unidades)",
            "censo": f"{m_censo['c_refugios']} albergues ({int(m_censo['anim_censados'] or 0):,} animales)",
            "red_humana": f"{m_vol['c_don']} donantes, {m_vol['c_ope']} operativos, {m_vol['c_trans']} conductores"
        }
    })

@app.route("/api/municipio-detalle/<nombre>")
def api_municipio_detalle(nombre):
    fecha_filtro = request.args.get("fecha", "").strip()
    conn = get_db()
    c = conn.cursor()
    nom_clean = nombre.strip()

    filtro_fecha = "AND fecha_lote = ?" if fecha_filtro else ""
    params = [nom_clean, fecha_filtro] if fecha_filtro else [nom_clean]

    c.execute(f"""
        SELECT 
            SUM(alimento_perro_kg) AS perro,
            SUM(alimento_gato_kg) AS gato,
            SUM(total_alimento_seco_kg) AS total_seco,
            SUM(comida_humeda_perro_und) AS hum_perro,
            SUM(comida_humeda_gato_und) AS hum_gato,
            SUM(arena_kg) AS arena,
            SUM(huacales_und) AS huacales,
            SUM(areneros_und) AS areneros,
            SUM(recipientes_und) AS comederos,
            SUM(collares_und) AS collares,
            SUM(camas_und) AS camas,
            SUM(cobijas_und) AS cobijas
        FROM salidas_alimentos
        WHERE LOWER(municipio) = LOWER(?) {filtro_fecha}
    """, params)
    stats = c.fetchone() or {}

    c.execute(f"""
        SELECT COUNT(*) AS total_meds
        FROM salidas_medicamentos m
        JOIN salidas_alimentos s ON m.codigo_acta_vinculante = s.codigo_acta_vinculante
        WHERE LOWER(s.municipio) = LOWER(?) AND s.codigo_acta_vinculante != 'SIN_NUMERO' {filtro_fecha}
    """, params)
    meds_count = (c.fetchone() or {}).get("total_meds", 0)

    c.execute(f"""
        SELECT barrio_corregimiento_refugio, recibe_nombre, total_alimento_seco_kg, archivo_imagen, codigo_acta_vinculante, fecha_lote
        FROM salidas_alimentos
        WHERE LOWER(municipio) = LOWER(?) AND barrio_corregimiento_refugio != '' {filtro_fecha}
        ORDER BY total_alimento_seco_kg DESC LIMIT 40
    """, params)
    puntos = c.fetchall()
    conn.close()

    perro = round(stats.get("perro") or 0, 1)
    gato = round(stats.get("gato") or 0, 1)
    total_seco = round(stats.get("total_seco") or 0, 1)

    priority_cards = [
        {"key": "Alimento Perro (Kg)", "val": f"{perro:,.1f} Kg", "tipo": "perro"},
        {"key": "Alimento Gato (Kg)", "val": f"{gato:,.1f} Kg", "tipo": "gato"},
        {"key": "Total Concentrado (Kg)", "val": f"{total_seco:,.1f} Kg", "tipo": "total"}
    ]

    others_raw = {
        "Arena Sanitaria (Kg)": f"{round(stats.get('arena') or 0, 1):,.1f} Kg",
        "Areneros (Und)": stats.get("areneros") or 0,
        "Camas / Espumas (Und)": stats.get("camas") or 0,
        "Cobijas / Sábanas (Und)": stats.get("cobijas") or 0,
        "Collares / Correas (Und)": stats.get("collares") or 0,
        "Comederos / Platos (Und)": stats.get("comederos") or 0,
        "Huacales / Jaulas (Und)": stats.get("huacales") or 0,
        "Húmeda Gato (Und)": stats.get("hum_gato") or 0,
        "Húmeda Perro (Und)": stats.get("hum_perro") or 0,
        "Insumos Médicos (Unds)": meds_count or 0
    }

    sorted_others = [{"key": k, "val": str(v), "tipo": "normal"} for k, v in sorted(others_raw.items())]

    return jsonify({
        "municipio": nom_clean,
        "estadisticas_ordenadas": priority_cards + sorted_others,
        "puntos": puntos
    })

# ==============================================================================
# SUBMENÚ 2: DESPACHOS
# ==============================================================================

@app.route("/api/despachos/filtrar", methods=["POST"])
def api_despachos_filtrar():
    data = request.get_json() or {}
    autoriza = data.get("autoriza", "").strip()
    recibe = data.get("recibe", "").strip()
    municipio = data.get("municipio", "").strip()
    fecha_desde = data.get("fecha_desde", "").strip()
    fecha_hasta = data.get("fecha_hasta", "").strip()

    filtros = ["1=1"]
    params = []

    if autoriza:
        filtros.append("autoriza_nombre LIKE ?")
        params.append(f"%{autoriza}%")
    if recibe:
        filtros.append("recibe_nombre LIKE ?")
        params.append(f"%{recibe}%")
    if municipio:
        filtros.append("municipio LIKE ?")
        params.append(f"%{municipio}%")
    if fecha_desde:
        filtros.append("fecha_lote >= ?")
        params.append(fecha_desde)
    if fecha_hasta:
        filtros.append("fecha_lote <= ?")
        params.append(fecha_hasta)

    clausula = " AND ".join(filtros)
    conn = get_db()
    c = conn.cursor()

    c.execute(f"""
        SELECT 
            COUNT(*) AS total_actas,
            SUM(alimento_perro_kg) AS perro_kg,
            SUM(alimento_gato_kg) AS gato_kg,
            SUM(total_alimento_seco_kg) AS total_seco_kg,
            SUM(comida_humeda_perro_und) AS hum_perro,
            SUM(comida_humeda_gato_und) AS hum_gato,
            SUM(arena_kg) AS arena_kg,
            SUM(huacales_und) AS huacales,
            SUM(areneros_und) AS areneros,
            SUM(recipientes_und) AS comederos,
            SUM(collares_und) AS collares,
            SUM(camas_und) AS camas,
            SUM(cobijas_und) AS cobijas
        FROM salidas_alimentos
        WHERE {clausula}
    """, params)
    kpi_res = c.fetchone() or {}

    c.execute(f"""
        SELECT s.*, 
               (SELECT COUNT(*) FROM salidas_medicamentos m WHERE m.codigo_acta_vinculante = s.codigo_acta_vinculante AND s.codigo_acta_vinculante != 'SIN_NUMERO') as num_meds
        FROM salidas_alimentos s
        WHERE {clausula}
        ORDER BY s.id DESC LIMIT 150
    """, params)
    resultados = c.fetchall()
    conn.close()

    return jsonify({
        "kpis": {
            "Actas Coincidentes": kpi_res.get("total_actas") or 0,
            "Perro (Kg)": round(kpi_res.get("perro_kg") or 0, 1),
            "Gato (Kg)": round(kpi_res.get("gato_kg") or 0, 1),
            "Total Seco (Kg)": round(kpi_res.get("total_seco_kg") or 0, 1),
            "Húmeda Perro": kpi_res.get("hum_perro") or 0,
            "Húmeda Gato": kpi_res.get("hum_gato") or 0,
            "Arena (Kg)": round(kpi_res.get("arena_kg") or 0, 1),
            "Huacales": kpi_res.get("huacales") or 0,
            "Areneros": kpi_res.get("areneros") or 0,
            "Comederos": kpi_res.get("comederos") or 0,
            "Collares": kpi_res.get("collares") or 0,
            "Camas": kpi_res.get("camas") or 0
        },
        "resultados": resultados
    })

# ==============================================================================
# SUBMENÚ 3: BUSCADOR (ACTAS Y TRAZABILIDAD)
# ==============================================================================

@app.route("/api/actas/buscar")
def api_actas_buscar():
    q = request.args.get("q", "").strip()
    fecha_desde = request.args.get("fecha_desde", "").strip()
    fecha_hasta = request.args.get("fecha_hasta", "").strip()
    
    filtros = ["1=1"]
    params = []
    if q:
        q_like = f"%{q}%"
        filtros.append("""(s.id_documento LIKE ? OR s.codigo_acta_vinculante LIKE ? OR s.autoriza_nombre LIKE ? 
           OR s.recibe_nombre LIKE ? OR s.municipio LIKE ? OR s.barrio_corregimiento_refugio LIKE ? 
           OR s.recibe_cedula LIKE ? OR s.autoriza_cedula LIKE ?)""")
        params.extend([q_like] * 8)
    if fecha_desde:
        filtros.append("s.fecha_lote >= ?")
        params.append(fecha_desde)
    if fecha_hasta:
        filtros.append("s.fecha_lote <= ?")
        params.append(fecha_hasta)

    clausula = " AND ".join(filtros)
    conn = get_db()
    c = conn.cursor()
    c.execute(f"""
        SELECT s.*, 
               (SELECT COUNT(*) FROM salidas_medicamentos m WHERE m.codigo_acta_vinculante = s.codigo_acta_vinculante AND s.codigo_acta_vinculante != 'SIN_NUMERO') as num_meds
        FROM salidas_alimentos s
        WHERE {clausula}
        ORDER BY s.id DESC LIMIT 120
    """, params)
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

@app.route("/api/actas/detalle/<id_doc>")
def api_actas_detalle(id_doc):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM salidas_alimentos WHERE id_documento = ?", (id_doc,))
    alimento = c.fetchone()
    if not alimento:
        conn.close()
        return jsonify({"error": "Acta no encontrada"}), 404
    
    cod_vinc = alimento.get("codigo_acta_vinculante", "SIN_NUMERO")
    medicamentos = []
    if cod_vinc and cod_vinc != "SIN_NUMERO":
        c.execute("""
            SELECT medicamento_insumo, cantidad, unidad, presentacion, categoria_farmacologica, archivo_imagen, id_documento
            FROM salidas_medicamentos
            WHERE codigo_acta_vinculante = ?
        """, (cod_vinc,))
        medicamentos = c.fetchall()
    
    conn.close()
    
    meds_cat = {}
    for m in medicamentos:
        cat = m.get("categoria_farmacologica") or "Otros Insumos Veterinarios"
        if cat not in meds_cat:
            meds_cat[cat] = []
        meds_cat[cat].append(m)

    return jsonify({
        "alimento": alimento,
        "medicamentos_por_categoria": meds_cat,
        "tiene_medicamentos": len(medicamentos) > 0
    })

# ==============================================================================
# SUBMENÚ 4: FARMACOLOGÍA
# ==============================================================================

@app.route("/api/farmacologia/datos")
def api_farmacologia_datos():
    mun = request.args.get("municipio", "").strip()
    q_med = request.args.get("q", "").strip()
    recibe = request.args.get("recibe", "").strip()
    autoriza = request.args.get("autoriza", "").strip()
    fecha_desde = request.args.get("fecha_desde", "").strip()
    fecha_hasta = request.args.get("fecha_hasta", "").strip()

    filtros = ["1=1"]
    params = []
    if mun:
        filtros.append("s.municipio LIKE ?")
        params.append(f"%{mun}%")
    if q_med:
        filtros.append("m.medicamento_insumo LIKE ?")
        params.append(f"%{q_med}%")
    if recibe:
        filtros.append("s.recibe_nombre LIKE ?")
        params.append(f"%{recibe}%")
    if autoriza:
        filtros.append("s.autoriza_nombre LIKE ?")
        params.append(f"%{autoriza}%")
    if fecha_desde:
        filtros.append("m.fecha_lote >= ?")
        params.append(fecha_desde)
    if fecha_hasta:
        filtros.append("m.fecha_lote <= ?")
        params.append(fecha_hasta)

    clausula = " AND ".join(filtros)
    conn = get_db()
    c = conn.cursor()

    c.execute(f"""
        SELECT 
            m.medicamento_insumo, m.cantidad, m.unidad, m.presentacion,
            m.categoria_farmacologica, m.codigo_acta_vinculante, m.archivo_imagen,
            s.municipio, s.recibe_nombre, s.autoriza_nombre, s.id_documento, m.fecha_lote
        FROM salidas_medicamentos m
        LEFT JOIN salidas_alimentos s ON m.codigo_acta_vinculante = s.codigo_acta_vinculante AND s.codigo_acta_vinculante != 'SIN_NUMERO'
        WHERE {clausula}
        ORDER BY m.id DESC LIMIT 500
    """, params)
    filas = c.fetchall()
    conn.close()

    categorias_est = {
        "Material Quirúrgico y Curación": {"total_items": 0, "total_unidades": 0, "meds": {}},
        "Otros Insumos Veterinarios": {"total_items": 0, "total_unidades": 0, "meds": {}},
        "Analgésicos y Antiinflamatorios": {"total_items": 0, "total_unidades": 0, "meds": {}},
        "Fluidoterapia y Sueros": {"total_items": 0, "total_unidades": 0, "meds": {}},
        "Antibióticos": {"total_items": 0, "total_unidades": 0, "meds": {}},
        "Vitaminas y Suplementos": {"total_items": 0, "total_unidades": 0, "meds": {}},
        "Antiparasitarios y Purgantes": {"total_items": 0, "total_unidades": 0, "meds": {}},
        "Anestésicos y Sedantes": {"total_items": 0, "total_unidades": 0, "meds": {}},
        "Vacunas y Biológicos": {"total_items": 0, "total_unidades": 0, "meds": {}}
    }

    for f in filas:
        cat = f.get("categoria_farmacologica") or "Otros Insumos Veterinarios"
        if cat not in categorias_est:
            categorias_est[cat] = {"total_items": 0, "total_unidades": 0, "meds": {}}
        
        cant = float(f["cantidad"] or 0)
        categorias_est[cat]["total_items"] += 1
        categorias_est[cat]["total_unidades"] += cant

        nom = f["medicamento_insumo"].strip().upper()
        if nom not in categorias_est[cat]["meds"]:
            categorias_est[cat]["meds"][nom] = {"cantidad_total": 0.0, "unidad": f["unidad"], "entregas": []}
        
        categorias_est[cat]["meds"][nom]["cantidad_total"] += cant
        categorias_est[cat]["meds"][nom]["entregas"].append({
            "recibe": f["recibe_nombre"] or "Albergue / Refugio",
            "autoriza": f["autoriza_nombre"] or "N/A",
            "municipio": f["municipio"] or "Valle del Cauca",
            "acta": f["codigo_acta_vinculante"] or f["id_documento"],
            "foto": f["archivo_imagen"],
            "fecha": f["fecha_lote"] or "N/A"
        })

    return jsonify({"categorias": categorias_est, "registros_totales": len(filas)})

# ==============================================================================
# SUBMENÚ 5: ALBERGUES (CENSO EDAN)
# ==============================================================================

@app.route("/api/censo/datos")
def api_censo_datos():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM censo_emergencias_refugios ORDER BY total_animales_censados DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

# ==============================================================================
# SUBMENÚ 6: VOLUNTARIOS (RED HUMANA Y AUDITORÍA)
# ==============================================================================

@app.route("/api/red-humana/datos")
def api_red_humana_datos():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM donaciones_voluntarios ORDER BY id DESC")
    donantes = c.fetchall()
    c.execute("SELECT * FROM voluntarios_operativos ORDER BY id DESC")
    voluntarios = c.fetchall()
    c.execute("SELECT * FROM voluntarios_transporte ORDER BY id DESC")
    transportistas = c.fetchall()
    conn.close()
    return jsonify({
        "donantes": donantes,
        "voluntarios": voluntarios,
        "transportistas": transportistas,
        "kpis": {
            "total_donantes": len(donantes),
            "total_voluntarios": len(voluntarios),
            "total_transporte": len(transportistas),
            "trazabilidad": "100%"
        }
    })

@app.route("/api/red-humana/historial/<path:nombre>")
def api_red_humana_historial(nombre):
    conn = get_db()
    c = conn.cursor()
    nombre_clean = nombre.strip()
    q_like = f"%{nombre_clean}%"
    c.execute("""
        SELECT id_documento, codigo_acta_vinculante, fecha_lote, municipio, barrio_corregimiento_refugio,
               autoriza_nombre, recibe_nombre, total_alimento_seco_kg, alimento_perro_kg, alimento_gato_kg, archivo_imagen
        FROM salidas_alimentos
        WHERE autoriza_nombre LIKE ? OR recibe_nombre LIKE ?
        ORDER BY fecha_lote DESC LIMIT 60
    """, (q_like, q_like))
    historial = c.fetchall()
    conn.close()
    return jsonify(historial)

# ==============================================================================
# INICIO SERVIDOR
# ==============================================================================

if __name__ == "__main__":
    print("\n=======================================================")
    print("   🚀 API BACKEND SISMO 2026 - ACTIVA (PUERTO 5001)")
    print("   Servidor iniciado en: http://127.0.0.1:5001")
    print("=======================================================\n")
    app.run(debug=True, host="0.0.0.0", port=5001)