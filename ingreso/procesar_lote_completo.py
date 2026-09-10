import csv
import json
import logging
import shutil
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from PIL import Image
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# 1. Silenciar logs internos
logging.getLogger("google_genai").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning)

# ==============================================================================
# 2. CONFIGURACIÓN DEL LOTE Y PARÁMETROS DE LA API
# ==============================================================================
# Cambia esta fecha según el paquete de escaneo a procesar (AAAA-MM-DD):
FECHA_LOTE_CONFIGURADA = "2026-08-17"

API_KEY = "AQ.Ab8RN6LBz47MPFu4W2AtJ65WBH82IibEyQuDdNubmUriBbf6EA"
client = genai.Client(api_key=API_KEY)

MODELO_UNICO = "gemini-3.1-flash-lite"
MAX_REINTENTOS = 5
PAUSA_BASE_REINTENTO = 4.0
PAUSA_ENTRE_FOTOS = 1.0  # Pausa breve entre fotos exitosas
TASA_CAMBIO_COP = 3100.0  # Tasa COP por USD

# Tarifas oficiales Gemini 3.1 Flash-Lite (por millón de tokens)
TARIFA_INPUT_1M_USD = 0.25
TARIFA_OUTPUT_1M_USD = 1.50

# Rutas del proyecto
BASE_DIR = Path(__file__).resolve().parent
CARPETA_ACTAS = BASE_DIR / "actas"
CARPETA_PROCESADAS = CARPETA_ACTAS / "procesadas"
CARPETA_TERMINADAS = CARPETA_ACTAS / "terminadas"
CARPETA_CON_ERROR = CARPETA_ACTAS / "conError"
CARPETA_DATOS_JSON = CARPETA_ACTAS / "datos_json"

CSV_RECEPCION = BASE_DIR / "recepcion_medicamentos_inventario.csv"

# ==============================================================================
# 3. ESQUEMA SIMPLIFICADO: MEDICAMENTOS, INSUMOS Y CANTIDADES (PYDANTIC)
# ==============================================================================
class ItemMedicamentoRecepcion(BaseModel):
    medicamento_insumo: str = Field(
        description="Nombre del medicamento, antibiótico, analgésico, suero, vacuna o insumo médico"
    )
    cantidad: float = Field(0.0, description="Cantidad numérica exacta")
    unidad: str = Field(
        "", description="Unidad de medida (frascos, tabletas, cajas, ampollas, ml, bolsas, unidades, rollos, etc.)"
    )
    presentacion: Optional[str] = Field(
        "", description="Concentración, presentación, lote o fecha de vencimiento si aparece anotado"
    )

class DocumentoRecepcionMedicamentos(BaseModel):
    numero_acta: str = Field(
        description="Código o consecutivo manuscrito/impreso si aparece (ej. E-001, REC-01). Si no tiene número, colocar estrictamente 'SIN_NUMERO'."
    )
    fecha_documento_detectada: Optional[str] = Field(
        "", description="Fecha visible en el documento si la tiene"
    )
    medicamentos: List[ItemMedicamentoRecepcion] = Field(
        default_factory=list,
        description="Lista completa de medicamentos e insumos médicos con sus cantidades"
    )

# Columnas del consolidado CSV
COLUMNAS_RECEPCION = [
    "numero_acta", "archivo_imagen", "fecha_lote", "fecha_documento",
    "medicamento_insumo", "cantidad", "unidad", "presentacion"
]

# ==============================================================================
# 4. GESTIÓN DE ARCHIVOS Y BASES DE DATOS
# ==============================================================================
def inicializar_entorno():
    CARPETA_PROCESADAS.mkdir(parents=True, exist_ok=True)
    CARPETA_TERMINADAS.mkdir(parents=True, exist_ok=True)
    CARPETA_CON_ERROR.mkdir(parents=True, exist_ok=True)
    CARPETA_DATOS_JSON.mkdir(parents=True, exist_ok=True)

    if not CSV_RECEPCION.exists():
        with open(CSV_RECEPCION, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNAS_RECEPCION)
            writer.writeheader()

def guardar_json_individual(datos: dict, tokens_info: dict, duracion: float, nombre_archivo: str) -> Path:
    """Genera el JSON independiente con los medicamentos y metadatos de auditoría."""
    nombre_json = Path(nombre_archivo).stem + ".json"
    ruta_json = CARPETA_DATOS_JSON / nombre_json

    costo_usd = ((tokens_info["in"] / 1_000_000) * TARIFA_INPUT_1M_USD) + \
                ((tokens_info["out"] / 1_000_000) * TARIFA_OUTPUT_1M_USD)

    paquete_completo = {
        "archivo_imagen": nombre_archivo,
        "fecha_lote": FECHA_LOTE_CONFIGURADA,
        "codigo_acta": datos.get("numero_acta", "SIN_NUMERO"),
        "tipo_documento": "RECEPCION_MEDICAMENTOS",
        "fecha_documento_detectada": datos.get("fecha_documento_detectada", ""),
        "datos_medicamentos": datos.get("medicamentos", []),
        "metadatos_auditoria": {
            "modelo_ia": MODELO_UNICO,
            "fecha_procesamiento": datetime.now().isoformat(),
            "duracion_segundos": duracion,
            "tokens_entrada": tokens_info["in"],
            "tokens_salida": tokens_info["out"],
            "tokens_total": tokens_info["total"],
            "costo_usd_estimado": round(costo_usd, 6)
        }
    }

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(paquete_completo, f, ensure_ascii=False, indent=2)

    return ruta_json

def registrar_en_csv(datos: dict, nombre_archivo: str):
    """Guarda cada ítem como una fila en el CSV de inventario."""
    num_acta = datos.get("numero_acta", "SIN_NUMERO")
    items = datos.get("medicamentos", [])

    if items:
        with open(CSV_RECEPCION, mode="a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNAS_RECEPCION)
            for item in items:
                writer.writerow({
                    "numero_acta": num_acta,
                    "archivo_imagen": nombre_archivo,
                    "fecha_lote": FECHA_LOTE_CONFIGURADA,
                    "fecha_documento": datos.get("fecha_documento_detectada", ""),
                    "medicamento_insumo": item.get("medicamento_insumo", ""),
                    "cantidad": item.get("cantidad", 0),
                    "unidad": item.get("unidad", ""),
                    "presentacion": item.get("presentacion", "")
                })

# ==============================================================================
# 5. LLAMADA A LA IA CON PROMPT ENFOCADO EN FÁRMACOS E INSUMOS
# ==============================================================================
def extraer_con_ia(ruta_imagen: Path) -> tuple[dict, dict, float]:
    img = Image.open(ruta_imagen)
    
    prompt = """
    Actúa como un perito farmacéutico y auditor veterinario.
    Analiza esta planilla/documento y extrae fielmente la lista de medicamentos e insumos médicos veterinarios.

    Instrucciones estrictas:
    1. Si hay un código identificador o consecutivo visible, extráelo en 'numero_acta'. Si no hay, coloca 'SIN_NUMERO'.
    2. Extrae CADA UNO de los ítems de la lista en 'medicamentos':
       - 'medicamento_insumo': Nombre del producto/fármaco/insumo. Prioriza términos farmacológicos veterinarios correctos (ej: Enrofloxacina, Meloxicam, Ketoprofeno, Doxiciclina, Ivermectina, Amoxicilina, Cefalexina, Lactato de Ringer, Solución Salina, Gasas, Jeringas, Catéteres, Guantes, Suturas, etc.).
       - 'cantidad': Número exacto ingresado.
       - 'unidad': Unidad de medida o empaque (frascos, tabletas, cajas, ampollas, ml, bolsas, unidades, etc.).
       - 'presentacion': Concentración, presentación o lote si aparece anotado.
    """

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            inicio = time.time()
            response = client.models.generate_content(
                model=MODELO_UNICO,
                contents=[img, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DocumentoRecepcionMedicamentos,
                    temperature=0.0,
                    thinking_config=types.ThinkingConfig(thinking_budget=0)  # CERO TOKENS DE PENSAMIENTO
                ),
            )
            duracion = round(time.time() - inicio, 2)
            
            meta = response.usage_metadata
            tokens_info = {
                "in": meta.prompt_token_count,
                "out": meta.candidates_token_count,
                "total": meta.total_token_count
            }

            return response.parsed.model_dump(), tokens_info, duracion

        except Exception as e:
            error_str = str(e)
            es_recuperable = any(c in error_str for c in ["503", "UNAVAILABLE", "429", "ResourceExhausted", "DeadlineExceeded"])
            
            if es_recuperable and intento < MAX_REINTENTOS:
                espera = PAUSA_BASE_REINTENTO * intento
                print(f"    [!] Servidor ocupado ({error_str[:45]}...). Reintentando en {espera}s (Intento {intento}/{MAX_REINTENTOS})...")
                time.sleep(espera)
            else:
                raise RuntimeError(f"Fallo tras {intento} intentos: {error_str}")

# ==============================================================================
# 6. BUCLE PRINCIPAL DE PROCESAMIENTO
# ==============================================================================
def ejecutar_digitalizacion():
    inicializar_entorno()

    extensiones = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG"}
    archivos = [f for f in CARPETA_PROCESADAS.iterdir() if f.is_file() and f.suffix in extensiones]
    archivos.sort(key=lambda f: f.name)

    total = len(archivos)
    print(f"\n======================================================================")
    print(f"   DIGITALIZACIÓN: RECEPCIÓN DE MEDICAMENTOS E INSUMOS")
    print(f"   Modelo activo:     {MODELO_UNICO} (thinking_budget = 0)")
    print(f"   Fecha de lote:     {FECHA_LOTE_CONFIGURADA}")
    print(f"   Actas pendientes:  {total}")
    print(f"   Carpeta origen:    {CARPETA_PROCESADAS}")
    print(f"======================================================================\n")

    if total == 0:
        print("No hay imágenes pendientes en 'actas/procesadas/'.")
        return

    historial_tokens = []

    for i, archivo in enumerate(archivos, start=1):
        nombre_json = archivo.stem + ".json"
        ruta_json_existente = CARPETA_DATOS_JSON / nombre_json

        # 1. Modo de reanudación automática (Cero costo)
        if ruta_json_existente.exists():
            print(f"[{i}/{total}] {archivo.name} ya fue procesado ({nombre_json} existe). Moviendo a terminadas...")
            shutil.move(str(archivo), str(CARPETA_TERMINADAS / archivo.name))
            continue

        print(f"[{i}/{total}] LEYENDO: {archivo.name}")
        try:
            # 2. Extracción con IA (sin tokens de pensamiento)
            datos, tokens, duracion = extraer_con_ia(archivo)

            # 3. Guardar archivo JSON individual
            ruta_json = guardar_json_individual(datos, tokens, duracion, archivo.name)

            # 4. Registrar en base de datos CSV de recepción
            registrar_en_csv(datos, archivo.name)

            # 5. Mover a carpeta terminadas
            shutil.move(str(archivo), str(CARPETA_TERMINADAS / archivo.name))

            historial_tokens.append({
                "in": tokens["in"],
                "out": tokens["out"],
                "total": tokens["total"],
                "duracion": duracion
            })

            # Resumen en consola
            num = datos.get("numero_acta")
            meds_count = len(datos.get("medicamentos", []))

            costo_foto_usd = ((tokens["in"] / 1_000_000) * TARIFA_INPUT_1M_USD) + \
                             ((tokens["out"] / 1_000_000) * TARIFA_OUTPUT_1M_USD)

            print(f"  ├─ Código: {num} | Fármacos/Insumos: {meds_count} extraídos")
            print(f"  ├─ JSON generado: {ruta_json.name}")
            print(f"  └─ Tokens: {tokens['in']} In + {tokens['out']} Out = {tokens['total']} Tot (${costo_foto_usd:.5f} USD en {duracion}s) [OK]\n")

        except Exception as e:
            print(f"  [ERROR CRÍTICO] en {archivo.name}: {e}")
            print(f"  -> Moviendo a '{CARPETA_CON_ERROR.name}' para revisión manual.\n")
            shutil.move(str(archivo), str(CARPETA_CON_ERROR / archivo.name))

        if i < total:
            time.sleep(PAUSA_ENTRE_FOTOS)

    # 7. INFORME CONSOLIDADO FINAL
    if historial_tokens:
        tot_in = sum(x["in"] for x in historial_tokens)
        tot_out = sum(x["out"] for x in historial_tokens)
        tot_global = sum(x["total"] for x in historial_tokens)
        n = len(historial_tokens)

        costo_in = (tot_in / 1_000_000) * TARIFA_INPUT_1M_USD
        costo_out = (tot_out / 1_000_000) * TARIFA_OUTPUT_1M_USD
        costo_total_usd = costo_in + costo_out
        costo_total_cop = costo_total_usd * TASA_CAMBIO_COP

        print("=" * 70)
        print("                 REPORTE FINAL DE RECEPCIÓN")
        print("=" * 70)
        print(f"• Planillas procesadas exitosamente:  {n}")
        print(f"• Tokens de entrada acumulados:       {tot_in:,}")
        print(f"• Tokens de salida acumulados:        {tot_out:,}")
        print(f"• Consumo total de tokens:            {tot_global:,}")
        print(f"• Inversión real de este lote:        ${costo_total_usd:.4f} USD (~${costo_total_cop:,.0f} COP)")
        print("-" * 70)
        print(f"• Promedio por planilla:              {round(tot_global/n, 1)} tokens ({round(tot_in/n, 1)} In / {round(tot_out/n, 1)} Out)")
        print("=" * 70 + "\n")

    print("Proceso finalizado.")
    print(f"  • JSONs individuales: {CARPETA_DATOS_JSON.resolve()}")
    print(f"  • Base de datos CSV:  {CSV_RECEPCION.resolve()}")

if __name__ == "__main__":
    ejecutar_digitalizacion()