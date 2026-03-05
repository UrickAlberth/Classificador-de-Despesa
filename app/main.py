from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from .schemas import AnalysisRequest, AnalysisResponse
from .service import ExpenseClassificationService


BASE_DIR = Path(__file__).resolve().parent.parent
service = ExpenseClassificationService(BASE_DIR)

app = FastAPI(
    title="TJMG Classificador de Despesa com IA",
    description="MVP de classificação econômica e tributária com suporte a CATMAS, tabelas orçamentárias e Gemini 2.5.",
    version="0.1.0",
)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.post("/analisar", response_model=AnalysisResponse)
def analisar_despesa(payload: AnalysisRequest):
    try:
        return service.analyze(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
