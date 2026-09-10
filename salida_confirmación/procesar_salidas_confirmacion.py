import json
import logging
import re
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageEnhance, ImageOps
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# 1. Silenciar logs de bajo nivel
logging.getLogger("google_genai").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning)

# ==============================================================================
# 2. CONFIGURACIÓN DE RUTAS Y CLIENTE API
# ==============================================================================
API_KEY = "AQ.Ab8RN6LBz47MPFu4W2AtJ65WBH82IibEyQuDdNubmUriBbf6EA"
client = genai.Client(api_key=API_KEY)
MODELO_UNICO = "gemini-3.1-flash-lite"

# Directorio base: carpeta actual donde reside este script
BASE_DIR = Path(__file__).resolve().parent

# Rutas internas directas
DIR_SCAN_ACTAS = BASE_DIR / "actas" / "scan" / "actas"
DIR_PROCESADAS = BASE_DIR / "actas" / "procesadas"
DIR_JSON = BASE_DIR / "json"
ARCHIVO_CONSECUTIVO = BASE_DIR / "consecutivo_salida.txt"
ARCHIVO_INFORME = BASE_DIR / "informe_revision_manual.txt"

# Parámetros de optimización visual
MAX_ALTO = 1100
CORTE_BLANCOS = 1.5
FACTOR_CONTRASTE = 1.35
CALIDAD_JPEG = 70
PAUSA_ENTRE_LLAMADAS = 0.6

# ==============================================================================
# 3. ESQUEMA ESTRUCTURADO (PYDANTIC)
# ==============================================================================
class ItemOtroInsumo(BaseModel):
    articulo: str = Field(description="Nombre del artículo no contemplado en las casillas fijas")
    cantidad: float = Field(0.0, description="Cantidad numérica")
    unidad: str = Field("", description="Unidad de medida (und, paquete, rollo, etc.)")

class ActaSalidaSchema(BaseModel):
    codigo_acta_vinculante: str = Field(
        description="Código manuscrito de vinculación en formato A-001, A-010, A-101, etc. Si NO existe en esquinas/márgenes, colocar estrictamente 'SIN_NUMERO'."
    )
    municipio: str = Field(
        description="Nombre oficial del municipio cabecera según el diccionario del Valle. Si es Chocó o Quindío, colocar 'Otro Departamento'. Si dice 'Norte del Valle' o 'Valle del Cauca' sin especificar municipio, colocar tal cual 'REVISAR_VALLE'."
    )
    barrio_corregimiento_refugio: str = Field(
        "", description="Corregimiento, vereda, barrio o refugio identificado."
    )
    autoriza_nombre: str = Field(
        "", description="Nombre manuscrito de quien autoriza/entrega. IGNORAR COMPLETAMENTE el nombre preimpreso 'LIZETH JOHANA PARRA GONZÁLEZ' del membrete."
    )
    autoriza_cedula: str = Field("", description="Cédula de quien autoriza")
    recibe_nombre: str = Field("", description="Nombre manuscrito de quien recibe")
    recibe_cedula: str = Field("", description="Cédula de quien recibe")
    
    # Cantidades
    alimento_perro_kg: float = Field(0.0, description="Kilos de concentrado/comida seca para perro")
    alimento_gato_kg: float = Field(0.0, description="Kilos de concentrado/comida seca para gato")
    comida_humeda_perro_und: int = Field(0, description="Unidades (latas/sobres/pouch) de húmeda para perro")
    comida_humeda_gato_und: int = Field(0, description="Unidades (latas/sobres/pouch) de húmeda para gato")
    arena_kg: float = Field(0.0, description="Kilos de arena sanitaria. Si dice 'bolsa' = 4kg cada una; si dice 'bulto' = 12kg cada uno; si dice kg directo, usa ese valor.")
    areneros_und: int = Field(0, description="Areneros o bandejas sanitarias")
    recipientes_und: int = Field(0, description="Comederos, platos, bebederos o tazas")
    huacales_und: int = Field(0, description="Guacales, huacales o transportadores")
    collares_und: int = Field(0, description="Collares, correas o traíllas")
    camas_und: int = Field(0, description="Camas, tapetes o espumas para dormir")
    cobijas_und: int = Field(0, description="Cobijas, sábanas o mantas")
    insumos_medicos_und: int = Field(0, description="Kits veterinarios, botiquines o insumos médicos generales contados por unidad")
    otros_articulos: List[ItemOtroInsumo] = Field(default_factory=list, description="Artículos adicionales que no encajan en las categorías anteriores")

# ==============================================================================
# 4. PROMPT CON DICCIONARIO GEOGRÁFICO INTEGRADO
# ==============================================================================
PROMPT_EXTRACCION = """
Actúa como un perito auditor y analista de datos de auxilio animal para el Valle del Cauca, Colombia.
Analiza con rigor la imagen del acta de salida y extrae los datos siguiendo estas reglas obligatorias:

1. CÓDIGO VINCULANTE (codigo_acta_vinculante):
   - Busca en márgenes o esquinas el código manuscrito de enlace con medicamentos (formato A-001, A-010, A-101, etc.).
   - Si no hay código escrito a mano, coloca 'SIN_NUMERO'.

2. DICCIONARIO GEOGRÁFICO (MUNICIPIO Y CORREGIMIENTOS):
   Si en el acta solo dice el corregimiento/barrio, asígnalo obligatoriamente a su municipio correspondiente:
   - Santiago de Cali: Navarro, El Hormiguero, Pance, Villacarmelo, La Buitrera, Los Andes, Pichindé, Felidia, Leonera, El Saladito, La Elvira, La Castilla, La Paz, Golondrinas, Montebello.
   - Jamundí: Robles, Quinamayó, Villa Paz, Timba, Potrerito, San Antonio, Ampudia, Paso de la Bolsa, Guachinte, Chagres, Bocas del Palo, Puente Vélez.
   - Palmira: Rozo, La Acequia, La Herradura, Obando, Matapalo, Coronado, Zamorano, Ciudad del Campo, Guanabanal, Palmaseca, El Bolo, Bolo Alape, Amaime, El Placer, Boyacá, La Quisquina, Combia, Toche, Calucé, Potrerillo, Tienda Nueva, La Pampa, Barrancas, Tablones, Santa Elena, El Recreo.
   - Yumbo: Dapa, Arroyohondo, Mulaló, San Marcos, Yumbillo, Santa Inés, Montañitas, La Olga.
   - Candelaria: Villagorgona, El Carmelo, Poblado Campestre, Buchitolo, Cavasa, San Joaquín, Juanchito, El Lauro, La Regina, Cabuyal.
   - Pradera: Bolo Azul, Bolo Blanco, El Retiro, La Fría, La Feria, Lomitas, Potrerito, San Antonio, Valparaíso.
   - Florida: El Llanito, San Antonio de los Caballeros, El Chocó, La Diana, San Francisco, Pueblo Nuevo, Tarragona.
   - Dagua: Borrero Ayerbe (Km 30), El Queremal, El Carmen, Atuncela, La Cascada, Providencia, Loboguerrero, Danubio, San José del Salado, El Limonar, La Elsa, San Bernardo, Jiguales, Santa María del Palmar.
   - La Cumbre: Pavas, Bitaco, Lomitas, Arboledas, La María, Jiguales.
   - Vijes: Carbonero, Caxibío, El Oconó, La Rivera, Miravalle, Portugalo, San Antonio, Santa Inés, Villa María.
   - Tuluá: La Marina, La Moralia, Nariño, Bocas de Tuluá, Tres Esquinas, Campoalegre, Aguaclara, San Lorenzo, Puerto Frazadas, San Rafael, Monteloro, Barragán, Santa Lucía, La Iberia, El Picacho, La Diadema, Venus, Quebradagrande.
   - Guadalajara de Buga: Chambimbal, El Vínculo, Quebradaseca, La Magdalena, La Habana, El Placer, Presidente, Zanjón Hondo, Los Chancos, Frías, Miraflores.
   - Andalucía: Altaflor, Campoalegre, El Salto, Pardo Zabaletas, Tamboral, Potrerillo, Monte Hermoso.
   - Bugalagrande: El Overo, Ceilán, Galicia, Mestizal, Guayabo, San Antonio, Paila Arriba, Chorreras.
   - San Pedro: Todos Santos, Buenos Aires, Presidente, Los Chancos, San José, Potrerillo.
   - Riofrío: Fenicia, Salónica, Portugal de Piedras, La Zulia, Madroñal, Cuernavaca.
   - Trujillo: Venecia, Huasano, Andinápolis, Robledo, Sonora, Cerro Azul, La Sonora, Cristales.
   - El Cerrito: Santa Elena, San Antonio, El Castillo, El Placer, Santa Luisa, Los Andes, Tenerife, El Pital, Carrizal.
   - Ginebra: Costa Rica, Juntas, Cocorná, La Floresta, Los Andes, La Selva.
   - Guacarí: Guabitas, Sonso, Cananguá, Santa Rosa de Tapias, Puente Rojo.
   - Yotoco: Mediacanoa, Jiguales, El Caney, Miravalle, Rayambá.
   - Restrepo: Madroñal, San Salvador, Ilama, Palma de Vino, Román, San Joaquín.
   - Calima - El Darién: Río Bravo, La Primavera, Jiguales, El Diamante, La Unión.
   - Cartago: Zaragoza, Santa Ana, Modín, Piedras de Moler, Coloradas, Guanabanal.
   - Zarzal: La Paila, Vallejuelo, Limones, Quebradanueva, Guasimal, La Caña.
   - Roldanillo: El Retiro, Higueroncito, Morelia, Montañuelas, Santa Rita, Matapalo, Buenavista, Isaza.
   - Sevilla: San Antonio, Ceilán, Palomino, Corozal, La Cuchilla, Venecia, Quebradanueva, Manzanillo, La María.
   - Caicedonia: Samaria, Aures, Puerto Rico, Montegrande, La Rivera, La Suiza, Barragán.
   - La Unión: San Luis, La Campiña, Córcega, Santa Elena, Quebrada Grande.
   - La Victoria: Holguín, San Pedro, Miravalles, San José, Riveralta.
   - Alcalá: La Cuchilla, Maravélez, La Estrella, El Congal, La Caña.
   - Ansermanuevo: El Billar, Gramalote, El Vergel, Chocó, La Puerta, San Agustín.
   - Argelia: El Silencio, El Pital, Guadalupe, Maracaibo, Santa Inés.
   - Bolívar: Ricaurte, Naranjal, Primavera, Betania, Guaduas, San Fernando, La Tulia.
   - El Águila: Villanueva, San José, La María, Santa Marta, Espartillal.
   - El Cairo: Albán, El Pacífico, La Italia, Buenos Aires.
   - El Dovio: Lituania, Mateguadua, Bitaco, Playa Rica.
   - Obando: Villa Rodas, San Isidro, Santa Bárbara, Cruces.
   - Toro: San Antonio, San Francisco, Bohío, La Pradera.
   - Ulloa: Calambrina, Chapinero, Moctezuma, Sucre.
   - Versalles: La Florida, Campoalegre, El Balsal, Puerto Nuevo.
   - Buenaventura: Cisneros, Córdoba, San Pedro de Naya, Puerto Merizalde, Yurumanguí, Bahía Málaga, Juanchaco, Ladrilleros, La Bocana, Punta Soldado, Zacarías, Triana, Silva, Gamboa, Sabaletas, Aguaclara, Mayorquín, Bajo Calima, San Cipriano.
   * REGLAS ESPECIALES DE DESTINO:
     - Si dice 'Chocó' o 'Quindío' (ej. Montenegro) -> municipio: 'Otro Departamento', y anotas el lugar en barrio_corregimiento_refugio.
     - Si solo dice 'Norte del Valle' o 'Valle del Cauca' sin municipio identificable -> municipio: 'REVISAR_VALLE'.

3. REGLAS DE CONVERSIÓN Y RAZONAMIENTO EN INSUMOS:
   - Alimento seco: Si dice 'Perro 8' o 'Canino 8' -> 8.0 kg en alimento_perro_kg.
   - Arena: Si dice '3 bolsas de arena' -> multiplica 3 * 4kg = 12.0 kg. Si dice '2 bultos de arena' -> multiplica 2 * 12kg = 24.0 kg. Si da kilos directos, usa los kilos.
   - Comida húmeda: Sobres, latas o pouch van en unidades. Si dice '50/50' -> 50 a perro y 50 a gato.
   - Ropa/Cobijas: Sábanas, mantas, toallas van en cobijas_und.
   - Descanso: Camas, tapetes, colchonetas, espumas van en camas_und.
   - Insumos médicos: Kits veterinarios, insumos clínicos o botiquines contables van en insumos_medicos_und.
   - Si un artículo no encaja en ninguna casilla fija (ej: tijeras, bozales, guantes), agrégalo en 'otros_articulos'.

4. FIRMAS Y AUTORIZACIÓN:
   - IGNORA por completo el texto preimpreso 'LIZETH JOHANA PARRA GONZÁLEZ'. Extrae únicamente los nombres y cédulas manuscritos en los renglones correspondientes.
"""

# ==============================================================================
# 5. FUNCIONES DE PROCESAMIENTO Y CONTROL
# ==============================================================================
def inicializar_entorno():
    DIR_PROCESADAS.mkdir(parents=True, exist_ok=True)
    DIR_JSON.mkdir(parents=True, exist_ok=True)
    if not ARCHIVO_INFORME.exists():
        with open(ARCHIVO_INFORME, "w", encoding="utf-8") as f:
            f.write("====================================================================\n")
            f.write("   INFORME DE AUDITORÍA Y CASOS PARA REVISIÓN MANUAL (SALIDAS)\n")
            f.write("====================================================================\n\n")

def obtener_ultimo_consecutivo() -> int:
    """Lee el último consecutivo AS-XXXXXX registrado."""
    ultimo = 0
    if ARCHIVO_CONSECUTIVO.exists():
        try:
            with open(ARCHIVO_CONSECUTIVO, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val.isdigit():
                    ultimo = int(val)
        except Exception:
            pass

    patron = re.compile(r"^AS-(\d{6})\.(jpg|json)$", re.IGNORECASE)
    for carpeta in [DIR_PROCESADAS, DIR_JSON]:
        if carpeta.exists():
            for f in carpeta.iterdir():
                m = patron.match(f.name)
                if m:
                    n = int(m.group(1))
                    if n > ultimo:
                        ultimo = n
    return ultimo

def guardar_consecutivo(numero: int):
    try:
        with open(ARCHIVO_CONSECUTIVO, "w", encoding="utf-8") as f:
            f.write(str(numero))
    except Exception as e:
        print(f"[!] Error guardando consecutivo: {e}")

def registrar_alerta_informe(nombre_acta: str, razon: str, detalle: str = ""):
    with open(ARCHIVO_INFORME, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {nombre_acta}.jpg | {nombre_acta}.json\n")
        f.write(f"   • Motivo:  {razon}\n")
        if detalle:
            f.write(f"   • Detalle: {detalle}\n")
        f.write("-" * 68 + "\n")

def optimizar_imagen(ruta_origen: Path, ruta_destino: Path):
    """Aplica escala de grises, autocontraste, realce y redimensionado a 1100px."""
    with Image.open(ruta_origen) as img:
        img = ImageOps.exif_transpose(img)
        img_gray = img.convert("L")
        img_clean = ImageOps.autocontrast(img_gray, cutoff=CORTE_BLANCOS)
        enhancer = ImageEnhance.Contrast(img_clean)
        img_contrast = enhancer.enhance(FACTOR_CONTRASTE)
        img_contrast.thumbnail((MAX_ALTO, MAX_ALTO), Image.Resampling.LANCZOS)
        img_contrast.save(
            ruta_destino,
            format="JPEG",
            quality=CALIDAD_JPEG,
            optimize=True,
            progressive=True
        )

def consultar_ia(ruta_imagen: Path, con_pensamiento: bool = False) -> tuple[dict, dict, float]:
    """Llama a la API con o sin presupuesto de pensamiento."""
    img = Image.open(ruta_imagen)
    t_config = types.ThinkingConfig(thinking_budget=2048) if con_pensamiento else types.ThinkingConfig(thinking_budget=0)
    
    t0 = time.time()
    resp = client.models.generate_content(
        model=MODELO_UNICO,
        contents=[img, PROMPT_EXTRACCION],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ActaSalidaSchema,
            temperature=0.0,
            thinking_config=t_config
        )
    )
    duracion = round(time.time() - t0, 2)
    meta = resp.usage_metadata
    tokens_info = {
        "in": meta.prompt_token_count,
        "out": meta.candidates_token_count,
        "total": meta.total_token_count
    }
    return resp.parsed.model_dump(), tokens_info, duracion

def son_datos_equivalentes(d1: dict, d2: dict) -> tuple[bool, str]:
    """Valida si las dos consultas independientes concuerdan en las variables críticas."""
    campos_numericos = [
        "alimento_perro_kg", "alimento_gato_kg",
        "comida_humeda_perro_und", "comida_humeda_gato_und",
        "arena_kg", "areneros_und", "huacales_und",
        "camas_und", "cobijas_und", "recipientes_und"
    ]
    for c in campos_numericos:
        if abs(float(d1.get(c, 0.0) or 0.0) - float(d2.get(c, 0.0) or 0.0)) > 0.01:
            return False, f"Discrepancia en {c}: {d1.get(c)} vs {d2.get(c)}"

    cod1 = (d1.get("codigo_acta_vinculante") or "").strip().upper()
    cod2 = (d2.get("codigo_acta_vinculante") or "").strip().upper()
    if cod1 != cod2:
        return False, f"Discrepancia en código acta: '{cod1}' vs '{cod2}'"

    mun1 = (d1.get("municipio") or "").strip().upper()
    mun2 = (d2.get("municipio") or "").strip().upper()
    if mun1 != mun2:
        return False, f"Discrepancia en municipio: '{mun1}' vs '{mun2}'"

    return True, "OK"

# ==============================================================================
# 6. BUCLE PRINCIPAL DE PROCESAMIENTO
# ==============================================================================
def ejecutar():
    inicializar_entorno()
    
    print("\n" + "=" * 75)
    print("   SISTEMA DE CONFIRMACIÓN Y RE-EXTRACCIÓN: ACTAS DE SALIDA")
    print(f"   Origen de escaneos: {DIR_SCAN_ACTAS.resolve()}")
    print(f"   Destino JSONs:      {DIR_JSON.resolve()}")
    print("=" * 75 + "\n")

    if not DIR_SCAN_ACTAS.exists():
        print(f"[!] Error: No se encontró la ruta {DIR_SCAN_ACTAS.resolve()}")
        return

    # Buscar subcarpetas de días (12 al 19)
    subcarpetas_dias = []
    for p in DIR_SCAN_ACTAS.iterdir():
        if p.is_dir() and p.name.isdigit():
            subcarpetas_dias.append(p)
    subcarpetas_dias.sort(key=lambda p: int(p.name))

    if not subcarpetas_dias:
        print("[!] No se encontraron carpetas con números de día (12-19) en la ruta de escaneo.")
        return

    consecutivo_actual = obtener_ultimo_consecutivo()
    print(f"• Último consecutivo registrado: AS-{consecutivo_actual:06d}")
    print(f"• Carpetas de días detectadas:  {[d.name for d in subcarpetas_dias]}\n")

    total_procesadas_tanda = 0
    extensiones = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".bmp", ".tif", ".tiff"}

    for carpeta_dia in subcarpetas_dias:
        dia_num = int(carpeta_dia.name)
        fecha_lote = f"2026-08-{dia_num:02d}"
        
        fotos = [f for f in carpeta_dia.iterdir() if f.is_file() and f.suffix in extensiones]
        fotos.sort(key=lambda f: (f.stat().st_mtime, f.name))

        if not fotos:
            continue

        print(f"📁 --- INICIANDO DÍA {dia_num} ({fecha_lote}) | {len(fotos)} Actas Detectadas ---")

        for foto_cruda in fotos:
            consecutivo_actual += 1
            nombre_estandar = f"AS-{consecutivo_actual:06d}"
            ruta_foto_procesada = DIR_PROCESADAS / f"{nombre_estandar}.jpg"
            ruta_json_final = DIR_JSON / f"{nombre_estandar}.json"

            # 1. Modo de reanudación
            if ruta_json_final.exists() and ruta_foto_procesada.exists():
                print(f"   [{nombre_estandar}] Ya existe. Saltando...")
                continue

            print(f"\n▶ [{nombre_estandar}] Procesando: {foto_cruda.name} (Día {dia_num})...")

            try:
                # 2. Optimizar imagen
                optimizar_imagen(foto_cruda, ruta_foto_procesada)

                # 3. Doble pasada con IA (Zero-Thinking)
                print("   ├─ [IA Pasada 1/2] Extrayendo datos...")
                d1, tok1, dur1 = consultar_ia(ruta_foto_procesada, con_pensamiento=False)
                time.sleep(PAUSA_ENTRE_LLAMADAS)

                print("   ├─ [IA Pasada 2/2] Verificando concordancia...")
                d2, tok2, dur2 = consultar_ia(ruta_foto_procesada, con_pensamiento=False)

                coinciden, motivo = son_datos_equivalentes(d1, d2)
                datos_finales = None
                arbitrada_con_pensamiento = False

                if coinciden:
                    print("   ├─ ✅ Verificación Exitosa: Ambas lecturas coinciden al 100%.")
                    datos_finales = d1
                else:
                    print(f"   ├─ ⚠️ {motivo}. Activando árbitro con PENSAMIENTO...")
                    d3, tok3, dur3 = consultar_ia(ruta_foto_procesada, con_pensamiento=True)
                    datos_finales = d3
                    arbitrada_con_pensamiento = True
                    registrar_alerta_informe(
                        nombre_estandar,
                        "Discrepancia en doble verificación - Resuelto con Pensamiento",
                        f"P1 vs P2: {motivo}"
                    )

                # 4. Validar alertas de municipio para el informe
                mun_final = datos_finales.get("municipio", "").strip()
                if mun_final in ["REVISAR_VALLE", "", "SIN_DATO"]:
                    registrar_alerta_informe(
                        nombre_estandar,
                        "Municipio ambiguo o no identificado",
                        f"Texto detectado en lugar: '{datos_finales.get('barrio_corregimiento_refugio')}'"
                    )

                # 5. Construir y guardar paquete JSON final
                p_kg = float(datos_finales.get("alimento_perro_kg", 0.0) or 0.0)
                g_kg = float(datos_finales.get("alimento_gato_kg", 0.0) or 0.0)
                tot_seco = round(p_kg + g_kg, 2)
                h_p = int(datos_finales.get("comida_humeda_perro_und", 0) or 0)
                h_g = int(datos_finales.get("comida_humeda_gato_und", 0) or 0)

                paquete_json = {
                    "id_documento": nombre_estandar,
                    "archivo_imagen": f"{nombre_estandar}.jpg",
                    "archivo_origen_escaneo": foto_cruda.name,
                    "fecha_lote": fecha_lote,
                    "dia_agosto": dia_num,
                    "tipo_documento": "ALIMENTOS",
                    "codigo_acta_vinculante": datos_finales.get("codigo_acta_vinculante", "SIN_NUMERO"),
                    "municipio": mun_final,
                    "barrio_corregimiento_refugio": datos_finales.get("barrio_corregimiento_refugio", ""),
                    "autoriza_entrega": {
                        "nombre": datos_finales.get("autoriza_nombre", ""),
                        "cedula": datos_finales.get("autoriza_cedula", "")
                    },
                    "recibe": {
                        "nombre": datos_finales.get("recibe_nombre", ""),
                        "cedula": datos_finales.get("recibe_cedula", "")
                    },
                    "datos_alimentos": {
                        "alimento_perro_kg": p_kg,
                        "alimento_gato_kg": g_kg,
                        "total_alimento_seco_kg": tot_seco,
                        "comida_humeda_perro_und": h_p,
                        "comida_humeda_gato_und": h_g,
                        "comida_humeda_total_und": h_p + h_g,
                        "arena_kg": float(datos_finales.get("arena_kg", 0.0) or 0.0),
                        "areneros_und": int(datos_finales.get("areneros_und", 0) or 0),
                        "camas_und": int(datos_finales.get("camas_und", 0) or 0),
                        "cobijas_und": int(datos_finales.get("cobijas_und", 0) or 0),
                        "recipientes_und": int(datos_finales.get("recipientes_und", 0) or 0),
                        "huacales_und": int(datos_finales.get("huacales_und", 0) or 0),
                        "collares_und": int(datos_finales.get("collares_und", 0) or 0),
                        "insumos_medicos_und": int(datos_finales.get("insumos_medicos_und", 0) or 0),
                        "otros_articulos_adicionales": datos_finales.get("otros_articulos", [])
                    },
                    "metadatos_auditoria": {
                        "arbitrada_con_pensamiento": arbitrada_con_pensamiento,
                        "fecha_procesamiento": datetime.now().isoformat()
                    }
                }

                with open(ruta_json_final, "w", encoding="utf-8") as f:
                    json.dump(paquete_json, f, ensure_ascii=False, indent=2)

                # 6. Actualizar consecutivo en disco
                guardar_consecutivo(consecutivo_actual)
                total_procesadas_tanda += 1

                print(f"   └─ 💾 Guardado {nombre_estandar}.json | Perro: {p_kg} Kg | Gato: {g_kg} Kg | Destino: {mun_final} | Enlace: {datos_finales.get('codigo_acta_vinculante')}")

            except Exception as e:
                print(f"   [!] ERROR CRÍTICO en {foto_cruda.name}: {e}")
                registrar_alerta_informe(nombre_estandar, f"Error en ejecución: {e}", foto_cruda.name)
                consecutivo_actual -= 1  # Revertir incremento si falló

            time.sleep(PAUSA_ENTRE_LLAMADAS)

    print("\n" + "=" * 75)
    print("                    PROCESO FINALIZADO CON ÉXITO")
    print("=" * 75)
    print(f"• Total actas procesadas en esta jornada: {total_procesadas_tanda}")
    print(f"• Consecutivo final alcanzado:            AS-{consecutivo_actual:06d}")
    print(f"• Carpeta de imágenes optimizadas:        {DIR_PROCESADAS.resolve()}")
    print(f"• Carpeta de archivos JSON:               {DIR_JSON.resolve()}")
    print(f"• Informe de casos para revisión:         {ARCHIVO_INFORME.resolve()}")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    ejecutar()