from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import AnalysisRequest, AnalysisResponse
from .service import ExpenseClassificationService


BASE_DIR = Path(__file__).resolve().parent.parent
service = ExpenseClassificationService(BASE_DIR)

app = FastAPI(
    title="TJMG Classificador de Despesa com IA",
    description="MVP de classificação econômica e tributária com suporte a CATMAS, tabelas orçamentárias e Gemini 2.5.",
    version="0.1.0",
)


def _resolve_allowed_origins() -> list[str]:
    configured = os.getenv("FRONTEND_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    # Default aberto para simplificar integração entre deploys na Vercel.
    return ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
