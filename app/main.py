from fastapi import FastAPI

app = FastAPI(
    title="API Atelier de Couture",
    description="Gestion des clients, mesures, commandes, paiements et livraisons.",
    version="1.0.0",
)


@app.get("/health", tags=["Santé"])
def health():
    """Vérifie que l'API répond (la connexion à la base sera ajoutée plus tard)."""
    return {"status": "ok"}
