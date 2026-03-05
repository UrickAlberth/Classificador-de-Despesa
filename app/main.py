from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .schemas import AnalysisRequest, AnalysisResponse
from .service import ExpenseClassificationService


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
service = ExpenseClassificationService(BASE_DIR)

app = FastAPI(
    title="TJMG Classificador de Despesa com IA",
    description="MVP de classificação econômica e tributária com suporte a CATMAS, tabelas orçamentárias e Gemini 2.5.",
    version="0.1.0",
)

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/")
def root():
    index_html = FRONTEND_DIST / "index.html"
    if index_html.exists():
        return FileResponse(str(index_html))
    return {"status": "ok"}


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.post("/analisar", response_model=AnalysisResponse)
def analisar_despesa(payload: AnalysisRequest):
    try:
        return service.analyze(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):  # noqa: ARG001
    index_html = FRONTEND_DIST / "index.html"
    if index_html.exists():
        return FileResponse(str(index_html))
    raise HTTPException(status_code=404, detail="Not found")
