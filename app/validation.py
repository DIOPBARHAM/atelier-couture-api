def traduire_erreur(err: dict) -> str:
    """Traduit une erreur de validation Pydantic en français."""
    type_erreur = err.get("type", "")
    ctx = err.get("ctx", {})
    msg = err.get("msg", "")

    if type_erreur == "missing":
        return "champ obligatoire"
    if type_erreur == "too_short":
        return f"doit contenir au moins {ctx.get('min_length')} élément(s)"
    if type_erreur == "string_too_short":
        return f"doit contenir au moins {ctx.get('min_length')} caractère(s)"
    if type_erreur == "string_too_long":
        return f"doit contenir au plus {ctx.get('max_length')} caractères"
    if type_erreur == "greater_than":
        return f"doit être strictement supérieur à {ctx.get('gt')}"
    if type_erreur == "greater_than_equal":
        return f"doit être supérieur ou égal à {ctx.get('ge')}"
    if type_erreur == "less_than_equal":
        return f"doit être inférieur ou égal à {ctx.get('le')}"
    if type_erreur == "less_than":
        return f"doit être strictement inférieur à {ctx.get('lt')}"
    if type_erreur in ("int_parsing", "float_parsing", "int_from_float"):
        return "doit être un nombre valide"
    if type_erreur == "bool_parsing":
        return "doit être vrai ou faux (true ou false)"
    if type_erreur in ("date_parsing", "date_from_datetime_parsing", "date_type"):
        return "date invalide (format attendu : AAAA-MM-JJ)"
    if type_erreur == "enum":
        return f"valeur invalide, valeurs possibles : {ctx.get('expected')}"
    if type_erreur == "json_invalid":
        return "le corps de la requête n'est pas un JSON valide"
    if type_erreur == "string_type":
        return "doit être un texte"
    if type_erreur == "list_type":
        return "doit être une liste"
    if "email" in msg.lower():
        return "adresse email invalide"
    return msg.removeprefix("Value error, ")
