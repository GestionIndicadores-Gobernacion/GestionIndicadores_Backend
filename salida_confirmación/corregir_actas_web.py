import json
import logging
import re
from pathlib import Path
from flask import Flask, jsonify, render_template_string, request, send_from_directory
from google import genai
from google.genai import types
from PIL import Image

logging.getLogger("google_genai").setLevel(logging.ERROR)

# ==============================================================================
# CONFIGURACIÓN DE RUTAS (Relativas dentro de salida_confirmacion/)
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DIR_PROCESADAS = BASE_DIR / "actas" / "procesadas"
DIR_JSON = BASE_DIR / "json"
ARCHIVO_INFORME = BASE_DIR / "informe_revision_manual.txt"

API_KEY = "AQ.Ab8RN6LBz47MPFu4W2AtJ65WBH82IibEyQuDdNubmUriBbf6EA"
client = genai.Client(api_key=API_KEY)
MODELO_UNICO = "gemini-3.1-flash-lite"

app = Flask(__name__)

MUNICIPIOS_VALLE = [
    "Santiago de Cali", "Jamundí", "Palmira", "Yumbo", "Candelaria", "Pradera", "Florida",
    "Dagua", "La Cumbre", "Vijes", "Tuluá", "Guadalajara de Buga", "Andalucía", "Bugalagrande",
    "San Pedro", "Riofrío", "Trujillo", "El Cerrito", "Ginebra", "Guacarí", "Yotoco", "Restrepo",
    "Calima - El Darién", "Cartago", "Zarzal", "Roldanillo", "Sevilla", "Caicedonia", "La Unión",
    "La Victoria", "Alcalá", "Ansermanuevo", "Argelia", "Bolívar", "El Águila", "El Cairo",
    "El Dovio", "Obando", "Toro", "Ulloa", "Versalles", "Buenaventura", "Otro Departamento", "Norte del Valle"
]

def parsear_informe():
    """Lee las actas reportadas con problemas desde informe_revision_manual.txt."""
    problemas = {}
    if not ARCHIVO_INFORME.exists():
        return problemas

    with open(ARCHIVO_INFORME, "r", encoding="utf-8") as f:
        contenido = f.read()

    bloques = contenido.split("--------------------------------------------------------------------")
    for b in bloques:
        m_id = re.search(r"(AS-\d{6})", b)
        if m_id:
            id_doc = m_id.group(1)
            m_motivo = re.search(r"• Motivo:\s*(.*)", b)
            m_detalle = re.search(r"• Detalle:\s*(.*)", b)
            motivo = m_motivo.group(1).strip() if m_motivo else "Revisión requerida"
            detalle = m_detalle.group(1).strip() if m_detalle else ""
            problemas[id_doc] = {"motivo": motivo, "detalle": detalle}
    return problemas

# ==============================================================================
# ENDPOINTS API
# ==============================================================================
@app.route("/foto/<nombre_archivo>")
def servir_foto(nombre_archivo):
    ruta = DIR_PROCESADAS / nombre_archivo
    if ruta.exists():
        return send_from_directory(DIR_PROCESADAS, nombre_archivo)
    return "Imagen no encontrada", 404

@app.route("/api/lista-casos")
def api_lista():
    problemas = parsear_informe()
    todos_json = sorted([f.stem for f in DIR_JSON.glob("*.json")])
    
    lista = []
    for id_doc in todos_json:
        tiene_alerta = id_doc in problemas
        lista.append({
            "id": id_doc,
            "alerta": tiene_alerta,
            "motivo": problemas.get(id_doc, {}).get("motivo", ""),
            "detalle": problemas.get(id_doc, {}).get("detalle", "")
        })
    # Ordenar: primero los que tienen alerta
    lista.sort(key=lambda x: (not x["alerta"], x["id"]))
    return jsonify({"casos": lista, "municipios": MUNICIPIOS_VALLE})

@app.route("/api/acta/<id_doc>")
def api_get_acta(id_doc):
    f_json = DIR_JSON / f"{id_doc}.json"
    if not f_json.exists():
        return jsonify({"error": "No existe el JSON"}), 404

    with open(f_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    problemas = parsear_informe()
    alerta_info = problemas.get(id_doc, None)

    return jsonify({
        "data": data,
        "alerta": alerta_info,
        "foto_url": f"/foto/{id_doc}.jpg"
    })

@app.route("/api/guardar/<id_doc>", methods=["POST"])
def api_guardar(id_doc):
    f_json = DIR_JSON / f"{id_doc}.json"
    payload = request.get_json()

    with open(f_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return jsonify({"status": "ok", "mensaje": f"{id_doc}.json guardado correctamente"})

@app.route("/api/reprocesar_ia/<id_doc>", methods=["POST"])
def api_reprocesar(id_doc):
    ruta_img = DIR_PROCESADAS / f"{id_doc}.jpg"
    if not ruta_img.exists():
        return jsonify({"error": "No existe la imagen procesada"}), 404

    try:
        img = Image.open(ruta_img)
        prompt = """
        Actúa como auditor y extrae los datos de esta acta oficial de salida de auxilio animal.
        Extrae: codigo_acta_vinculante (formato A-001 o SIN_NUMERO), municipio cabecera, barrio_corregimiento_refugio,
        autoriza_nombre, autoriza_cedula, recibe_nombre, recibe_cedula,
        alimento_perro_kg, alimento_gato_kg, comida_humeda_perro_und, comida_humeda_gato_und,
        arena_kg, areneros_und, camas_und, cobijas_und, recipientes_und, huacales_und, collares_und, insumos_medicos_und.
        """
        resp = client.models.generate_content(
            model=MODELO_UNICO,
            contents=[img, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=2048)
            )
        )
        data = json.loads(resp.text)
        
        # Cargar JSON actual y actualizar valores
        f_json = DIR_JSON / f"{id_doc}.json"
        if f_json.exists():
            with open(f_json, "r", encoding="utf-8") as f:
                actual = json.load(f)
        else:
            actual = {"id_documento": id_doc, "archivo_imagen": f"{id_doc}.jpg"}

        actual.update(data)
        if "datos_alimentos" not in actual:
            actual["datos_alimentos"] = {}
        actual["datos_alimentos"]["alimento_perro_kg"] = data.get("alimento_perro_kg", 0.0)
        actual["datos_alimentos"]["alimento_gato_kg"] = data.get("alimento_gato_kg", 0.0)
        actual["datos_alimentos"]["total_alimento_seco_kg"] = round(float(data.get("alimento_perro_kg", 0.0)) + float(data.get("alimento_gato_kg", 0.0)), 2)

        with open(f_json, "w", encoding="utf-8") as f:
            json.dump(actual, f, ensure_ascii=False, indent=2)

        return jsonify({"status": "ok", "data": actual})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# PLANTILLA HTML INTERACTIVA
# ==============================================================================
HTML_UI = """
<!DOCTYPE html>
<html lang="es" class="h-full bg-slate-950 text-slate-100">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Auditor y Corrector Visual de Actas</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    .custom-scrollbar::-webkit-scrollbar { width: 6px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: #0f172a; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
  </style>
</head>
<body class="h-full flex flex-col font-sans overflow-hidden">

  <!-- Encabezado -->
  <header class="h-14 bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between shrink-0">
    <div class="flex items-center space-x-3">
      <div class="p-1.5 bg-amber-500/10 text-amber-400 rounded-lg border border-amber-500/20">
        <i data-lucide="check-square" class="w-5 h-5"></i>
      </div>
      <div>
        <h1 class="text-sm font-bold text-white">Revisor Manual de Actas con Observaciones</h1>
        <p class="text-[11px] text-slate-400">Verifica la foto original y ajusta el JSON en tiempo real</p>
      </div>
    </div>
    <div class="flex items-center space-x-2">
      <button onclick="cargarActaAnterior()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold rounded-lg flex items-center gap-1">
        <i data-lucide="chevron-left" class="w-4 h-4"></i> Anterior
      </button>
      <span id="posicion-actual" class="text-xs font-mono font-bold text-slate-300 px-2">0 / 0</span>
      <button onclick="cargarActaSiguiente()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold rounded-lg flex items-center gap-1">
        Siguiente <i data-lucide="chevron-right" class="w-4 h-4"></i>
      </button>
      <button onclick="guardarCambios()" class="ml-3 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg flex items-center gap-1.5 shadow-lg shadow-emerald-950">
        <i data-lucide="save" class="w-4 h-4"></i> Guardar y Siguiente
      </button>
    </div>
  </header>

  <!-- Cuerpo Principal Dividido -->
  <div class="flex-1 flex overflow-hidden">
    
    <!-- Barra Lateral: Lista de Actas con Alertas -->
    <aside class="w-64 bg-slate-900/60 border-r border-slate-800 flex flex-col shrink-0">
      <div class="p-3 border-b border-slate-800">
        <input type="text" id="filtro-actas" oninput="filtrarLista()" placeholder="Filtrar por AS-XXXXXX..." class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200">
      </div>
      <div id="lista-casos-ui" class="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
        <!-- Llenado por JS -->
      </div>
    </aside>

    <!-- Visor de Foto (Izquierda) -->
    <section class="flex-1 bg-slate-950 flex flex-col border-r border-slate-800 relative overflow-hidden">
      <div class="h-9 bg-slate-900/80 px-3 flex items-center justify-between border-b border-slate-800 text-xs">
        <span id="foto-titulo" class="font-mono text-slate-300">AS-000001.jpg</span>
        <div class="space-x-2">
          <button onclick="zoomIn()" class="p-1 hover:bg-slate-800 rounded text-slate-300"><i data-lucide="zoom-in" class="w-4 h-4"></i></button>
          <button onclick="zoomOut()" class="p-1 hover:bg-slate-800 rounded text-slate-300"><i data-lucide="zoom-out" class="w-4 h-4"></i></button>
          <button onclick="zoomReset()" class="p-1 hover:bg-slate-800 rounded text-slate-300"><i data-lucide="rotate-ccw" class="w-4 h-4"></i></button>
        </div>
      </div>
      <div class="flex-1 overflow-auto flex items-center justify-center p-4 bg-slate-950" id="contenedor-foto">
        <img id="img-acta" src="" alt="Acta" class="max-h-full max-w-full object-contain transition-transform duration-150">
      </div>
    </section>

    <!-- Formulario de Edición (Derecha) -->
    <section class="w-[480px] bg-slate-900 flex flex-col shrink-0">
      <div class="h-9 bg-slate-900 px-4 flex items-center justify-between border-b border-slate-800 text-xs">
        <span class="font-bold text-slate-200">Datos Extraídos del JSON</span>
        <button onclick="reprocesarConIA()" class="text-amber-400 hover:text-amber-300 flex items-center gap-1 text-[11px] font-semibold">
          <i data-lucide="sparkles" class="w-3.5 h-3.5"></i> Re-intentar con IA
        </button>
      </div>

      <div class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4 text-xs">
        
        <!-- Caja de Alerta del Informe -->
        <div id="caja-alerta" class="hidden p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl space-y-1">
          <div class="flex items-center gap-1.5 text-amber-400 font-bold">
            <i data-lucide="alert-triangle" class="w-4 h-4"></i>
            <span id="alerta-motivo">Motivo de alerta</span>
          </div>
          <p id="alerta-detalle" class="text-[11px] text-slate-300 pl-5">Detalle detectado</p>
        </div>

        <!-- Campos de Identificación y Enlace -->
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Código Enlace (A-XXX)</label>
            <input type="text" id="f-codigo" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-100 font-mono font-bold">
          </div>
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Fecha Lote</label>
            <input type="text" id="f-fecha" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-300">
          </div>
        </div>

        <!-- Ubicación Geográfica -->
        <div class="space-y-2 bg-slate-950 p-3 rounded-xl border border-slate-800">
          <div>
            <label class="block font-semibold text-emerald-400 mb-1">Municipio Cabecera</label>
            <input list="lista-municipios" id="f-municipio" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-100 font-bold">
            <datalist id="lista-municipios"></datalist>
          </div>
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Corregimiento / Vereda / Albergue</label>
            <input type="text" id="f-lugar" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200">
          </div>
        </div>

        <!-- Kilos de Alimento Seco -->
        <div class="space-y-2 bg-slate-950 p-3 rounded-xl border border-slate-800">
          <p class="font-bold text-amber-400 mb-1">Alimento Seco (Concentrado)</p>
          <div class="grid grid-cols-3 gap-2">
            <div>
              <label class="block text-[11px] text-slate-400">Perro (Kg)</label>
              <input type="number" step="0.1" id="f-perro-kg" oninput="recalcularTotalSeco()" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-slate-100 font-bold">
            </div>
            <div>
              <label class="block text-[11px] text-slate-400">Gato (Kg)</label>
              <input type="number" step="0.1" id="f-gato-kg" oninput="recalcularTotalSeco()" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-slate-100 font-bold">
            </div>
            <div>
              <label class="block text-[11px] text-amber-400 font-semibold">Total (Kg)</label>
              <input type="number" step="0.1" id="f-total-kg" readonly class="w-full bg-amber-950/40 border border-amber-700/50 rounded-lg px-2 py-1.5 text-amber-300 font-bold">
            </div>
          </div>
        </div>

        <!-- Comida Húmeda e Insumos -->
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="block text-slate-400 mb-1">Húmeda Perro (Unds)</label>
            <input type="number" id="f-hum-perro" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200">
          </div>
          <div>
            <label class="block text-slate-400 mb-1">Húmeda Gato (Unds)</label>
            <input type="number" id="f-hum-gato" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200">
          </div>
          <div>
            <label class="block text-slate-400 mb-1">Arena Sanitaria (Kg)</label>
            <input type="number" step="0.1" id="f-arena" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200">
          </div>
          <div>
            <label class="block text-slate-400 mb-1">Huacales / Jaulas</label>
            <input type="number" id="f-huacales" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200">
          </div>
          <div>
            <label class="block text-slate-400 mb-1">Areneros</label>
            <input type="number" id="f-areneros" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200">
          </div>
          <div>
            <label class="block text-slate-400 mb-1">Comederos / Platos</label>
            <input type="number" id="f-recipientes" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200">
          </div>
        </div>

        <!-- Personas / Firmas -->
        <div class="grid grid-cols-2 gap-2 bg-slate-950 p-3 rounded-xl border border-slate-800">
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Recibe (Nombre)</label>
            <input type="text" id="f-recibe-nom" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-slate-200">
          </div>
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Recibe (Cédula)</label>
            <input type="text" id="f-recibe-ced" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-slate-200">
          </div>
        </div>

        <!-- Desglose Multi-Municipio (Para Norte del Valle) -->
        <div class="bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-2">
          <div class="flex items-center justify-between">
            <span class="font-bold text-sky-400">Desglose Multi-Municipio (Opcional)</span>
            <button onclick="agregarFilaDesglose()" class="text-sky-400 hover:text-sky-300 font-bold text-xs">+ Agregar</button>
          </div>
          <div id="contenedor-desglose" class="space-y-1.5">
            <!-- Filas dinámicas -->
          </div>
        </div>

      </div>
    </section>

  </div>

  <script>
    let casosGlobales = [];
    let indiceActual = 0;
    let zoomNivel = 1.0;
    let jsonActual = {};

    document.addEventListener("DOMContentLoaded", async () => {
      lucide.createIcons();
      await cargarListaCasos();
    });

    async function cargarListaCasos() {
      const res = await fetch("/api/lista-casos");
      const d = await res.json();
      casosGlobales = d.casos;

      // Llenar datalist de municipios
      const dl = document.getElementById("lista-municipios");
      dl.innerHTML = d.municipios.map(m => `<option value="${m}">`).join("");

      renderizarListaUI();
      if (casosGlobales.length > 0) {
        cargarActaPorIndice(0);
      }
    }

    function renderizarListaUI() {
      const cont = document.getElementById("lista-casos-ui");
      cont.innerHTML = "";
      casosGlobales.forEach((c, idx) => {
        const btn = document.createElement("button");
        btn.id = `item-caso-${idx}`;
        btn.className = `w-full text-left p-2 rounded-lg text-xs font-mono flex items-center justify-between transition ${idx === indiceActual ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold' : 'hover:bg-slate-800 text-slate-300'}`;
        btn.innerHTML = `
          <span>${c.id}</span>
          ${c.alerta ? '<span class="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-400 font-bold">ALERTA</span>' : '<span class="text-slate-500 text-[10px]">OK</span>'}
        `;
        btn.onclick = () => cargarActaPorIndice(idx);
        cont.appendChild(btn);
      });
    }

    async function cargarActaPorIndice(idx) {
      if (idx < 0 || idx >= casosGlobales.length) return;
      indiceActual = idx;
      document.getElementById("posicion-actual").innerText = `${idx + 1} / ${casosGlobales.length}`;

      // Resaltar en lista lateral
      casosGlobales.forEach((_, i) => {
        const el = document.getElementById(`item-caso-${i}`);
        if (el) {
          if (i === idx) {
            el.className = "w-full text-left p-2 rounded-lg text-xs font-mono flex items-center justify-between bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold";
          } else {
            el.className = "w-full text-left p-2 rounded-lg text-xs font-mono flex items-center justify-between hover:bg-slate-800 text-slate-300";
          }
        }
      });

      const caso = casosGlobales[idx];
      const res = await fetch(`/api/acta/${caso.id}`);
      const payload = await res.json();
      jsonActual = payload.data;

      // Cargar Imagen
      document.getElementById("img-acta").src = payload.foto_url;
      document.getElementById("foto-titulo").innerText = `${caso.id}.jpg`;
      zoomReset();

      // Cargar Alerta
      const cAlerta = document.getElementById("caja-alerta");
      if (payload.alerta) {
        cAlerta.classList.remove("hidden");
        document.getElementById("alerta-motivo").innerText = payload.alerta.motivo;
        document.getElementById("alerta-detalle").innerText = payload.alerta.detalle || "Revisar caligrafía y municipio";
      } else {
        cAlerta.classList.add("hidden");
      }

      // Llenar Formulario
      document.getElementById("f-codigo").value = jsonActual.codigo_acta_vinculante || "SIN_NUMERO";
      document.getElementById("f-fecha").value = jsonActual.fecha_lote || "";
      document.getElementById("f-municipio").value = jsonActual.municipio || "";
      document.getElementById("f-lugar").value = jsonActual.barrio_corregimiento_refugio || "";

      const ali = jsonActual.datos_alimentos || {};
      document.getElementById("f-perro-kg").value = ali.alimento_perro_kg || 0;
      document.getElementById("f-gato-kg").value = ali.alimento_gato_kg || 0;
      document.getElementById("f-total-kg").value = ali.total_alimento_seco_kg || 0;
      document.getElementById("f-hum-perro").value = ali.comida_humeda_perro_und || 0;
      document.getElementById("f-hum-gato").value = ali.comida_humeda_gato_und || 0;
      document.getElementById("f-arena").value = ali.arena_kg || 0;
      document.getElementById("f-huacales").value = ali.huacales_und || 0;
      document.getElementById("f-areneros").value = ali.areneros_und || 0;
      document.getElementById("f-recipientes").value = ali.recipientes_und || 0;

      const rec = jsonActual.recibe || {};
      document.getElementById("f-recibe-nom").value = rec.nombre || "";
      document.getElementById("f-recibe-ced").value = rec.cedula || "";

      // Desglose multi-municipio
      const contDes = document.getElementById("contenedor-desglose");
      contDes.innerHTML = "";
      const desglose = jsonActual.desglose_municipios || [];
      desglose.forEach(d => agregarFilaDesglose(d.municipio, d.alimento_perro_kg, d.alimento_gato_kg));
    }

    function recalcularTotalSeco() {
      const p = parseFloat(document.getElementById("f-perro-kg").value || 0);
      const g = parseFloat(document.getElementById("f-gato-kg").value || 0);
      document.getElementById("f-total-kg").value = (p + g).toFixed(1);
    }

    function agregarFilaDesglose(mun="", p=0, g=0) {
      const cont = document.getElementById("contenedor-desglose");
      const div = document.createElement("div");
      div.className = "flex gap-1.5 items-center fila-desglose";
      div.innerHTML = `
        <input type="text" placeholder="Municipio" value="${mun}" class="flex-1 bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-100">
        <input type="number" step="0.1" placeholder="P (Kg)" value="${p}" class="w-16 bg-slate-900 border border-slate-800 rounded px-1.5 py-1 text-slate-100">
        <input type="number" step="0.1" placeholder="G (Kg)" value="${g}" class="w-16 bg-slate-900 border border-slate-800 rounded px-1.5 py-1 text-slate-100">
        <button onclick="this.parentElement.remove()" class="text-rose-400 hover:text-rose-300 p-1"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
      `;
      cont.appendChild(div);
      lucide.createIcons();
    }

    async function guardarCambios() {
      const caso = casosGlobales[indiceActual];
      
      jsonActual.codigo_acta_vinculante = document.getElementById("f-codigo").value.trim();
      jsonActual.municipio = document.getElementById("f-municipio").value.trim();
      jsonActual.barrio_corregimiento_refugio = document.getElementById("f-lugar").value.trim();

      const p_kg = parseFloat(document.getElementById("f-perro-kg").value || 0);
      const g_kg = parseFloat(document.getElementById("f-gato-kg").value || 0);

      jsonActual.datos_alimentos = jsonActual.datos_alimentos || {};
      jsonActual.datos_alimentos.alimento_perro_kg = p_kg;
      jsonActual.datos_alimentos.alimento_gato_kg = g_kg;
      jsonActual.datos_alimentos.total_alimento_seco_kg = parseFloat((p_kg + g_kg).toFixed(1));
      jsonActual.datos_alimentos.comida_humeda_perro_und = parseInt(document.getElementById("f-hum-perro").value || 0);
      jsonActual.datos_alimentos.comida_humeda_gato_und = parseInt(document.getElementById("f-hum-gato").value || 0);
      jsonActual.datos_alimentos.comida_humeda_total_und = jsonActual.datos_alimentos.comida_humeda_perro_und + jsonActual.datos_alimentos.comida_humeda_gato_und;
      jsonActual.datos_alimentos.arena_kg = parseFloat(document.getElementById("f-arena").value || 0);
      jsonActual.datos_alimentos.huacales_und = parseInt(document.getElementById("f-huacales").value || 0);
      jsonActual.datos_alimentos.areneros_und = parseInt(document.getElementById("f-areneros").value || 0);
      jsonActual.datos_alimentos.recipientes_und = parseInt(document.getElementById("f-recipientes").value || 0);

      jsonActual.recibe = jsonActual.recibe || {};
      jsonActual.recibe.nombre = document.getElementById("f-recibe-nom").value.trim();
      jsonActual.recibe.cedula = document.getElementById("f-recibe-ced").value.trim();

      // Recoger desglose si existe
      const filasDes = document.querySelectorAll(".fila-desglose");
      const listaDes = [];
      filasDes.forEach(f => {
        const inps = f.querySelectorAll("input");
        const m = inps[0].value.trim();
        const p = parseFloat(inps[1].value || 0);
        const g = parseFloat(inps[2].value || 0);
        if (m) listaDes.push({ municipio: m, alimento_perro_kg: p, alimento_gato_kg: g });
      });
      jsonActual.desglose_municipios = listaDes;

      await fetch(`/api/guardar/${caso.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(jsonActual)
      });

      // Pasar automáticamente al siguiente
      cargarActaSiguiente();
    }

    async function reprocesarConIA() {
      const caso = casosGlobales[indiceActual];
      document.getElementById("alerta-motivo").innerText = "Procesando con Pensamiento IA...";
      const res = await fetch(`/api/reprocesar_ia/${caso.id}`, { method: "POST" });
      const data = await res.json();
      if (data.status === "ok") {
        await cargarActaPorIndice(indiceActual);
      } else {
        alert("Error re-procesando: " + (data.error || "Fallo en API"));
      }
    }

    function cargarActaSiguiente() {
      if (indiceActual < casosGlobales.length - 1) {
        cargarActaPorIndice(indiceActual + 1);
      }
    }

    function cargarActaAnterior() {
      if (indiceActual > 0) {
        cargarActaPorIndice(indiceActual - 1);
      }
    }

    function zoomIn() { zoomNivel += 0.25; aplicarZoom(); }
    function zoomOut() { if (zoomNivel > 0.5) zoomNivel -= 0.25; aplicarZoom(); }
    function zoomReset() { zoomNivel = 1.0; aplicarZoom(); }
    function aplicarZoom() { document.getElementById("img-acta").style.transform = `scale(${zoomNivel})`; }
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_UI)

if __name__ == "__main__":
    print("\n=======================================================")
    print("  🔍 AUDITOR Y REVISOR VISUAL DE ACTAS")
    print("  Iniciado en: http://127.0.0.1:5001")
    print("=======================================================\n")
    app.run(debug=True, host="0.0.0.0", port=5001)