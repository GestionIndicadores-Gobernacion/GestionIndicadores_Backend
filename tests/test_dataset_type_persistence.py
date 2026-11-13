"""
Identificación estable del dashboard de cada dataset (``datasets.dataset_type``).

Cubre: actualizar con el mismo archivo / con otro nombre / con filas nuevas /
con columnas adicionales / con columnas obligatorias faltantes, dataset nuevo,
datasets heredados sin tipo guardado, que los tipos existentes se sigan
detectando igual, y los dos casos reportados (Z080 formato SAP y PERSONAS
PROMOTORES PYBA).
"""
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pytest

from app.core.extensions import db
from app.modules.datasets.dashboard.analyzer import analyze_dataset, detect_dataset_type
from app.modules.datasets.dashboard.dataset_types import (
    detect_type_from_names, is_compatible, missing_requirements,
)
from app.modules.datasets.models.dataset import Dataset
from app.modules.datasets.models.field import Field
from app.modules.datasets.models.record import Record
from app.modules.datasets.models.table import Table
from app.modules.datasets.services.excel_import_handler import (
    import_excel_dataset, update_excel_dataset,
)
from app.utils.normalizers import normalize_name


# ── helpers ──────────────────────────────────────────────────────────────────

def xlsx(rows, sheet="Sheet1"):
    buf = BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False, sheet_name=sheet)
    buf.seek(0)
    return buf


def xlsx_sheets(sheets: dict):
    buf = BytesIO()
    with pd.ExcelWriter(buf) as writer:
        for name, rows in sheets.items():
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name=name)
    buf.seek(0)
    return buf


def detect(columns):
    return detect_type_from_names(normalize_name(c) for c in columns)


# Z080 "resumido" (formato 2026, como el corte de marzo)
def z080_resumido(n=3, project="Implementación Política Pública Un Valle Animalista"):
    return [{
        "C.Gestor": 1159, "Fondo": 121000, "Proyecto": "P-1",
        "Descripcion Proyecto": project, "Descripcion PEP": f"Actividad {i}",
        "Pres. Inicial": 100, "Apropiacion Definitiva": 1000 + i,
        "Total Ejecutado": 500, "Total Pagos": 300, "Total Obligaciones": 400,
        "Presup. Disponible": 500, "% Ejecutado": 30,
    } for i in range(n)]


# Z080 completo exportado de SAP (como el corte de junio)
def z080_sap(n=3, project="Implementación Política Pública Un Valle Animalista"):
    return [{
        "C.Gestor": 1159, "Nombre C.Gestor": "SRIA DE AMBIENTE", "Fondo": 121000,
        "Desc. Grupo": "Inversión", "Proyecto": "P-1", "Desc. Proyecto": project,
        "Desc. PEP": f"Actividad {i}", "Pres. Inicial": 100,
        "Presup. Definitivo": 1000 + i, "CDP Ejecutado": 600, "Total Ejecutado": 500,
        "Total Pagos": 300, "Total Oblig.": 400, "Presup. Dispon.": 500,
        "% Ejecutado": 30,
    } for i in range(n)]


def promotores(n=3):
    return [{"#": i + 1, "NOMBRE COMPLETO DEL PROMOTOR": f"Promotor {i}"} for i in range(n)]


def denuncias(n=3):
    return [{
        "Número de caso": i, "Fecha": "2026-01-01", "Nombre del denunciante": f"D{i}",
        "Motivo de la denuncia": "maltrato", "Municipio": "Cali",
    } for i in range(n)]


@pytest.fixture()
def created(app):
    ids = []
    yield ids
    db.session.rollback()
    # SQLite no aplica ON DELETE CASCADE (los modelos usan passive_deletes),
    # así que se borran hijos explícitamente para no contaminar otros tests.
    for dataset_id in ids:
        for t in Table.query.filter_by(dataset_id=dataset_id).all():
            Record.query.filter_by(table_id=t.id).delete()
            Field.query.filter_by(table_id=t.id).delete()
        Table.query.filter_by(dataset_id=dataset_id).delete()
        Dataset.query.filter_by(id=dataset_id).delete()
    db.session.commit()


def do_import(created, rows, name):
    result = import_excel_dataset(xlsx(rows), name)
    assert isinstance(result, dict), result
    created.append(result["dataset_id"])
    return result


def table_of(dataset_id):
    return Table.query.filter_by(dataset_id=dataset_id).order_by(Table.id).first()


def record_count(dataset_id):
    return Record.query.filter_by(table_id=table_of(dataset_id).id).count()


def dashboard(client, dataset_id):
    resp = client.get(f"/datasets/tables/{table_of(dataset_id).id}/dashboard")
    assert resp.status_code == 200
    return resp.json


# ── detección (no debe cambiar para los tipos que ya funcionaban) ────────────

@pytest.mark.parametrize("columns,expected", [
    (["Número de caso", "Nombre del denunciante", "Motivo de la denuncia", "Municipio"], "denuncias"),
    (["Municipio", "Alimento perro", "Alimento gato", "Total"], "donaton"),
    (["Mujer", "Hombre", "Municipio", "Guia 1", "Guia 2", "Guia 3", "Rural", "Urbana", "Fecha"],
     "personas_capacitadas_consolidado"),
    (["Mujer", "Hombre", "Municipio", "Guia 1"], "personas_capacitadas"),
    (["Nombres y Apellidos", "Municipio de Residencia", "Año de ingreso a la RAV", "TIPO DE VOLUNTARIADO"],
     "red_animalia"),
    (["Nombres y Apellidos", "Municipio", "Otro Telefono", "Correo Electrónico"], "animales"),
    (["Apropiacion Definitiva", "Presup. Disponible", "CDP Ejecutado"], "presupuesto"),
    (["Apropiacion Definitiva", "Presup. Disponible", "Total Ejecutado"], "presupuesto"),
    (["Presup. Definitivo", "Presup. Dispon.", "CDP Ejecutado", "Total Ejecutado"], "presupuesto"),
    (["POBLACIÓN PERROS 2026", "POBLACIÓN GATOS 2026", "MUNICIPIO"], "censo_animal"),
    (["Municipio", "Perros", "Gatos"], "censo_animal"),
    (["#", "NOMBRE COMPLETO DEL PROMOTOR"], "generico"),
])
def test_detection_by_columns(columns, expected):
    assert detect(columns) == expected


def test_z080_sap_full_format_is_detected_by_columns_not_by_name():
    assert detect(list(z080_sap(1)[0].keys())) == "presupuesto"
    # El nombre ya no decide: columnas genéricas con "Z080" en el nombre → genérico.
    fields = [SimpleNamespace(name="field"), SimpleNamespace(name="nombre")]
    assert detect_dataset_type(fields, name_hint="Z080 - corte") == "generico"


def test_missing_requirements_lists_what_is_missing():
    names = [normalize_name(c) for c in ["Presup. Definitivo", "CDP Ejecutado"]]
    assert not is_compatible("presupuesto", names)
    missing = missing_requirements("presupuesto", names)
    assert missing == ["presup_disponible o presup_dispon"]
    assert missing_requirements("generico", names) == []


# ── importación de un dataset nuevo ──────────────────────────────────────────

def test_new_dataset_persists_detected_type(app, created):
    r = do_import(created, z080_resumido(), "T new presupuesto")
    assert r["dataset_type"] == "presupuesto"
    assert db.session.get(Dataset, r["dataset_id"]).dataset_type == "presupuesto"

    g = do_import(created, promotores(), "T new generico")
    assert g["dataset_type"] == "generico"


# ── actualizaciones ──────────────────────────────────────────────────────────

def test_update_same_file_keeps_type_and_replaces_rows(app, client, created):
    r = do_import(created, z080_resumido(3), "T same file")
    res = update_excel_dataset(xlsx(z080_resumido(3)), r["dataset_id"])
    assert isinstance(res, dict), res
    assert res["dataset_type"] == "presupuesto"
    assert record_count(r["dataset_id"]) == 3
    assert dashboard(client, r["dataset_id"])["dataset_type"] == "presupuesto"


def test_update_with_other_name_keeps_type(app, client, created):
    r = do_import(created, z080_resumido(), "T other name")
    res = update_excel_dataset(xlsx(z080_resumido()), r["dataset_id"],
                               dataset_name="T other name - corte julio")
    assert isinstance(res, dict), res
    ds = db.session.get(Dataset, r["dataset_id"])
    assert ds.id == r["dataset_id"]          # mismo dataset, sin duplicar
    assert ds.name == "T other name - corte julio"
    assert ds.dataset_type == "presupuesto"
    assert Dataset.query.filter(Dataset.name.like("T other name%")).count() == 1


def test_update_with_new_rows(app, created):
    r = do_import(created, promotores(3), "T new rows")
    res = update_excel_dataset(xlsx(promotores(10)), r["dataset_id"])
    assert res["records_inserted"] == 10
    assert record_count(r["dataset_id"]) == 10


def test_update_with_additional_columns_reports_them(app, client, created):
    r = do_import(created, z080_resumido(), "T extra cols")
    rows = [dict(row, **{"Columna Nueva": 1}) for row in z080_resumido()]
    res = update_excel_dataset(xlsx(rows), r["dataset_id"])
    assert res["dataset_type"] == "presupuesto"
    assert res["columns_added"] == ["columna_nueva"]
    assert res["columns_removed"] == []
    assert dashboard(client, r["dataset_id"])["dataset_type"] == "presupuesto"


def test_update_missing_required_columns_is_rejected_without_changes(app, client, created):
    r = do_import(created, z080_resumido(3), "T missing cols")
    table_before = table_of(r["dataset_id"]).id
    rows = [{k: v for k, v in row.items() if k != "Presup. Disponible"} for row in z080_resumido(5)]

    body, status = update_excel_dataset(xlsx(rows), r["dataset_id"],
                                        dataset_name="T missing cols renamed")
    assert status == 409
    assert body["code"] == "DATASET_TYPE_INCOMPATIBLE"
    assert body["expected_type"] == "presupuesto"
    assert body["missing_columns"] == ["presup_disponible o presup_dispon"]
    assert "No se modificó" in body["message"]

    ds = db.session.get(Dataset, r["dataset_id"])
    assert ds.dataset_type == "presupuesto"
    assert ds.name == "T missing cols"            # el rename también se revierte
    assert table_of(r["dataset_id"]).id == table_before
    assert record_count(r["dataset_id"]) == 3
    assert dashboard(client, r["dataset_id"])["dataset_type"] == "presupuesto"


def test_update_incompatible_with_explicit_confirmation_changes_type(app, created):
    r = do_import(created, z080_resumido(), "T allow change")
    res = update_excel_dataset(xlsx(promotores()), r["dataset_id"], allow_type_change=True)
    assert isinstance(res, dict), res
    assert res["dataset_type"] == "generico"
    assert res["previous_dataset_type"] == "presupuesto"
    assert res["warnings"]


def test_update_endpoint_returns_409_and_honors_confirmation(app, client, created):
    from tests.test_admin_d1_endpoints import _seed, _token_for
    _seed(app)
    headers = {"Authorization": f"Bearer {_token_for(client, app, 'admin')}"}
    r = do_import(created, z080_resumido(), "T route")
    url = f"/datasets/{r['dataset_id']}/update-excel"

    resp = client.put(url, headers=headers, content_type="multipart/form-data",
                      data={"file": (xlsx(promotores()), "PROMOTORES.xlsx")})
    assert resp.status_code == 409
    assert resp.json["code"] == "DATASET_TYPE_INCOMPATIBLE"
    assert resp.json["missing_columns"]

    resp = client.put(url, headers=headers, content_type="multipart/form-data",
                      data={"file": (xlsx(promotores()), "PROMOTORES.xlsx"),
                            "allow_type_change": "true"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.json["dataset_type"] == "generico"

    # El listado expone el tipo guardado para el frontend.
    listed = client.get("/datasets/", headers=headers).json
    assert next(d for d in listed if d["id"] == r["dataset_id"])["dataset_type"] == "generico"


def test_empty_workbook_does_not_wipe_dataset(app, created):
    r = do_import(created, promotores(4), "T empty wb")
    body, status = update_excel_dataset(xlsx([]), r["dataset_id"])
    assert status == 400
    assert record_count(r["dataset_id"]) == 4


def test_generic_dataset_upgrades_when_new_file_matches_a_type(app, created):
    r = do_import(created, promotores(), "T upgrade")
    res = update_excel_dataset(xlsx(denuncias()), r["dataset_id"])
    assert res["dataset_type"] == "denuncias"


def test_legacy_dataset_without_stored_type(app, client, created):
    """Datasets anteriores a la columna: el tipo previo se deduce de sus campos."""
    r = do_import(created, z080_resumido(), "T legacy")
    ds = db.session.get(Dataset, r["dataset_id"])
    ds.dataset_type = None
    db.session.commit()

    # Render sin tipo guardado → detección por columnas
    assert dashboard(client, r["dataset_id"])["dataset_type_source"] == "detected"

    rows = [{k: v for k, v in row.items() if k != "Presup. Disponible"} for row in z080_resumido()]
    body, status = update_excel_dataset(xlsx(rows), r["dataset_id"])
    assert status == 409

    res = update_excel_dataset(xlsx(z080_resumido()), r["dataset_id"])
    assert res["dataset_type"] == "presupuesto"
    assert db.session.get(Dataset, r["dataset_id"]).dataset_type == "presupuesto"


def test_multi_sheet_update_validates_any_sheet(app, client, created):
    r = do_import(created, z080_resumido(), "T multi sheet")
    wb = xlsx_sheets({"Notas": promotores(), "Z080": z080_resumido()})
    res = update_excel_dataset(wb, r["dataset_id"])
    assert res["dataset_type"] == "presupuesto"
    tables = Table.query.filter_by(dataset_id=r["dataset_id"]).order_by(Table.id).all()
    names = [t.name for t in tables]
    assert names == ["notas", "z080"]
    # La hoja auxiliar no tiene las columnas: avisa en vez de caer en silencio.
    notas = client.get(f"/datasets/tables/{tables[0].id}/dashboard").json
    assert notas["dataset_type"] == "generico"
    assert notas["dataset_type_source"] == "fallback"
    assert "Presupuesto" in notas["dataset_type_warning"]
    z = client.get(f"/datasets/tables/{tables[1].id}/dashboard").json
    assert z["dataset_type"] == "presupuesto"
    assert z["dataset_type_source"] == "stored"


# ── casos reportados ─────────────────────────────────────────────────────────

def test_case_z080_monthly_update_from_resumido_to_sap_format(app, client, created):
    """El corte de marzo (resumido) se actualiza con el de junio (SAP completo)."""
    r = do_import(created, z080_resumido(), "Z080 - 30-03-2026-PRELIMINAR")
    res = update_excel_dataset(xlsx(z080_sap(4)), r["dataset_id"])
    assert isinstance(res, dict), res
    assert res["dataset_type"] == "presupuesto"
    assert "presup_definitivo" in res["columns_added"]
    assert "apropiacion_definitiva" in res["columns_removed"]

    dash = dashboard(client, r["dataset_id"])
    assert dash["dataset_type"] == "presupuesto"
    kpis = {k["label"]: k["value"] for k in dash["kpis"]}
    # Antes: apropiación $0 porque el builder no conocía "Presup. Definitivo".
    assert kpis["Presupuesto inicial"] == "${:,.0f}".format(sum(1000 + i for i in range(4)))
    assert kpis["Total obligaciones"] == "$1,600"
    section_ids = {s["id"] for s in dash["sections"]}
    assert "__detalle_proyectos__" in section_ids


def test_case_z080_sap_new_import_filters_animalista_project(app, client, created):
    rows = z080_sap(2) + z080_sap(3, project="Otro proyecto")
    r = do_import(created, rows, "Z080 - 17.06.2026_PRELIMINAR_JUNIO (1)")
    assert r["dataset_type"] == "presupuesto"
    dash = dashboard(client, r["dataset_id"])
    assert dash["total"] == 2


def test_case_personas_promotores_pyba(app, client, created):
    r = do_import(created, promotores(23), "PERSONAS PROMOTORES PYBA")
    assert r["dataset_type"] == "generico"
    res = update_excel_dataset(xlsx(promotores(25)), r["dataset_id"])
    assert res["dataset_type"] == "generico"
    dash = dashboard(client, r["dataset_id"])
    assert dash["dataset_type"] == "generico"
    assert dash["total"] == 25
    # El nombre del dataset se conserva (lo usa el modal de planes de acción).
    assert db.session.get(Dataset, r["dataset_id"]).name == "PERSONAS PROMOTORES PYBA"


def test_empty_table_keeps_generic_view(app):
    fields = [SimpleNamespace(name="apropiacion_definitiva"),
              SimpleNamespace(name="presup_disponible"),
              SimpleNamespace(name="cdp_ejecutado")]
    out = analyze_dataset(fields, [], stored_type="presupuesto")
    assert out["total"] == 0 and out["dataset_type"] == "generico"


# ── vista listado (datasets sin gráficas, p. ej. PROMOTORES PYBA) ────────────

def test_listing_section_for_datasets_without_charts(app, client, created):
    r = do_import(created, promotores(23), "T listado promotores")
    dash = dashboard(client, r["dataset_id"])
    assert dash["dataset_type"] == "generico"
    listing = [s for s in dash["sections"] if s["id"] == "__listado__"]
    assert len(listing) == 1
    sec = listing[0]
    assert sec["type"] == "table" and sec["span"] == "full"
    # La columna "#" (field) se omite: la tabla ya numera las filas.
    assert sec["columns"] == ["NOMBRE COMPLETO DEL PROMOTOR"]
    assert len(sec["rows"]) == 23
    assert sec["rows"][0] == {"NOMBRE COMPLETO DEL PROMOTOR": "Promotor 0"}


def test_listing_not_added_when_generic_has_charts(app, client, created):
    rows = [{"Municipio": m, "Nombre": f"P{i}"} for i, m in enumerate(["Cali", "Buga", "Cali", "Tuluá"] * 3)]
    r = do_import(created, rows, "T generico con graficas")
    ids = [s["id"] for s in dashboard(client, r["dataset_id"])["sections"]]
    assert ids and "__listado__" not in ids


def test_listing_caps_rows(app):
    from app.modules.datasets.dashboard.builders import generico
    fields = [SimpleNamespace(name="nombre", label="Nombre", type="text")]
    out = generico.build_listing_section(fields, {"nombre": [f"x{i}" for i in range(1500)]}, 1500)
    assert len(out["rows"]) == generico.LISTING_MAX_ROWS
    assert "1500" in out["subtitle"]
