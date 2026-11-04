from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ErreurMetier
from app.routers import auth, catalogue, clients, utilisateurs
from app.validation import traduire_erreur

app = FastAPI(
    title="API Atelier de Couture",
    description="Gestion des clients, mesures, commandes, paiements et livraisons.",
    version="1.0.0",
)

@app.exception_handler(ErreurMetier)
async def gerer_erreur_metier(request: Request, exc: ErreurMetier) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}
    )


@app.exception_handler(RequestValidationError)
async def gerer_validation(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Transforme les erreurs de validation Pydantic en un message texte français."""
    messages = []
    for err in exc.errors():
        champ = ".".join(
            str(part) for part in err["loc"] if part not in ("body", "query", "path")
        )
        msg = traduire_erreur(err).removeprefix("Value error, ")
        messages.append(f"{champ} : {msg}" if champ else msg)
    return JSONResponse(status_code=422, content={"detail": " ; ".join(messages)})


app.include_router(auth.router, prefix="/api/v1")
app.include_router(catalogue.router, prefix="/api/v1")
app.include_router(clients.router, prefix="/api/v1")
app.include_router(utilisateurs.router, prefix="/api/v1")


@app.get("/health", tags=["Santé"])
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Vérifie que l'API répond et que PostgreSQL est joignable."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503, detail="Base de données inaccessible"
        ) from exc
    return {"status": "ok"}
