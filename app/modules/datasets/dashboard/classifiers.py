from .formatters import norm, fill_rate, unique_clean, is_yes, is_no


def classify_fields(fields, field_values, total):
    classified = {
        "location": [], "demographic": [], "service": [],
        "numeric": [], "program": [], "contact": [],
        "yesno": [], "categorical": [], "identifier": []
    }

    LOCATION_KW   = {"municipio","ciudad","departamento","localidad","barrio","zona","region","ubicacion"}
    DEMOGRAPHIC_KW = {"sexo","genero","edad","escolar","educativo","educacion","nivel","estudio"}
    SERVICE_KW    = {"servicio","albergue","fundacion","tipo","actividad","rol"}
    PROGRAM_KW    = {"capacitacion","esterilizacion","alimento","gobernacion","programa","participacion","jornada","entrega"}
    CONTACT_KW    = {"telefono","correo","email","direccion","celular","whatsapp"}
    IDENTIFIER_KW = {"nombre","id","codigo","observacion","nota","comentario","unnamed","cuantos","descripcion","cual"}

    def match(name, kws):
        n = norm(name)
        return any(k in n for k in kws)

    for f in fields:
        vals = field_values[f.name]
        fill = fill_rate(vals, total)
        unique = unique_clean(vals)
        n_unique = len(unique)

        if match(f.name, CONTACT_KW):
            classified["contact"].append(f); continue
        if fill < 3:
            classified["identifier"].append(f); continue
        if match(f.name, IDENTIFIER_KW):
            classified["identifier"].append(f); continue
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

        yes_no = sum(1 for v in vals if is_yes(v) or is_no(v))
        if yes_no > total * 0.25 and n_unique <= 8:
            classified["yesno"].append(f); continue
        if 2 <= n_unique <= 30:
            classified["categorical"].append(f); continue

        classified["identifier"].append(f)

    return classified