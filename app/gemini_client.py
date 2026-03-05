from __future__ import annotations

import difflib
import json
import os
import re
from typing import Any, Dict, List

from google import genai

# Pattern to extract CATMA mentions from free text such as:
#   "Item CATMAS: MICROCOMPUTADOR PORTATIL TIPO NOTEBOOK (4010010)"
#   "CATMAS 4010010 – NOTEBOOK"
#   "código 4010010"
_CATMA_MENTION_RE = re.compile(
    r"(?:item\s+catmas?|catmas?|código|codigo)[:\s-]*"
    r"(?P<desc>[A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][A-ZÀ-Ú0-9 /\-().]+?)?\s*"
    r"\(?\s*(?P<code>\d{5,10})\s*\)?",
    re.IGNORECASE,
)

# Maximum number of CATMA candidate codes to embed in the prompt header.
_MAX_CODES_IN_PROMPT = 12
# Minimum SequenceMatcher ratio to accept when replacing an AI item name with a
# candidate item name during CATMA code validation.
_MIN_ITEM_MATCH_RATIO = 0.5


class GeminiClassifier:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        self.enabled = bool(self.api_key)
        if self.enabled:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def suggest(
        self,
        finalidade: str,
        objeto_contratacao: str,
        context_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self.enabled or self.client is None:
            return self._fallback_response(context_payload)

        prompt = self._build_prompt(finalidade, objeto_contratacao, context_payload)
        response = self.client.models.generate_content(model=self.model_name, contents=prompt)
        text = getattr(response, "text", "") or ""
        parsed = self._extract_json(text)
        if parsed:
            parsed = self._validate_catmas_codes(parsed, context_payload)
            return parsed
        return self._fallback_response(context_payload)

    def _extract_json(self, text: str) -> Dict[str, Any] | None:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        raw = match.group(0)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # ------------------------------------------------------------------
    # CATMA code helpers
    # ------------------------------------------------------------------

    def _extract_catmas_from_text(self, text: str) -> List[Dict[str, str]]:
        """Extract CATMA item/code pairs mentioned in free text (e.g. user docs).

        Recognises patterns such as:
          "Item CATMAS: MICROCOMPUTADOR PORTATIL TIPO NOTEBOOK (4010010)"
          "CATMAS 4010010"
          "código 4010010"
        Returns a list of dicts with keys 'item' and 'codigo_material_servico'.
        """
        results: List[Dict[str, str]] = []
        for match in _CATMA_MENTION_RE.finditer(text):
            code = match.group("code").strip()
            desc = (match.group("desc") or "").strip().rstrip("–-").strip()
            results.append({"item": desc, "codigo_material_servico": code})
        return results

    def _valid_catmas_codes(self, context_payload: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """Build a lookup of valid CATMA codes → candidate dict from context.

        Also includes codes extracted from user-supplied document text so that
        explicitly mentioned codes are treated as authoritative.
        """
        lookup: Dict[str, Dict[str, str]] = {}
        for candidate in context_payload.get("catmas_candidates", []):
            code = str(candidate.get("codigo_material_servico", "")).strip()
            if code:
                lookup[code] = candidate

        doc_text = context_payload.get("texto_documentos_usuario", "")
        if doc_text:
            for mention in self._extract_catmas_from_text(doc_text):
                code = mention["codigo_material_servico"]
                if code not in lookup:
                    lookup[code] = mention

        return lookup

    def _validate_catmas_codes(
        self, ai_output: Dict[str, Any], context_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ensure every suggestion references a CATMA code that actually exists.

        When the AI returns a code that is not in the valid set, replace it with
        the best candidate whose *item* description most closely matches the
        AI-supplied item name.  If no close match can be found, mark as N/A.
        """
        valid = self._valid_catmas_codes(context_payload)
        if not valid:
            return ai_output

        valid_codes = set(valid.keys())
        candidates_list = list(context_payload.get("catmas_candidates", []))

        for suggestion in ai_output.get("sugestoes", []):
            code = str(suggestion.get("item_catmas_codigo", "")).strip()
            if code in valid_codes:
                continue  # already valid

            # Try to find the best matching candidate by item description
            ai_item_name = str(suggestion.get("item_catmas", "")).lower()
            best_code = "N/A"
            best_item = suggestion.get("item_catmas", "Sem correspondência CATMAS")
            best_ratio = 0.0
            for candidate in candidates_list:
                cand_name = str(candidate.get("item", "")).lower()
                if not cand_name:
                    continue
                ratio = difflib.SequenceMatcher(None, ai_item_name, cand_name).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_code = str(candidate.get("codigo_material_servico", "N/A")).strip()
                    best_item = str(candidate.get("item", best_item)).strip()

            suggestion["item_catmas_codigo"] = best_code
            if best_ratio > _MIN_ITEM_MATCH_RATIO:
                suggestion["item_catmas"] = best_item

        return ai_output

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def _build_prompt(self, finalidade: str, objeto_contratacao: str, context_payload: Dict[str, Any]) -> str:
        valid_codes_summary = ", ".join(
            f"{c.get('codigo_material_servico', '')} ({c.get('item', '')})"
            for c in context_payload.get("catmas_candidates", [])[:_MAX_CODES_IN_PROMPT]
            if c.get("codigo_material_servico")
        )

        doc_text = context_payload.get("texto_documentos_usuario", "")
        doc_catmas_hint = ""
        if doc_text:
            mentions = self._extract_catmas_from_text(doc_text)
            if mentions:
                doc_catmas_hint = (
                    "\nItens CATMAS identificados nos documentos do usuário: "
                    + "; ".join(
                        f"{m['item']} ({m['codigo_material_servico']})" for m in mentions
                    )
                )

        return f"""
Você é um assistente de classificação de despesa pública do TJMG.

Regras obrigatórias:
1) Cruzar Finalidade do Gasto x Objeto da Contratação x Tabelas Orçamentárias.
2) Priorizar item CATMAS com situação ATIVO; informar status e linhas de fornecimento.
3) Permitir múltiplas classificações quando aplicável.
4) Considerar conformidade com Lei 14.133/2021 e Resolução CNJ 370/2021.
5) Sinalizar riscos tributários e compatibilidade CNAE x objeto.
6) OBRIGATÓRIO: o campo "item_catmas_codigo" deve conter EXCLUSIVAMENTE um dos códigos
   da lista de candidatos CATMAS fornecida abaixo. Nunca invente ou extrapole códigos.
   Códigos válidos disponíveis: {valid_codes_summary if valid_codes_summary else "consultar catmas_candidates no contexto JSON"}.{doc_catmas_hint}

Entrada:
- Finalidade: {finalidade}
- Objeto da contratação: {objeto_contratacao}
- Contexto estruturado (JSON):
{json.dumps(context_payload, ensure_ascii=False)}

Retorne SOMENTE JSON no formato:
{{
  "sugestoes": [
    {{
      "item_catmas": "",
      "item_catmas_codigo": "",
      "item_catmas_status": "",
      "item_catmas_linhas_fornecimento": "",
      "categoria_economica_tabela_3": "",
      "grupo_natureza_despesa_tabela_4": "",
      "modalidade_aplicacao_tabela_5": "",
      "elemento_despesa_tabela_7": "",
      "item_despesa_tabela_8": "",
      "codigo_tributacao_nacional": "",
      "justificativa": ""
    }}
  ],
  "compatibilidade_cnae": "",
  "alertas": [""]
}}
"""

    # ------------------------------------------------------------------
    # Fallback (no AI available)
    # ------------------------------------------------------------------

    def _fallback_response(self, context_payload: Dict[str, Any]) -> Dict[str, Any]:
        catmas = context_payload.get("catmas_candidates", [])
        t3 = context_payload.get("tabela_3", [])
        t4 = context_payload.get("tabela_4", [])
        t5 = context_payload.get("tabela_5", [])
        t7 = context_payload.get("tabela_7", [])
        t8 = context_payload.get("tabela_8", [])
        trib = context_payload.get("tributacao", [])

        # Try to use CATMA codes explicitly mentioned in user documents first
        doc_text = context_payload.get("texto_documentos_usuario", "")
        doc_mentions = self._extract_catmas_from_text(doc_text) if doc_text else []

        # Build a lookup of valid candidates
        valid_lookup: Dict[str, Dict[str, str]] = {
            str(c.get("codigo_material_servico", "")).strip(): c for c in catmas if c.get("codigo_material_servico")
        }

        # Prefer a candidate whose code was explicitly mentioned in documents
        first_catmas: Dict[str, str] = {}
        for mention in doc_mentions:
            code = mention["codigo_material_servico"]
            if code in valid_lookup:
                first_catmas = valid_lookup[code]
                break

        if not first_catmas:
            first_catmas = catmas[0] if catmas else {}

        return {
            "sugestoes": [
                {
                    "item_catmas": first_catmas.get("item", "Sem correspondência CATMAS"),
                    "item_catmas_codigo": first_catmas.get("codigo_material_servico", "N/A"),
                    "item_catmas_status": first_catmas.get("situacao_item", "N/A"),
                    "item_catmas_linhas_fornecimento": first_catmas.get("linhas_fornecimento", "N/A"),
                    "categoria_economica_tabela_3": (t3[0]["valor"] if t3 else "N/A"),
                    "grupo_natureza_despesa_tabela_4": (t4[0]["valor"] if t4 else "N/A"),
                    "modalidade_aplicacao_tabela_5": (t5[0]["valor"] if t5 else "N/A"),
                    "elemento_despesa_tabela_7": (t7[0]["valor"] if t7 else "N/A"),
                    "item_despesa_tabela_8": (t8[0]["valor"] if t8 else "N/A"),
                    "codigo_tributacao_nacional": trib[0].get("codigo", "N/A") if trib else "N/A",
                    "justificativa": "Sugestão gerada por fallback determinístico por ausência/erro na chamada Gemini.",
                }
            ],
            "compatibilidade_cnae": "Análise preliminar sem IA: revisar CNAE e objeto para aderência final.",
            "alertas": ["Verificar manualmente compatibilidade tributária antes da emissão fiscal."],
        }
