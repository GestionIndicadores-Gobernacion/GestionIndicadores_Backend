def normalize_payload(data):
    """
    Convierte un modelo SQLAlchemy en un dict usable.
    flask-smorest + SQLAlchemyAutoSchema envían modelos en lugar de dicts.
    """
    if isinstance(data, dict):
        return data

    # Si es modelo -> convertir
    d = data.__dict__.copy()
    d.pop("_sa_instance_state", None)
    return d
