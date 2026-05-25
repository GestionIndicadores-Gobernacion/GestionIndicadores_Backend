"""Validaciones del catálogo de permisos (Bloque 3).

El propio módulo `catalog` corre validaciones al importarse (fail-fast).
Estos tests existen para que las asimetrías aparezcan como casos
explícitos en la salida de pytest cuando alguien rompa el catálogo.
"""


def test_catalog_imports_clean():
    # Si _validate_catalog() falla al importar, este test es lo primero
    # que reventará — pista clara para el desarrollador.
    from app.shared.permissions import catalog
    assert len(catalog.ALL_PERMISSIONS) > 0


def test_codes_are_unique():
    from app.shared.permissions.catalog import ALL_PERMISSIONS

    codes = [p.code for p in ALL_PERMISSIONS]
    assert len(codes) == len(set(codes)), "Hay codes duplicados en el catálogo"


def test_all_modules_are_valid():
    from app.shared.permissions.catalog import ALL_PERMISSIONS, ALL_MODULES

    for p in ALL_PERMISSIONS:
        assert p.module in ALL_MODULES, (
            f"Permiso {p.code!r} usa módulo {p.module!r} no declarado en ALL_MODULES"
        )


def test_constants_in_sync_with_catalog():
    """Cada PERM_* tiene entrada y cada entrada tiene PERM_*."""
    import app.shared.permissions.catalog as cat

    constants = {
        val for name, val in vars(cat).items()
        if name.startswith("PERM_") and isinstance(val, str)
    }
    catalog_codes = {p.code for p in cat.ALL_PERMISSIONS}

    only_constants = constants - catalog_codes
    only_catalog   = catalog_codes - constants

    assert not only_constants, (
        f"Constantes PERM_* sin entrada en ALL_PERMISSIONS: {sorted(only_constants)}"
    )
    assert not only_catalog, (
        f"Entradas en ALL_PERMISSIONS sin constante PERM_*: {sorted(only_catalog)}"
    )


def test_by_code_index_matches_catalog():
    from app.shared.permissions.catalog import ALL_PERMISSIONS, BY_CODE

    assert set(BY_CODE.keys()) == {p.code for p in ALL_PERMISSIONS}
    for p in ALL_PERMISSIONS:
        assert BY_CODE[p.code] is p


def test_grouping_preserves_total_count():
    from app.shared.permissions.catalog import (
        ALL_PERMISSIONS, permissions_by_module,
    )

    grouped = permissions_by_module()
    total_grouped = sum(len(v) for v in grouped.values())
    assert total_grouped == len(ALL_PERMISSIONS)


def test_codes_follow_naming_convention():
    """Los codes deben ser minúsculas, separados por `.`, con módulo prefijo."""
    import re
    from app.shared.permissions.catalog import ALL_PERMISSIONS, ALL_MODULES

    code_re = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
    for p in ALL_PERMISSIONS:
        assert code_re.match(p.code), f"Code no respeta convención: {p.code!r}"
        prefix = p.code.split(".", 1)[0]
        assert prefix == p.module, (
            f"El prefijo del code {p.code!r} ({prefix!r}) no coincide con "
            f"su módulo {p.module!r}"
        )
        assert prefix in ALL_MODULES, (
            f"Prefijo del code {p.code!r} no está declarado en ALL_MODULES"
        )
