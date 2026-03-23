from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic import ValidationError

from .data_sources import KnowledgeRepository, _normalize_digits, _normalize_spaces, _score_text
from .document_ai import infer_objeto_contratacao_from_text
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

        def _extract_document_items(self, documento_text: str, tabela_8: List[dict]) -> List[dict]:
            """Segmenta documento e identifica itens por aderência à interpretação da Tabela 8."""
            if not documento_text or not tabela_8:
                return []
        
            doc_lower = documento_text.lower()
            encontrados: List[dict] = []
            usado: set[str] = set()
        
            for entry in tabela_8:
                interpretacao = str(entry.get("interpretacao", "")).lower().strip()
                descricao_item = str(entry.get("descricao", "")).lower().strip()
                codigo_item = str(entry.get("codigo", "")).strip()
            
                if not interpretacao:
                    continue
            
                palavras_chave = [p.strip() for p in interpretacao.split() if len(p.strip()) > 3]
                match_score = 0.0
            
                for palavra in palavras_chave[:5]:
                    if palavra in doc_lower:
                        match_score += 0.2
            
                if match_score >= 0.4 and codigo_item not in usado:
                    encontrados.append({
                        "codigo_item_tabela8": codigo_item,
                        "descricao_item_tabela8": descricao_item,
                        "interpretacao": interpretacao,
                        "match_score": match_score,
                    })
                    usado.add(codigo_item)
        
            encontrados.sort(key=lambda x: x["match_score"], reverse=True)
            return encontrados[:10]

    def _build_tabela8_enriched_query(
        self,
        base_objeto: str,
        search_query: str,
        documento_text: str,
        tabela_8: List[dict],
    ) -> str:
        """Constrói query para CATMAS usando interpretação da Tabela 8 com máxima prioridade."""
        base_reference = _normalize_spaces(
            f"{search_query} {base_objeto} {(documento_text or '')[:3000]}"
        )
        if not tabela_8:
            return _normalize_spaces(base_objeto or search_query)

        partes = [base_objeto or search_query]
        for item in tabela_8[:5]:
            interpretacao = str(item.get("interpretacao", "")).strip()
            descricao = str(item.get("descricao", "")).strip()

            if interpretacao and _score_text(base_reference, interpretacao) >= 0.15:
                partes.append(interpretacao)
                partes.append(interpretacao)
            elif interpretacao and _score_text(base_reference, interpretacao) >= 0.08:
                partes.append(interpretacao)
            
            if descricao and _score_text(base_reference, descricao) >= 0.10:
                partes.append(descricao)

        return _normalize_spaces(" ".join(partes))

    def _rerank_catmas_with_tabela8(
        self,
        catmas_candidates: List[dict],
        tabela_8: List[dict],
        search_reference: str,
    ) -> List[dict]:
        """Reordena CATMAS com MÁXIMO peso na correspondência com Interpretação Tabela 8."""
        if not catmas_candidates or not tabela_8:
            return catmas_candidates

        reranked: List[dict] = []
        top_tabela8 = tabela_8[:8]

        for candidate in catmas_candidates:
            base_score = self._to_float(candidate.get("score", 0), 0.0)
            candidate_text = _normalize_spaces(
                " ".join(
                    [
                        str(candidate.get("descricao_material_servico", "")),
                        str(candidate.get("item", "")),
                        str(candidate.get("linhas_fornecimento", "")),
                        str(candidate.get("natureza_despesa", "")),
                    ]
                )
            )

            best_cross_score = 0.0
            for entry in top_tabela8:
                interpretacao = str(entry.get("interpretacao", ""))
                descricao_item = str(entry.get("descricao", ""))

                catmas_interp = _score_text(candidate_text, interpretacao)
                catmas_desc = _score_text(candidate_text, descricao_item)
                doc_interp = _score_text(search_reference, interpretacao)
                doc_desc = _score_text(search_reference, descricao_item)

                cross_score = (
                    (catmas_interp * 0.65)
                    + (catmas_desc * 0.15)
                    + (doc_interp * 0.15)
                    + (doc_desc * 0.05)
                )
                best_cross_score = max(best_cross_score, cross_score)

            updated = dict(candidate)
            final_score = (base_score * 0.3) + (best_cross_score * 0.7)
            updated["score"] = f"{final_score:.4f}"
            reranked.append(updated)

        reranked.sort(key=lambda item: self._to_float(item.get("score", 0), 0.0), reverse=True)
        return reranked

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
        documento_text = (request.texto_documentos or "").strip()
        objeto_inferido = infer_objeto_contratacao_from_text(documento_text)

        tabela8_query = _normalize_spaces(f"{search_query} {documento_text[:3500]}")
        tabela_8 = self.repo.rank_table_entries(self.repo.tables.tabela_8, tabela8_query)

        document_items = self._extract_document_items(documento_text, tabela_8)

        # Quando houver anexos com objeto identificavel, ele vira a fonte primaria da busca CATMAS.
        base_objeto = objeto_inferido or request.objeto_contratacao.strip() or search_query
        
        if document_items:
            catmas_queries = [_normalize_spaces(f"{item['interpretacao']} {item['descricao_item_tabela8']}") for item in document_items]
            catmas_query = _normalize_spaces(" ".join(catmas_queries))
        else:
            catmas_query = self._build_tabela8_enriched_query(base_objeto, search_query, documento_text, tabela_8)
        
        catmas_candidates = self.repo.search_catmas(catmas_query, max_results=20, only_active=True)
        
        if document_items:
            catmas_all = []
            for item in document_items:
                item_query = _normalize_spaces(f"{item['interpretacao']} {item['descricao_item_tabela8']}")
                item_candidates = self.repo.search_catmas(item_query, max_results=5, only_active=True)
                catmas_all.extend(item_candidates)
            if catmas_all:
                seen_codes = set()
                for cand in catmas_candidates + catmas_all:
                    code = cand.get("codigo_material_servico")
                    if code not in seen_codes and code:
                        seen_codes.add(code)
                unique_candidates = []
                for cand in catmas_candidates + catmas_all:
                    if cand.get("codigo_material_servico") in seen_codes:
                        unique_candidates.append(cand)
                        seen_codes.discard(cand.get("codigo_material_servico"))
                catmas_candidates = unique_candidates[:25]
        
        search_reference = _normalize_spaces(f"{search_query} {documento_text[:3000]}")
        catmas_candidates = self._rerank_catmas_with_tabela8(catmas_candidates, tabela_8, search_reference)

        tabela_3 = self.repo.rank_table_entries(self.repo.tables.tabela_3, search_query)
        tabela_4 = self.repo.rank_table_entries(self.repo.tables.tabela_4, search_query)
        tabela_5 = self.repo.rank_table_entries(self.repo.tables.tabela_5, search_query)
        tabela_7 = self.repo.rank_table_entries(self.repo.tables.tabela_7, search_query)

        external_enabled = os.getenv("ENABLE_EXTERNAL_LOOKUPS", "false").lower() == "true"
        validacao_externa = (
            validar_cnae_e_tributacao(base_objeto, request.cnae_empresa)
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
            "objeto_contratacao_inferido_documentos": objeto_inferido,
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
