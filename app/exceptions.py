class ErreurMetier(Exception):
    """Erreur levée par les services ; la route la transforme en réponse HTTP."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class NonTrouve(ErreurMetier):
    def __init__(self, detail: str):
        super().__init__(404, detail)


class Conflit(ErreurMetier):
    def __init__(self, detail: str):
        super().__init__(409, detail)


class DonneesInvalides(ErreurMetier):
    def __init__(self, detail: str):
        super().__init__(422, detail)


class AccesInterdit(ErreurMetier):
    def __init__(self, detail: str):
        super().__init__(403, detail)
