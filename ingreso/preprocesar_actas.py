import re
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps

# 1. Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent
CARPETA_ACTAS = BASE_DIR / "actas"
CARPETA_SIN_PROCESAR = CARPETA_ACTAS / "sinProcesar"
CARPETA_PROCESADAS = CARPETA_ACTAS / "procesadas"
CARPETA_TERMINADAS = CARPETA_ACTAS / "terminadas"
ARCHIVO_CONSECUTIVO = CARPETA_ACTAS / "consecutivo.txt"

# 2. Parámetros de optimización (Consumo mínimo: ~258 tokens por foto)
MAX_ALTO = 1100
CORTE_BLANCOS = 1.5
FACTOR_CONTRASTE = 1.35
CALIDAD_JPEG = 70

def obtener_ultimo_consecutivo() -> int:
    """
    Lee el último número utilizado desde consecutivo.txt o
    analiza las carpetas procesadas/ y terminadas/ como respaldo.
    """
    ultimo = 0

    # 1. Intentar leer desde el archivo consecutivo.txt
    if ARCHIVO_CONSECUTIVO.exists():
        try:
            with open(ARCHIVO_CONSECUTIVO, "r", encoding="utf-8") as f:
                contenido = f.read().strip()
                if contenido.isdigit():
                    ultimo = int(contenido)
        except Exception:
            pass

    # 2. Escaneo de respaldo en procesadas/ y terminadas/ con el prefijo E-
    patron = re.compile(r"^E-(\d{6})\.jpg$", re.IGNORECASE)
    for carpeta in [CARPETA_PROCESADAS, CARPETA_TERMINADAS]:
        if carpeta.exists():
            for archivo in carpeta.iterdir():
                match = patron.match(archivo.name)
                if match:
                    num = int(match.group(1))
                    if num > ultimo:
                        ultimo = num

    return ultimo

def guardar_consecutivo(numero: int):
    """Guarda el último consecutivo generado en disco."""
    try:
        with open(ARCHIVO_CONSECUTIVO, "w", encoding="utf-8") as f:
            f.write(str(numero))
    except Exception as e:
        print(f"[!] Advertencia: No se pudo actualizar consecutivo.txt: {e}")

def optimizar_acta(ruta_origen: Path, ruta_destino: Path):
    """Aplica corrección EXIF, escala de grises, autocontraste y redimensionamiento."""
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

def ejecutar():
    CARPETA_SIN_PROCESAR.mkdir(parents=True, exist_ok=True)
    CARPETA_PROCESADAS.mkdir(parents=True, exist_ok=True)
    CARPETA_TERMINADAS.mkdir(parents=True, exist_ok=True)

    extensiones = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".bmp", ".tif", ".tiff"}
    
    # Obtener y ordenar por fecha de modificación para preservar el orden del escáner
    fotos = [
        f for f in CARPETA_SIN_PROCESAR.iterdir() 
        if f.is_file() and f.suffix in extensiones
    ]
    fotos.sort(key=lambda f: (f.stat().st_mtime, f.name))

    total = len(fotos)
    ultimo_id = obtener_ultimo_consecutivo()

    print(f"\n=======================================================")
    print(f"  PREPROCESAMIENTO Y ASIGNACIÓN DE CONSECUTIVO (E-)")
    print(f"  Archivos nuevos detectados: {total}")
    print(f"  Último consecutivo registrado: E-{ultimo_id:06d}")
    print(f"  Próximo archivo a generar:     E-{(ultimo_id + 1):06d}.jpg")
    print(f"=======================================================")

    if total == 0:
        print("No hay imágenes pendientes en 'actas/sinProcesar/'.\n")
        return

    contador_actual = ultimo_id

    for i, foto in enumerate(fotos, start=1):
        contador_actual += 1
        nombre_estandar = f"E-{contador_actual:06d}.jpg"
        destino = CARPETA_PROCESADAS / nombre_estandar
        peso_orig_kb = round(foto.stat().st_size / 1024, 1)

        try:
            # 1. Optimizar y guardar con el nuevo nombre consecutivo
            optimizar_acta(foto, destino)
            peso_nuevo_kb = round(destino.stat().st_size / 1024, 1)

            # 2. Verificar y eliminar original
            if destino.exists() and destino.stat().st_size > 0:
                foto.unlink()
                guardar_consecutivo(contador_actual)
                print(f"[{i}/{total}] {foto.name} -> {nombre_estandar} ({peso_nuevo_kb} KB) [OK]")
            else:
                print(f"[{i}/{total}] [ALERTA] Falló la verificación de {nombre_estandar}")
                contador_actual -= 1  # Revertir incremento si falló

        except Exception as e:
            print(f"[{i}/{total}] [ERROR] en {foto.name}: {e}")
            contador_actual -= 1

    print(f"\nProceso finalizado con éxito.")
    print(f"  • Total procesadas en esta tanda: {total}")
    print(f"  • Consecutivo actual en disco:    E-{contador_actual:06d}")
    print(f"  • Archivos listos en:             {CARPETA_PROCESADAS.resolve()}\n")

if __name__ == "__main__":
    ejecutar()