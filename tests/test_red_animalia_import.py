import os
from types import SimpleNamespace

import pandas as pd
import pytest

from app.core.extensions import db
from app.modules.datasets.dashboard.analyzer import detect_dataset_type
from app.modules.datasets.models.dataset import Dataset
from app.modules.datasets.models.table import Table
from app.modules.datasets.models.record import Record
from app.modules.datasets.services.excel_import_handler import (
    _clean_dataframe, import_excel_dataset, update_excel_dataset,
)
from app.utils.normalizers import normalize_name


def detect(columns):
    return detect_dataset_type([SimpleNamespace(name=normalize_name(c)) for c in columns])


def test_recognizes_both_formats_without_classifying_other_animal_datasets():
    assert detect(['Tipo de vinculación dentro de la Red Animalia Valle', 'Perros cantidad', 'Gatos cantidad']) == 'red_animalia'
    assert detect(['Nombres y Apellidos', 'Municipio de Residencia', 'Año de ingreso a la RAV', 'TIPO DE VOLUNTARIADO']) == 'red_animalia'
    assert detect(['Municipio', 'Perros', 'Gatos']) == 'censo_animal'
    assert detect(['Nombres y Apellidos', 'Municipio de Residencia', 'TIPO DE VOLUNTARIADO']) == 'generico'


def test_preserves_sparse_members_only_for_animalia():
    columns = ['Nombres y Apellidos', 'Municipio de Residencia', 'Año de ingreso a la RAV', 'TIPO DE VOLUNTARIADO'] + [f'Pregunta {i}' for i in range(15)]
    frame = pd.DataFrame([['Integrante', 'Cali', 2026, 'Rescatista'] + [1]*15,
                          ['Integrante incompleto', 'Cali'] + [None]*17,
                          [None]*19], columns=columns)
    cleaned, _ = _clean_dataframe(frame)
    assert len(cleaned) == 2
    generic, _ = _clean_dataframe(frame.rename(columns={'Año de ingreso a la RAV': 'Año'}))
    assert len(generic) == 1


@pytest.mark.skipif(not os.getenv('ANIMALIA_TEST_XLSX'), reason='Optional private workbook regression')
def test_actual_workbook_import_and_replace_preserve_449_members(app, client):
    path = os.environ['ANIMALIA_TEST_XLSX']
    with open(path, 'rb') as source:
        result = import_excel_dataset(source, 'Animalia regression workbook')
    assert isinstance(result, dict), result
    dataset_id = result['dataset_id']
    try:
        assert result['records_inserted'] == 449
        assert result['skipped_rows'] == 262
        with open(path, 'rb') as source:
            updated = update_excel_dataset(source, dataset_id)
        assert updated['records_inserted'] == 449
        assert updated['failed_rows'] == 0
        table = Table.query.filter_by(dataset_id=dataset_id).one()
        assert Record.query.filter_by(table_id=table.id).count() == 449
        response = client.get(f'/datasets/tables/{table.id}/dashboard')
        assert response.status_code == 200
        assert response.json['dataset_type'] == 'red_animalia'
        assert response.json['total'] == 449
    finally:
        db.session.delete(db.session.get(Dataset, dataset_id))
        db.session.commit()
