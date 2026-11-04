from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import auth

app = FastAPI(
    title="API Atelier de Couture",
    description="Gestion des clients, mesures, commandes, paiements et livraisons.",
    version="1.0.0",
)

app.include_router(auth.router, prefix="/api/v1")


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
