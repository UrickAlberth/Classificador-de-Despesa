from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .auth import OIDCAuthMiddleware
from .document_ai import extract_text_from_uploaded_files, infer_objeto_contratacao_from_text
from .schemas import AnalysisRequest, AnalysisResponse
from .security import AuditLogMiddleware, HSTSMiddleware
from .service import ExpenseClassificationService


BASE_DIR = Path(__file__).resolve().parent.parent
service = ExpenseClassificationService(BASE_DIR)

app = FastAPI(
    title="TJMG Classificador de Despesa com IA",
    description="MVP de classificacao economica e tributaria com suporte a CATMAS, tabelas orcamentarias e OpenAI.",
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
app.add_middleware(HSTSMiddleware)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(OIDCAuthMiddleware)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "service": "TJMG Classificador de Despesa API",
        "status": "ok",
        "health": "/health",
        "analisar": "/analisar",
    }


@app.post("/analisar", response_model=AnalysisResponse)
def analisar_despesa(payload: AnalysisRequest):
    try:
        return service.analyze(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/analisar-com-arquivos", response_model=AnalysisResponse)
async def analisar_despesa_com_arquivos(
    finalidade: str = Form(...),
    objeto_contratacao: str = Form(""),
    texto_documentos: str = Form(""),
    cnpj: str = Form(""),
    cnae_empresa: str = Form(""),
    permitir_multiplas_classificacoes: bool = Form(True),
    max_sugestoes: int = Form(3),
    arquivos: list[UploadFile] = File(default=[]),
):
    try:
        extracted_text, file_metadata = extract_text_from_uploaded_files(arquivos)
        combined_text = "\n\n".join(part for part in [texto_documentos.strip(), extracted_text.strip()] if part)

        resolved_objeto = objeto_contratacao.strip()
        if not resolved_objeto:
            resolved_objeto = infer_objeto_contratacao_from_text(combined_text)

        if len(resolved_objeto) < 10:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Objeto da contratação não informado ou insuficiente. "
                    "Informe manualmente ou envie documentos com seção de objeto legível."
                ),
            )

        if file_metadata:
            combined_text = "\n".join([combined_text, "", "[Metadados de OCR]", *file_metadata]).strip()

        payload = AnalysisRequest(
            finalidade=finalidade,
            objeto_contratacao=resolved_objeto,
            texto_documentos=combined_text or None,
            cnpj=cnpj.strip() or None,
            cnae_empresa=cnae_empresa.strip() or None,
            permitir_multiplas_classificacoes=permitir_multiplas_classificacoes,
            max_sugestoes=max_sugestoes,
        )
        return service.analyze(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
