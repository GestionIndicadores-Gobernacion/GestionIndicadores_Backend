from flask import jsonify
from flask_smorest import Blueprint
from flask.views import MethodView
from collections import Counter
import re

from domains.datasets.models.table import Table
from domains.datasets.models.field import Field
from domains.datasets.models.record import Record

blp = Blueprint("dataset_dashboard", __name__, url_prefix="/datasets")

COLORS = ["#18181b","#3f3f46","#71717a","#a1a1aa","#52525b","#27272a","#d4d4d8","#09090b"]


# ─── Normalización ────────────────────────────────────────────────────────────

def _norm(val) -> str:
    if val is None: return ""
    return str(val).strip().lower()

def _is_yes(val) -> bool:
    return _norm(val) in ("si", "sí", "yes", "1", "1.0", "true", "x")

def _is_no(val) -> bool:
    return _norm(val) in ("no", "0", "0.0", "false")

def _fill_rate(values, total) -> float:
    filled = sum(1 for v in values if v is not None and str(v).strip())
    return round((filled / total) * 100, 1) if total else 0.0

def _group_similar(values, top_n=12, normalize_first_word=False):
    """Agrupa valores normalizando mayúsculas/espacios."""
    normalized = {}
    for v in values:
        if v is None: continue
        raw = str(v).strip()
        if not raw: continue
        if normalize_first_word:
            words = raw.lower().split()
            key = words[0] if words else raw.lower()
            display = key.capitalize()
        else:
            key = raw.lower()
            display = raw
        if key not in normalized:
            normalized[key] = [display, 0]
        normalized[key][1] += 1
    entries = sorted(normalized.values(), key=lambda x: -x[1])
    return [(label, count) for label, count in entries[:top_n]]

def _bars(grouped, total):
    return [
        {"label": label, "value": count,
         "pct": round((count / total) * 100, 1),
         "color": COLORS[i % len(COLORS)]}
        for i, (label, count) in enumerate(grouped) if count > 0
    ]

def _numeric_stats(values):
    try:
        nums = sorted(float(v) for v in values if v is not None)
    except Exception:
        return {}
    if not nums: return {}
    n = len(nums)
    mid = n // 2
    median = (nums[mid-1] + nums[mid]) / 2 if n % 2 == 0 else nums[mid]
    s = sum(nums)
    return {"min": round(min(nums),2), "max": round(max(nums),2),
            "avg": round(s/n,2), "median": round(median,2),
            "total": round(s,2), "count": n}

def _numeric_bins(values, buckets=8):
    try:
        nums = [float(v) for v in values if v is not None]
    except Exception:
        return []
    if not nums: return []
    mn, mx = min(nums), max(nums)
    step = (mx - mn) / buckets or 1
    bins = [{"label": f"{mn+i*step:.0f}–{mn+(i+1)*step:.0f}", "value": 0} for i in range(buckets)]
    for v in nums:
        idx = min(int((v - mn) / step), buckets - 1)
        bins[idx]["value"] += 1
    t = len(nums) or 1
    return [{**b, "pct": round(b["value"]/t*100,1), "color": COLORS[i%len(COLORS)]}
            for i, b in enumerate(bins) if b["value"] > 0]

def _unique_clean(values):
    return set(_norm(v) for v in values if v is not None and str(v).strip())


# ─── Clasificación de campos ──────────────────────────────────────────────────

def _classify_fields(fields, field_values, total):
    classified = {
        "location": [], "demographic": [], "service": [],
        "numeric": [], "program": [], "contact": [],
        "yesno": [], "categorical": [], "identifier": []
    }

    LOCATION_KW  = {"municipio","ciudad","departamento","localidad","barrio","zona","region","ubicacion"}
    DEMOGRAPHIC_KW = {"sexo","genero","edad","escolar","educativo","educacion","nivel","estudio"}
    SERVICE_KW   = {"servicio","albergue","fundacion","tipo","actividad","rol"}
    PROGRAM_KW   = {"capacitacion","esterilizacion","alimento","gobernacion","programa","participacion","jornada","entrega"}
    CONTACT_KW   = {"telefono","correo","email","direccion","celular","whatsapp"}
    IDENTIFIER_KW = {"nombre","id","codigo","observacion","nota","comentario","unnamed","cuantos","descripcion","cual"}

    def match(name, kws):
        n = _norm(name)
        return any(k in n for k in kws)

    for f in fields:
        vals = field_values[f.name]
        fill = _fill_rate(vals, total)
        unique = _unique_clean(vals)
        n_unique = len(unique)

        # Contacto siempre va a contacto, sin importar uniqueness
        if match(f.name, CONTACT_KW):
            classified["contact"].append(f); continue

        # Descartar campos vacíos o identificadores
        if fill < 3:
            classified["identifier"].append(f); continue
        if match(f.name, IDENTIFIER_KW):
            classified["identifier"].append(f); continue
        # Campos con demasiados valores únicos son textos libres
        if n_unique > total * 0.5:
            classified["identifier"].append(f); continue
        if match(f.name, LOCATION_KW):
            classified["location"].append(f); continue
        if match(f.name, DEMOGRAPHIC_KW):
            classified["demographic"].append(f); continue
        if match(f.name, SERVICE_KW):
            classified["service"].append(f); continue
        if match(f.name, PROGRAM_KW):
            classified["program"].append(f); continue
        if f.type == "number":
            classified["numeric"].append(f); continue

        # Detectar sí/no aunque no sea tipo boolean
        yes_no = sum(1 for v in vals if _is_yes(v) or _is_no(v))
        if yes_no > total * 0.25 and n_unique <= 8:
            classified["yesno"].append(f); continue

        # Categórico útil: entre 2 y 30 valores únicos
        if 2 <= n_unique <= 30:
            classified["categorical"].append(f); continue

        classified["identifier"].append(f)

    return classified


# ─── Generadores de secciones ─────────────────────────────────────────────────

def _bar_section(field, values, total, subtitle=""):
    grouped = _group_similar(values, top_n=12)
    b = _bars(grouped, total)
    if not b: return None
    n_unique = len(_unique_clean(values))
    return {
        "id": field.name,
        "title": field.label.strip(),
        "subtitle": subtitle or f"{n_unique} valores únicos",
        "type": "bar",
        "bars": b,
    }


def _section_programs(fields, field_values, total):
    """Una sola sección agrupando todos los programas con label limpio."""
    program_bars = []
    seen_labels = set()

    for f in fields:
        vals = field_values[f.name]
        participants = sum(
            1 for v in vals
            if v is not None and str(v).strip() and _norm(v) not in ("no", "0", "0.0", "")
        )
        if participants == 0:
            continue

        # Construir label único: si el label ya existe, agregar año del nombre del campo
        label = f.label.strip()
        # Intentar extraer año del nombre de campo (ej: "2025", "2026")
        year_match = re.search(r'(20\d{2})', f.name)
        if year_match and label in seen_labels:
            label = f"{label} ({year_match.group(1)})"
        elif label in seen_labels:
            label = f"{label} (2)"
        seen_labels.add(label)

        program_bars.append({
            "label": label[:40],
            "value": participants,
            "pct": round((participants / total) * 100, 1),
            "color": COLORS[len(program_bars) % len(COLORS)]
        })

    if not program_bars:
        return []

    program_bars.sort(key=lambda x: -x["value"])
    return [{
        "id": "__programs__",
        "title": "Participación en programas institucionales",
        "subtitle": f"{len(program_bars)} programas registrados",
        "type": "bar",
        "bars": program_bars,
    }]


def _section_contact(fields, field_values, total):
    """Completitud de campos de contacto — incluye también teléfono y dirección."""
    # Siempre buscar campos de contacto por nombre aunque hayan caído en otro bucket
    CONTACT_NAMES = {"telefono", "correo", "email", "direccion", "celular"}

    bars = []
    for f in fields:
        rate = _fill_rate(field_values[f.name], total)
        bars.append({
            "label": f.label.strip(),
            "value": round(rate),
            "pct": rate,
            "color": COLORS[0] if rate >= 80 else COLORS[2] if rate >= 50 else COLORS[3]
        })

    if not bars:
        return []

    bars.sort(key=lambda x: -x["pct"])
    return [{
        "id": "__contact__",
        "title": "Capacidad de contacto de la red",
        "subtitle": "% de campos completados",
        "type": "completeness",
        "bars": bars,
    }]


def _section_animals(all_fields, field_values, total):
    """
    Sección especial: animales atendidos.
    Busca campos cuyo nombre contenga 'perro', 'gato', 'animal', 'especie'.
    """
    ANIMAL_KW = {"perro", "gato", "animal", "especie", "felino", "canino"}

    animal_fields = [
        f for f in all_fields
        if any(k in _norm(f.name) for k in ANIMAL_KW)
    ]

    sections = []
    for f in animal_fields:
        vals = field_values[f.name]
        if f.type == "number":
            bins = _numeric_bins(vals)
            stats = _numeric_stats(vals)
            if bins and stats:
                # KPI: cuántos voluntarios tienen este animal
                count_with = sum(1 for v in vals if v is not None and str(v).strip() != "" and str(v) != "0")
                sections.append({
                    "id": f.name,
                    "title": f.label.strip(),
                    "subtitle": f"{count_with} voluntarios atienden este animal · Total: {int(stats['total'])}",
                    "type": "histogram",
                    "bars": bins,
                    "stats": stats,
                })
        else:
            # Categórico (ej: Otro Animal)
            s = _bar_section(f, vals, total, "Animales atendidos")
            if s:
                sections.append(s)

    return sections


# ─── KPIs ─────────────────────────────────────────────────────────────────────

def _build_kpis(classified, all_fields, field_values, total):
    kpis = [{"label": "Total registros", "value": str(total), "icon": "users"}]

    # Municipios únicos
    for f in classified.get("location", []):
        n = len(_unique_clean(field_values[f.name]))
        kpis.append({"label": f"{f.label.strip()} con presencia", "value": str(n), "icon": "map"})

    # Programas → KPI individual con año
    for f in classified.get("program", [])[:4]:
        vals = field_values[f.name]
        p = sum(1 for v in vals if v is not None and str(v).strip() and _norm(v) not in ("no", "0", "0.0", ""))
        year_match = re.search(r'(20\d{2})', f.name)
        label = f.label.strip()[:25]
        if year_match:
            label = f"{label} {year_match.group(1)}"
        kpis.append({
            "label": label,
            "value": str(p),
            "sub": f"{round(p/total*100)}% del total",
            "icon": "check"
        })

    # Animales numéricos → total
    ANIMAL_KW = {"perro", "gato", "animal"}
    for f in all_fields:
        if any(k in _norm(f.name) for k in ANIMAL_KW) and f.type == "number":
            stats = _numeric_stats(field_values[f.name])
            if stats and stats["count"] > 0:
                kpis.append({
                    "label": f"Total {f.label.strip()}",
                    "value": f"{int(stats['total']):,}",
                    "sub": f"{stats['count']} voluntarios con datos",
                    "icon": "number"
                })

    return kpis[:7]


# ─── Análisis principal ───────────────────────────────────────────────────────

def analyze_dataset(fields, records):
    total = len(records)
    if total == 0:
        return {"kpis": [], "sections": [], "total": 0}

    field_values = {f.name: [r.data.get(f.name) for r in records] for f in fields}
    classified = _classify_fields(fields, field_values, total)

    # Encontrar campos de contacto en TODOS los campos (no solo los clasificados como contacto)
    CONTACT_NAMES = {"telefono", "correo", "email", "direccion", "celular"}
    all_contact_fields = [
        f for f in fields
        if any(k in _norm(f.name) for k in CONTACT_NAMES)
    ]

    kpis = _build_kpis(classified, fields, field_values, total)
    sections = []

    # 1. Cobertura territorial
    for f in classified["location"][:2]:
        s = _bar_section(f, field_values[f.name], total, "Cobertura territorial")
        if s: sections.append(s)

    # 2. Perfil demográfico
    for f in classified["demographic"]:
        vals = field_values[f.name]
        n_unique = len(_unique_clean(vals))
        # Si tiene muchos valores únicos, normalizar por primera palabra (ej: nivel escolar)
        normalize_fw = n_unique > 30
        grouped = _group_similar(vals, top_n=12, normalize_first_word=normalize_fw)
        b = _bars(grouped, total)
        if not b: continue
        sections.append({
            "id": f.name,
            "title": f.label.strip(),
            "subtitle": "Perfil demográfico",
            "type": "bar",
            "bars": b,
        })

    # 3. Tipos de servicio
    for f in classified["service"][:2]:
        s = _bar_section(f, field_values[f.name], total, "Tipos de servicio")
        if s: sections.append(s)

    # 4. Animales atendidos
    sections += _section_animals(fields, field_values, total)

    # 5. Sí/No (adopción, gobernación, etc.)
    for f in classified["yesno"][:4]:
        vals = field_values[f.name]
        yes = sum(1 for v in vals if _is_yes(v))
        no  = sum(1 for v in vals if _is_no(v))
        if yes + no < 5: continue
        sections.append({
            "id": f.name,
            "title": f.label.strip(),
            "subtitle": f"{yes} de {total} responden Sí",
            "type": "bar",
            "bars": [
                {"label": "Sí", "value": yes, "pct": round(yes/total*100,1), "color": COLORS[0]},
                {"label": "No", "value": no,  "pct": round(no/total*100,1),  "color": COLORS[2]},
            ]
        })

    # 6. Programas institucionales
    sections += _section_programs(classified["program"], field_values, total)

    # 7. Contactabilidad (buscar en TODOS los campos, no solo los clasificados)
    sections += _section_contact(all_contact_fields, field_values, total)

    # 8. Otros categóricos útiles
    for f in classified["categorical"][:3]:
        s = _bar_section(f, field_values[f.name], total)
        if s: sections.append(s)

    return {"total": total, "kpis": kpis, "sections": sections}


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@blp.route("/tables/<int:table_id>/dashboard")
class TableDashboardResource(MethodView):
    def get(self, table_id):
        table = Table.query.get_or_404(table_id)
        fields = Field.query.filter_by(table_id=table.id).all()
        records = Record.query.filter_by(table_id=table.id).all()
        dashboard = analyze_dataset(fields, records)
        dashboard["table"] = {
            "id": table.id, "name": table.name,
            "description": table.description, "dataset_id": table.dataset_id,
        }
        return jsonify(dashboard)