from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic import ValidationError

from .data_sources import KnowledgeRepository, _normalize_digits, _score_text
from .external_integrations import validar_cnae_e_tributacao
from .gemini_client import OpenAIClassifier
from .schemas import AnalysisRequest, AnalysisResponse, ClassificationSuggestion, SimilarCatmasItem


class ExpenseClassificationService:
    def __init__(self, base_dir: Path):
        self.repo = KnowledgeRepository(base_dir)
        self.ai = OpenAIClassifier()

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

    def _to_bool(self, value: object, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "sim", "yes", "1"}:
                return True
            if lowered in {"false", "nao", "não", "no", "0"}:
                return False
        return default

    def _to_float(self, value: object, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _table_field(self, table_data: List[dict], index: int = 0) -> tuple[str, str]:
        if len(table_data) <= index:
            return "N/A", "N/A"
        row = table_data[index]
        return str(row.get("codigo", "N/A")), str(row.get("descricao", "N/A"))

    def _build_similar_items(self, catmas_candidates: List[dict], limit: int = 5) -> List[SimilarCatmasItem]:
        items: List[SimilarCatmasItem] = []
        for candidate in catmas_candidates[:limit]:
            descricao = str(
                candidate.get("descricao_material_servico")
                or candidate.get("item", "")
            ).strip()
            items.append(
                SimilarCatmasItem(
                    codigo=str(candidate.get("codigo_material_servico", "")).strip(),
                    descricao=descricao,
                    situacao=str(candidate.get("situacao_item", "")).strip(),
                    grau_similaridade=round(self._to_float(candidate.get("score", 0), 0.0), 4),
                )
            )
        return items

    def _is_exact_catmas_match(self, search_query: str, candidate: dict) -> bool:
        candidate_score = self._to_float(candidate.get("score", 0), 0.0)
        query_digits = _normalize_digits(search_query)
        candidate_code = _normalize_digits(str(candidate.get("codigo_material_servico", "")))
        if query_digits and candidate_code and candidate_code == query_digits:
            return True
        return candidate_score >= 0.9

    def _avaliar_linha_fornecimento(self, search_query: str, linhas_fornecimento: str) -> str:
        if not linhas_fornecimento or linhas_fornecimento.strip().upper() == "N/A":
            return "Nao foi possivel validar linha de fornecimento automaticamente."

        score = _score_text(search_query, linhas_fornecimento)
        if score >= 0.2:
            return "Compativel"
        return "Possivel incompatibilidade entre objeto contratado e linha de fornecimento"

    def _build_safe_suggestion(self, ai_item: dict, context_payload: dict) -> ClassificationSuggestion:
        catmas = context_payload.get("catmas_candidates", [])
        t3 = context_payload.get("tabela_3", [])
        t4 = context_payload.get("tabela_4", [])
        t5 = context_payload.get("tabela_5", [])
        t7 = context_payload.get("tabela_7", [])
        t8 = context_payload.get("tabela_8", [])
        trib = context_payload.get("tributacao", [])

        first_catmas = catmas[0] if catmas else {}
        t3_code, t3_desc = self._table_field(t3)
        t4_code, t4_desc = self._table_field(t4)
        t5_code, t5_desc = self._table_field(t5)
        t7_code, t7_desc = self._table_field(t7)
        t8_code, t8_desc = self._table_field(t8)
        similar_items = self._build_similar_items(catmas)
        default_exact_match = bool(first_catmas) and self._is_exact_catmas_match(
            context_payload.get("search_query", ""), first_catmas
        )
        default_similarity = self._to_float(first_catmas.get("score", 0), 0.0) if first_catmas else 0.0
        default_linha = self._avaliar_linha_fornecimento(
            context_payload.get("search_query", ""),
            str(first_catmas.get("linhas_fornecimento", "N/A")),
        )
        default_motivo = (
            "Classificacao com correspondencia exata CATMAS." if default_exact_match else "Sem correspondencia exata CATMAS; validar manualmente."
        )

        defaults = {
            "item_catmas": first_catmas.get("descricao_material_servico")
            or first_catmas.get("item", "Sem correspondencia CATMAS"),
            "item_catmas_codigo": first_catmas.get("codigo_material_servico", "N/A"),
            "item_catmas_status": first_catmas.get("situacao_item", "N/A"),
            "item_catmas_linhas_fornecimento": first_catmas.get("linhas_fornecimento", "N/A"),
            "correspondencia_exata_catmas": default_exact_match,
            "grau_similaridade_catmas": default_similarity,
            "categoria_economica_tabela_3_codigo": t3_code,
            "categoria_economica_tabela_3_descricao": t3_desc,
            "grupo_natureza_despesa_tabela_4_codigo": t4_code,
            "grupo_natureza_despesa_tabela_4_descricao": t4_desc,
            "modalidade_aplicacao_tabela_5_codigo": t5_code,
            "modalidade_aplicacao_tabela_5_descricao": t5_desc,
            "elemento_despesa_tabela_7_codigo": t7_code,
            "elemento_despesa_tabela_7_descricao": t7_desc,
            "item_despesa_tabela_8_codigo": t8_code,
            "item_despesa_tabela_8_descricao": t8_desc,
            "codigo_tributacao_nacional": (trib[0].get("codigo", "N/A") if trib else "N/A"),
            "codigo_tributacao_nacional_descricao": (trib[0].get("descricao", "N/A") if trib else "N/A"),
            "linha_fornecimento_compativel": default_linha,
            "requer_validacao_humana": not default_exact_match,
            "motivo_validacao_humana": default_motivo,
            "itens_semelhantes_catmas": [item.model_dump() for item in similar_items],
            "justificativa": "Sugestao normalizada automaticamente devido a retorno parcial da IA.",
        }

        raw_item = ai_item or {}

        normalized: dict[str, object] = {}
        for field_name, default_value in defaults.items():
            incoming = raw_item.get(field_name, default_value)
            if incoming is None:
                normalized[field_name] = default_value
                continue

            if isinstance(default_value, bool):
                normalized[field_name] = self._to_bool(incoming, default_value)
            elif isinstance(default_value, float):
                normalized[field_name] = round(self._to_float(incoming, default_value), 4)
            elif isinstance(default_value, list):
                normalized[field_name] = incoming if isinstance(incoming, list) and incoming else default_value
            else:
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
        replacement_score = round(self._to_float(replacement.get("score", 0), 0.0), 4)
        exact_match = self._is_exact_catmas_match(search_query, replacement)
        return suggestion.model_copy(
            update={
                "item_catmas": replacement.get("descricao_material_servico")
                or replacement.get("item", suggestion.item_catmas),
                "item_catmas_codigo": replacement.get("codigo_material_servico", suggestion.item_catmas_codigo),
                "item_catmas_status": replacement.get("situacao_item", suggestion.item_catmas_status),
                "item_catmas_linhas_fornecimento": replacement.get(
                    "linhas_fornecimento", suggestion.item_catmas_linhas_fornecimento
                ),
                "correspondencia_exata_catmas": exact_match,
                "grau_similaridade_catmas": replacement_score,
                "linha_fornecimento_compativel": self._avaliar_linha_fornecimento(
                    search_query,
                    str(replacement.get("linhas_fornecimento", suggestion.item_catmas_linhas_fornecimento)),
                ),
                "requer_validacao_humana": not exact_match,
                "motivo_validacao_humana": (
                    "Classificacao com correspondencia exata CATMAS."
                    if exact_match
                    else "Sem correspondencia exata CATMAS; necessario validar manualmente antes da contratacao."
                ),
                "itens_semelhantes_catmas": self._build_similar_items(fallback_candidates),
                "justificativa": (
                    suggestion.justificativa
                    + " Codigo CATMAS retornado pela IA nao existe na base oficial ativa;"
                    + " foi substituido automaticamente por item real mais proximo."
                ),
            }
        )

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        search_query = f"{request.finalidade} {request.objeto_contratacao}"
        catmas_query = request.objeto_contratacao.strip() or search_query
        catmas_candidates = self.repo.search_catmas(catmas_query, max_results=20, only_active=True)
        tabela_3 = self.repo.rank_table_entries(self.repo.tables.tabela_3, search_query)
        tabela_4 = self.repo.rank_table_entries(self.repo.tables.tabela_4, search_query)
        tabela_5 = self.repo.rank_table_entries(self.repo.tables.tabela_5, search_query)
        tabela_7 = self.repo.rank_table_entries(self.repo.tables.tabela_7, search_query)
        tabela_8 = self.repo.rank_table_entries(self.repo.tables.tabela_8, search_query)

        external_enabled = os.getenv("ENABLE_EXTERNAL_LOOKUPS", "false").lower() == "true"
        validacao_externa = (
            validar_cnae_e_tributacao(request.objeto_contratacao, request.cnae_empresa)
            if external_enabled
            else {
                "cnaes_ibge": [],
                "codigos_tributacao_nacional": [],
                "compatibilidade_cnae": "Consultas externas desabilitadas.",
            }
        )
        cnaes_ibge = validacao_externa.get("cnaes_ibge", [])
        tributacao = validacao_externa.get("codigos_tributacao_nacional", [])

        context_payload = {
            "catmas_candidates": catmas_candidates[: min(12, request.max_sugestoes * 4)],
            "search_query": catmas_query,
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

        ai_output = self.ai.suggest(request.finalidade, request.objeto_contratacao, context_payload)

        raw_sugestoes = ai_output.get("sugestoes", [])
        sugestoes: List[ClassificationSuggestion] = []
        total_sugestoes = request.max_sugestoes if request.permitir_multiplas_classificacoes else 1
        for item in raw_sugestoes[:total_sugestoes]:
            try:
                sugestao = ClassificationSuggestion(**item)
            except ValidationError:
                sugestao = self._build_safe_suggestion(item, context_payload)

            sugestoes.append(self._enforce_existing_catmas(sugestao, catmas_query, catmas_candidates))

        if not sugestoes:
            sugestao_fallback = self._build_safe_suggestion({}, context_payload)
            sugestoes.append(self._enforce_existing_catmas(sugestao_fallback, catmas_query, catmas_candidates))

        if not request.permitir_multiplas_classificacoes:
            sugestoes = sugestoes[:1]

        for index, sugestao in enumerate(sugestoes):
            if sugestao.grau_similaridade_catmas <= 0:
                score = self._to_float(catmas_candidates[index].get("score", 0), 0.0) if len(catmas_candidates) > index else 0.0
                sugestoes[index] = sugestao.model_copy(update={"grau_similaridade_catmas": round(score, 4)})

        compatibilidade = (
            ai_output.get("compatibilidade_cnae")
            or str(validacao_externa.get("compatibilidade_cnae", "")).strip()
            or self._avaliar_compatibilidade_cnae(request.cnae_empresa, cnaes_ibge)
        )

        alertas = list(ai_output.get("alertas", []))
        observacoes_tecnicas: List[str] = []
        if self.repo.catmas_df.empty:
            alertas.append(
                "Base CATMAS indisponivel no momento (Google Sheets/CSV). Resultado retornado com dados parciais."
            )
        if any("SUSPENSO" in (c.get("situacao_item", "").upper()) for c in catmas_candidates[:5]):
            alertas.append("Ha item CATMAS suspenso entre os candidatos de alta relevancia.")
        if any("INATIVO" in (c.get("situacao_item", "").upper()) for c in catmas_candidates[:5]):
            alertas.append("Ha item CATMAS inativo entre os candidatos de alta relevancia.")
        if "incompatibilidade" in compatibilidade.lower():
            alertas.append("Alerta de risco fiscal ou orcamentario: incompatibilidade CNAE x servico.")
        if external_enabled and request.cnpj and not request.cnae_empresa:
            alertas.append("CNPJ informado sem CNAE da empresa. Informe CNAE para validacao completa de compatibilidade.")

        if len(catmas_candidates) > 1:
            top_score = self._to_float(catmas_candidates[0].get("score", 0), 0.0)
            second_score = self._to_float(catmas_candidates[1].get("score", 0), 0.0)
            if abs(top_score - second_score) <= 0.08:
                alertas.append("Ambiguidade detectada entre itens CATMAS de maior relevancia; revise alternativas antes da decisao final.")

        for sugestao in sugestoes:
            if sugestao.item_catmas_status.upper() in {"SUSPENSO", "INATIVO"}:
                alertas.append(
                    f"Item CATMAS selecionado com situacao {sugestao.item_catmas_status}. Necessaria revisao antes da contratacao."
                )
            if not sugestao.correspondencia_exata_catmas:
                alertas.append("Nao foi encontrada correspondencia exata no CATMAS para ao menos uma sugestao.")
                observacoes_tecnicas.append(
                    "Foram apresentados itens semelhantes com grau de similaridade e recomendacao de validacao humana."
                )
            if "incompatibilidade" in sugestao.linha_fornecimento_compativel.lower():
                alertas.append("Possivel incompatibilidade de linha de fornecimento com o objeto contratado.")

        if not alertas:
            observacoes_tecnicas.append("Sem inconsistencias criticas detectadas nas validacoes automaticas.")

        observacoes_tecnicas.append("A classificacao cruza finalidade, objeto, CATMAS e tabelas orcamentarias oficiais.")
        observacoes_tecnicas.append("Nao sao gerados codigos novos: somente codigos presentes em bases oficiais sao aceitos.")
        if any(not s.correspondencia_exata_catmas for s in sugestoes):
            observacoes_tecnicas.append("Validacao humana obrigatoria para confirmar item final quando nao ha correspondencia exata.")

        alertas = list(dict.fromkeys(alertas))
        observacoes_tecnicas = list(dict.fromkeys(observacoes_tecnicas))

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
            observacoes_tecnicas=observacoes_tecnicas,
            alinhamento_normativo=["Lei 14.133/2021", "Resolução CNJ 370/2021"],
            fontes_consultadas=fontes,
        )
