from fastapi import FastAPI

app = FastAPI(title="API Atelier de Couture")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
