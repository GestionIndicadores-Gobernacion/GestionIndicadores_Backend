"""Recognize both supported Red Animalia workbook schemas."""


def is_red_animalia(field_names):
    names = set(field_names)
    legacy = (
        "tipo_de_vinculacion_dentro_de_la_red_animalia_valle" in names
        and any("perros" in name for name in names)
        and any("gatos" in name for name in names)
    )
    unified = {
        "nombres_y_apellidos", "municipio_de_residencia",
        "ano_de_ingreso_a_la_rav", "tipo_de_voluntariado",
    }.issubset(names)
    return legacy or unified
