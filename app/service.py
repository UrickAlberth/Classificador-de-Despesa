from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic import ValidationError

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

    def _build_safe_suggestion(self, ai_item: dict, context_payload: dict) -> ClassificationSuggestion:
        catmas = context_payload.get("catmas_candidates", [])
        t3 = context_payload.get("tabela_3", [])
        t4 = context_payload.get("tabela_4", [])
        t5 = context_payload.get("tabela_5", [])
        t7 = context_payload.get("tabela_7", [])
        t8 = context_payload.get("tabela_8", [])
        trib = context_payload.get("tributacao", [])

        first_catmas = catmas[0] if catmas else {}

        defaults = {
            "item_catmas": first_catmas.get("item", "Sem correspondencia CATMAS"),
            "item_catmas_codigo": first_catmas.get("codigo_material_servico", "N/A"),
            "item_catmas_status": first_catmas.get("situacao_item", "N/A"),
            "item_catmas_linhas_fornecimento": first_catmas.get("linhas_fornecimento", "N/A"),
            "categoria_economica_tabela_3": (t3[0].get("valor", "N/A") if t3 else "N/A"),
            "grupo_natureza_despesa_tabela_4": (t4[0].get("valor", "N/A") if t4 else "N/A"),
            "modalidade_aplicacao_tabela_5": (t5[0].get("valor", "N/A") if t5 else "N/A"),
            "elemento_despesa_tabela_7": (t7[0].get("valor", "N/A") if t7 else "N/A"),
            "item_despesa_tabela_8": (t8[0].get("valor", "N/A") if t8 else "N/A"),
            "codigo_tributacao_nacional": (trib[0].get("codigo", "N/A") if trib else "N/A"),
            "justificativa": "Sugestao normalizada automaticamente devido a retorno parcial da IA.",
        }

        raw_item = ai_item or {}

        normalized: dict[str, str] = {}
        for field_name, default_value in defaults.items():
            incoming = raw_item.get(field_name, default_value)
            if incoming is None:
                normalized[field_name] = str(default_value)
                continue

            text_value = str(incoming).strip()
            normalized[field_name] = text_value if text_value else str(default_value)

        return ClassificationSuggestion(**normalized)

    def _enforce_existing_catmas(
        self,
        suggestion: ClassificationSuggestion,
        search_query: str,
        catmas_candidates: List[dict],
    ) -> ClassificationSuggestion:
        existing = self.repo.get_catmas_by_code(suggestion.item_catmas_codigo, only_active=True)
        if existing:
            return suggestion

        fallback_candidates = catmas_candidates or self.repo.search_catmas(search_query, max_results=10, only_active=True)
        if not fallback_candidates:
            fallback_candidates = self.repo.search_catmas(search_query, max_results=10, only_active=False)

        if not fallback_candidates:
            return suggestion

        replacement = fallback_candidates[0]
        return suggestion.model_copy(
            update={
                "item_catmas": replacement.get("item", suggestion.item_catmas),
                "item_catmas_codigo": replacement.get("codigo_material_servico", suggestion.item_catmas_codigo),
                "item_catmas_status": replacement.get("situacao_item", suggestion.item_catmas_status),
                "item_catmas_linhas_fornecimento": replacement.get(
                    "linhas_fornecimento", suggestion.item_catmas_linhas_fornecimento
                ),
                "justificativa": (
                    suggestion.justificativa
                    + " Codigo CATMAS retornado pela IA nao existe na base oficial ativa;"
                    + " foi substituido automaticamente por item real mais proximo."
                ),
            }
        )

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
            try:
                sugestao = ClassificationSuggestion(**item)
            except ValidationError:
                sugestao = self._build_safe_suggestion(item, context_payload)

            sugestoes.append(self._enforce_existing_catmas(sugestao, search_query, catmas_candidates))

        if not sugestoes:
            sugestao_fallback = self._build_safe_suggestion({}, context_payload)
            sugestoes.append(self._enforce_existing_catmas(sugestao_fallback, search_query, catmas_candidates))

        compatibilidade = ai_output.get("compatibilidade_cnae") or self._avaliar_compatibilidade_cnae(
            request.cnae_empresa, cnaes_ibge
        )

        alertas = list(ai_output.get("alertas", []))
        if self.repo.catmas_df.empty:
            alertas.append(
                "Base CATMAS indisponivel no momento (Google Sheets/CSV). Resultado retornado com dados parciais."
            )
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
