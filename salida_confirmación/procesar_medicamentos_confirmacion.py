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

# 1. Silenciar logs informativos
logging.getLogger("google_genai").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning)

# ==============================================================================
# 2. CONFIGURACIÓN DE RUTAS Y CLIENTE API
# ==============================================================================
API_KEY = "AQ.Ab8RN6LBz47MPFu4W2AtJ65WBH82IibEyQuDdNubmUriBbf6EA"
client = genai.Client(api_key=API_KEY)
MODELO_UNICO = "gemini-3.1-flash-lite"

# Directorio base (carpeta actual donde reside este script: salida_confirmacion/)
BASE_DIR = Path(__file__).resolve().parent

# Rutas internas relativas
DIR_SCAN_MEDS = BASE_DIR / "actas" / "scan" / "medicamentos"
DIR_PROCESADAS_MEDS = BASE_DIR / "actas" / "procesadas_medicamentos"
DIR_JSON = BASE_DIR / "json"
ARCHIVO_CONSECUTIVO = BASE_DIR / "consecutivo_medicamentos.txt"

# Parámetros de optimización visual (Consumo mínimo de tokens)
MAX_ALTO = 1100
CORTE_BLANCOS = 1.5
FACTOR_CONTRASTE = 1.35
CALIDAD_JPEG = 70
PAUSA_ENTRE_LLAMADAS = 0.5

# ==============================================================================
# 3. ESQUEMA ESTRUCTURADO Y CATEGORIZACIÓN CLÍNICA (PYDANTIC)
# ==============================================================================
class ItemMedicamentoSalida(BaseModel):
    medicamento_insumo: str = Field(
        description="Nombre comercial o genérico del medicamento o insumo médico veterinario (ej. Enrofloxacina, Meloxicam, Catéter 22G)"
    )
    categoria_farmacologica: str = Field(
        description="Categoría clínica veterinaria: 'Antibióticos', 'Analgésicos y Antiinflamatorios', 'Antiparasitarios y Purgantes', 'Anestésicos y Sedantes', 'Fluidoterapia y Sueros', 'Vacunas y Biológicos', 'Material Quirúrgico y Curación', 'Vitaminas y Suplementos', 'Otros Insumos Veterinarios'"
    )
    cantidad: float = Field(0.0, description="Cantidad numérica exacta entregada")
    unidad: str = Field(
        "", description="Unidad de medida (frascos, ampollas, tabletas, cajas, ml, bolsas, unidades, viales, etc.)"
    )
    presentacion: Optional[str] = Field(
        "", description="Concentración, volumen o presentación si aparece anotado (ej. 10%, 100ml, 500mg, x 10 tab)"
    )

class ActaMedicamentosSchema(BaseModel):
    codigo_acta_vinculante: str = Field(
        description="Código manuscrito de vinculación en formato A-001, A-010, A-101, etc., visible en esquinas o encabezado. Si no hay código visible, colocar estrictamente 'SIN_NUMERO'."
    )
    fecha_documento_detectada: Optional[str] = Field(
        "", description="Fecha visible en la planilla si está anotada"
    )
    municipio_o_lugar: Optional[str] = Field(
        "", description="Municipio, sede o albergue si aparece anotado en el encabezado"
    )
    recibe_nombre: Optional[str] = Field(
        "", description="Nombre manuscrito de quien recibe si aparece en el renglón de firma"
    )
    autoriza_nombre: Optional[str] = Field(
        "", description="Nombre manuscrito de quien autoriza (ignorar textos preimpresos)"
    )
    medicamentos: List[ItemMedicamentoSalida] = Field(
        default_factory=list,
        description="Lista completa de fármacos e insumos médicos veterinarios extraídos"
    )

# ==============================================================================
# 4. PROMPT CONTEXTUALIZADO EN FARMACOLOGÍA VETERINARIA
# ==============================================================================
PROMPT_MEDICAMENTOS = """
Actúa como un perito farmacéutico y auditor veterinario especializado en control de suministros clínicos de auxilio animal.
Analiza con rigor esta acta/planilla de salida de MEDICAMENTOS E INSUMOS VETERINARIOS y extrae los datos con las siguientes directrices:

1. CÓDIGO VINCULANTE (codigo_acta_vinculante):
   - Busca en márgenes, encabezado o esquinas el código manuscrito que inicia con 'A-' (ej: A-001, A-010, A-101, A-024, etc.).
   - Este código vincula esta planilla con el acta general de alimentos. Si no existe ningún código tipo A-XXX, coloca estrictamente 'SIN_NUMERO'.

2. RESOLUCIÓN DE AMBIGÜEDADES CALIGRÁFICAS EN MEDICAMENTOS:
   - Todo el contenido de esta hoja corresponde EXCLUSIVAMENTE a fármacos, biológicos, desinfectantes e insumos clínicos veterinarios.
   - Si un trazo o palabra es confuso, interpreta y normaliza según los principios activos y marcas veterinarias habituales:
     * Antibióticos / Antimicrobianos: Enrofloxacina, Cefalexina, Doxiciclina, Amoxicilina (+ Ácido Clavulánico), Metronidazol, Penicilina, Gentamicina, Oxitetraciclina, Sulfas / Trimetoprim.
     * Analgésicos y AINEs: Meloxicam, Ketoprofeno, Carprofeno, Dipirona, Tramadol, Dexametasona, Prednisolona, Flunixin Meglumine.
     * Antiparasitarios / Purgantes: Ivermectina, Febantel, Praziquantel, Albendazol, Fipronil, Pirantel, Pamoato, Bravecto, Nexgard, Simparica, Endovet.
     * Anestésicos / Sedantes: Ketamina, Xilacina, Acepromacina, Propofol, Lidocaína, Zolazepam.
     * Fluidoterapia: Lactato de Ringer, Solución Salina (SSN 0.9%), Dextrosa, Hartmann.
     * Vacunas / Biológicos: Rabia, Triple Felina, Parvovirus, Distemper, Nobivac, Feligen.
     * Material Quirúrgico y Curación: Jeringas (1ml, 3ml, 5ml, 10ml, 20ml), catéteres o yencos (calibres 18G, 20G, 22G, 24G), agujas, gasas estériles, guantes quirúrgicos, suturas (Catgut cromado, Nylon, Vicryl), hojas de bisturí, clorhexidina, yodopovidona, esparadrapo, vendas.

3. CLASIFICACIÓN POR CATEGORÍA CLÍNICA:
   - Clasifica cada ítem dentro de su campo 'categoria_farmacologica' usando exactamente una de las categorías descritas en el esquema.

4. CANTIDADES Y UNIDADES:
   - Extrae el número exacto y su unidad física (frascos, tabletas, cajas, ampollas, ml, bolsas, rollos, unidades, etc.).
"""

# ==============================================================================
# 5. FUNCIONES DE CONTROL Y PROCESAMIENTO
# ==============================================================================
def inicializar_entorno():
    DIR_PROCESADAS_MEDS.mkdir(parents=True, exist_ok=True)
    DIR_JSON.mkdir(parents=True, exist_ok=True)

def obtener_ultimo_consecutivo() -> int:
    """Lee el último consecutivo AM-XXXXXX registrado."""
    ultimo = 0
    if ARCHIVO_CONSECUTIVO.exists():
        try:
            with open(ARCHIVO_CONSECUTIVO, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val.isdigit():
                    ultimo = int(val)
        except Exception:
            pass

    patron = re.compile(r"^AM-(\d{6})\.(jpg|json)$", re.IGNORECASE)
    for carpeta in [DIR_PROCESADAS_MEDS, DIR_JSON]:
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

def optimizar_imagen(ruta_origen: Path, ruta_destino: Path):
    """Aplica corrección EXIF, escala de grises, autocontraste y redimensionado a 1100px."""
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

def extraer_con_ia(ruta_imagen: Path) -> tuple[dict, dict, float]:
    """Extracción directa con la IA en una sola pasada (Zero-Thinking)."""
    img = Image.open(ruta_imagen)
    t0 = time.time()
    resp = client.models.generate_content(
        model=MODELO_UNICO,
        contents=[img, PROMPT_MEDICAMENTOS],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ActaMedicamentosSchema,
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0)
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

# ==============================================================================
# 6. BUCLE PRINCIPAL DE EJECUCIÓN
# ==============================================================================
def ejecutar():
    inicializar_entorno()

    print("\n" + "=" * 75)
    print("   SISTEMA DE DIGITALIZACIÓN: SALIDA DE MEDICAMENTOS E INSUMOS (AM)")
    print(f"   Origen de escaneos: {DIR_SCAN_MEDS.resolve()}")
    print(f"   Destino Fotos:      {DIR_PROCESADAS_MEDS.resolve()}")
    print(f"   Destino JSONs:      {DIR_JSON.resolve()}")
    print("=" * 75 + "\n")

    if not DIR_SCAN_MEDS.exists():
        print(f"[!] Error: No se encontró la ruta {DIR_SCAN_MEDS.resolve()}")
        return

    # Buscar subcarpetas de días (12 al 19)
    subcarpetas_dias = []
    for p in DIR_SCAN_MEDS.iterdir():
        if p.is_dir() and p.name.isdigit():
            subcarpetas_dias.append(p)
    subcarpetas_dias.sort(key=lambda p: int(p.name))

    if not subcarpetas_dias:
        print("[!] No se encontraron carpetas numéricas de día (12-19) en scan/medicamentos/.")
        return

    consecutivo_actual = obtener_ultimo_consecutivo()
    print(f"• Último consecutivo registrado: AM-{consecutivo_actual:06d}")
    print(f"• Carpetas de días detectadas:  {[d.name for d in subcarpetas_dias]}\n")

    total_procesadas_tanda = 0
    total_farmacos_extraidos = 0
    extensiones = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".bmp", ".tif", ".tiff"}

    for carpeta_dia in subcarpetas_dias:
        dia_num = int(carpeta_dia.name)
        fecha_lote = f"2026-08-{dia_num:02d}"

        fotos = [f for f in carpeta_dia.iterdir() if f.is_file() and f.suffix in extensiones]
        fotos.sort(key=lambda f: (f.stat().st_mtime, f.name))

        if not fotos:
            continue

        print(f"📁 --- PROCESANDO MEDICAMENTOS DÍA {dia_num} ({fecha_lote}) | {len(fotos)} Actas ---")

        for foto_cruda in fotos:
            consecutivo_actual += 1
            nombre_estandar = f"AM-{consecutivo_actual:06d}"
            ruta_foto_procesada = DIR_PROCESADAS_MEDS / f"{nombre_estandar}.jpg"
            ruta_json_final = DIR_JSON / f"{nombre_estandar}.json"

            # 1. Modo de reanudación
            if ruta_json_final.exists() and ruta_foto_procesada.exists():
                print(f"   [{nombre_estandar}] Ya procesado previamente. Saltando...")
                continue

            print(f"\n▶ [{nombre_estandar}] Procesando: {foto_cruda.name} (Día {dia_num})...")

            try:
                # 2. Optimizar imagen
                optimizar_imagen(foto_cruda, ruta_foto_procesada)

                # 3. Extracción directa con IA
                datos, tokens, duracion = extraer_con_ia(ruta_foto_procesada)

                meds_lista = datos.get("medicamentos", [])
                cant_meds = len(meds_lista)
                total_farmacos_extraidos += cant_meds
                codigo_enlace = datos.get("codigo_acta_vinculante", "SIN_NUMERO")

                # 4. Construir y guardar paquete JSON
                paquete_json = {
                    "id_documento": nombre_estandar,
                    "archivo_imagen": f"{nombre_estandar}.jpg",
                    "archivo_origen_escaneo": foto_cruda.name,
                    "fecha_lote": fecha_lote,
                    "dia_agosto": dia_num,
                    "tipo_documento": "VETERINARIO",
                    "codigo_acta_vinculante": codigo_enlace,
                    "fecha_documento_detectada": datos.get("fecha_documento_detectada", ""),
                    "municipio_o_lugar": datos.get("municipio_o_lugar", ""),
                    "autoriza_nombre": datos.get("autoriza_nombre", ""),
                    "recibe_nombre": datos.get("recibe_nombre", ""),
                    "datos_medicamentos": meds_lista,
                    "metadatos_auditoria": {
                        "fecha_procesamiento": datetime.now().isoformat(),
                        "duracion_segundos": duracion,
                        "tokens_total": tokens["total"]
                    }
                }

                with open(ruta_json_final, "w", encoding="utf-8") as f:
                    json.dump(paquete_json, f, ensure_ascii=False, indent=2)

                # 5. Actualizar consecutivo en disco
                guardar_consecutivo(consecutivo_actual)
                total_procesadas_tanda += 1

                print(f"   └─ 💾 Guardado {nombre_estandar}.json | Enlace: {codigo_enlace} | {cant_meds} Fármacos/Insumos ({duracion}s) [OK]")

            except Exception as e:
                print(f"   [!] ERROR CRÍTICO en {foto_cruda.name}: {e}")
                consecutivo_actual -= 1  # Revertir si falló

            time.sleep(PAUSA_ENTRE_LLAMADAS)

    print("\n" + "=" * 75)
    print("                 PROCESO DE MEDICAMENTOS FINALIZADO")
    print("=" * 75)
    print(f"• Total planillas procesadas:           {total_procesadas_tanda}")
    print(f"• Total fármacos e insumos extraídos:  {total_farmacos_extraidos}")
    print(f"• Consecutivo final alcanzado:          AM-{consecutivo_actual:06d}")
    print(f"• Imágenes optimizadas en:              {DIR_PROCESADAS_MEDS.resolve()}")
    print(f"• Archivos JSON listos en:              {DIR_JSON.resolve()}")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    ejecutar()