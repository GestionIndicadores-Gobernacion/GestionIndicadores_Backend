def translate_db_error(error: Exception) -> str:
    msg = str(error).lower()

    if "value too long" in msg:
        return "El valor es demasiado largo para el campo."

    if "duplicate key value" in msg:
        return "Ya existe un registro con ese valor."

    if "not-null constraint" in msg:
        return "Hay campos obligatorios sin completar."

    if "foreign key constraint" in msg:
        return "No se puede eliminar o relacionar el registro."

    if "invalid input syntax" in msg:
        return "El formato de uno de los datos no es válido."

    return "Ocurrió un error al guardar la información."