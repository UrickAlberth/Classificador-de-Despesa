from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    finalidade: str = Field(..., min_length=10)
    objeto_contratacao: str = Field(..., min_length=10)
    texto_documentos: Optional[str] = None
    cnpj: Optional[str] = None
    cnae_empresa: Optional[str] = None
    permitir_multiplas_classificacoes: bool = True
    max_sugestoes: int = Field(3, ge=1, le=10)


class ClassificationSuggestion(BaseModel):
    item_catmas: str
    item_catmas_codigo: str
    item_catmas_status: str
    item_catmas_linhas_fornecimento: str
    categoria_economica_tabela_3: str
    grupo_natureza_despesa_tabela_4: str
    modalidade_aplicacao_tabela_5: str
    elemento_despesa_tabela_7: str
    item_despesa_tabela_8: str
    codigo_tributacao_nacional: str
    justificativa: str


class AnalysisResponse(BaseModel):
    sugestoes: List[ClassificationSuggestion]
    cruzamento_obrigatorio_realizado: bool
    compatibilidade_cnae: str
    alertas: List[str]
    alinhamento_normativo: List[str]
    fontes_consultadas: List[str]
