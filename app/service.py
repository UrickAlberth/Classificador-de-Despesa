from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .data_sources import KnowledgeRepository
from .external_integrations import consultar_cnae_ibge, consultar_codigo_tributacao_nacional
from .gemini_client import GeminiClassifier
from .schemas import AnalysisRequest, AnalysisResponse, ClassificationSuggestion


class ExpenseClassificationService:
    def __init__(self, base_dir: Path):
        self.repo = KnowledgeRepository(base_dir)
        self.gemini = GeminiClassifier()

    def _avaliar_compatibilidade_cnae(self, cnae_empresa: str | None, cnaes_ibge: List[dict]) -> str:
        if not cnae_empresa:
            return "CNAE da empresa não informado."

        if not cnaes_ibge:
            return "Sem retorno IBGE no momento para comparação automática."

        cnae_empresa_clean = cnae_empresa.replace(".", "").replace("-", "").replace("/", "")
        for item in cnaes_ibge:
            code = str(item.get("id", "")).replace(".", "").replace("-", "")
            if cnae_empresa_clean.startswith(code[:5]) or code.startswith(cnae_empresa_clean[:5]):
                return "Compatível (correspondência aproximada entre CNAE da empresa e CNAE sugerido pelo IBGE)."

        return "Potencial incompatibilidade entre CNAE informado e objeto contratado."

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        search_query = f"{request.finalidade} {request.objeto_contratacao}"
        catmas_candidates = self.repo.search_catmas(search_query, max_results=20, only_active=True)
        tabela_3 = self.repo.rank_table_entries(self.repo.tables.tabela_3, search_query)
        tabela_4 = self.repo.rank_table_entries(self.repo.tables.tabela_4, search_query)
        tabela_5 = self.repo.rank_table_entries(self.repo.tables.tabela_5, search_query)
        tabela_7 = self.repo.rank_table_entries(self.repo.tables.tabela_7, search_query)
        tabela_8 = self.repo.rank_table_entries(self.repo.tables.tabela_8, search_query)

        external_enabled = os.getenv("ENABLE_EXTERNAL_LOOKUPS", "false").lower() == "true"
        cnaes_ibge = consultar_cnae_ibge(request.objeto_contratacao) if external_enabled else []
        tributacao = consultar_codigo_tributacao_nacional(request.objeto_contratacao) if external_enabled else []

        context_payload = {
            "catmas_candidates": catmas_candidates[: min(12, request.max_sugestoes * 4)],
            "tabela_3": tabela_3,
            "tabela_4": tabela_4,
            "tabela_5": tabela_5,
            "tabela_7": tabela_7,
            "tabela_8": tabela_8,
            "cnaes_ibge": cnaes_ibge,
            "tributacao": tributacao,
            "documentos_suporte_resumo": self.repo.process_docs_text[:6000],
            "texto_documentos_usuario": request.texto_documentos or "",
        }

        ai_output = self.gemini.suggest(request.finalidade, request.objeto_contratacao, context_payload)

        raw_sugestoes = ai_output.get("sugestoes", [])
        sugestoes: List[ClassificationSuggestion] = []
        for item in raw_sugestoes[: request.max_sugestoes]:
            sugestoes.append(ClassificationSuggestion(**item))

        if not sugestoes:
            raise ValueError("A IA não retornou sugestões válidas.")

        compatibilidade = ai_output.get("compatibilidade_cnae") or self._avaliar_compatibilidade_cnae(
            request.cnae_empresa, cnaes_ibge
        )

        alertas = list(ai_output.get("alertas", []))
        if any("SUSPENSO" in (c.get("situacao_item", "").upper()) for c in catmas_candidates[:3]):
            alertas.append("Há item CATMAS suspenso entre os candidatos de alta relevância.")
        if "incompatibilidade" in compatibilidade.lower():
            alertas.append("Inconsistência tributária potencial com risco de responsabilização solidária.")

        fontes = [
            "CATMAS/SIAD (Google Sheets com fallback CSV local)",
            "Classificador Econômico de Despesas MG",
            "Tabelas Orçamentárias (3, 4, 5, 7 e 8)",
            "Documentos administrativos do processo SEI 0038700-03.2026.8.13.0000",
        ]
        if cnaes_ibge:
            fontes.append("IBGE - API CNAE")
        if tributacao:
            fontes.append("Portal Nacional NFS-e - integração configurada")

        return AnalysisResponse(
            sugestoes=sugestoes,
            cruzamento_obrigatorio_realizado=True,
            compatibilidade_cnae=compatibilidade,
            alertas=alertas,
            alinhamento_normativo=["Lei 14.133/2021", "Resolução CNJ 370/2021"],
            fontes_consultadas=fontes,
        )
