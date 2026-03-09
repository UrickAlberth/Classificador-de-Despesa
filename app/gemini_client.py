from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from google import genai


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

    def _build_prompt(self, finalidade: str, objeto_contratacao: str, context_payload: Dict[str, Any]) -> str:
        return f"""
Você é um assistente de classificação de despesa pública do TJMG.

Regras obrigatórias:
1) Cruzar Finalidade do Gasto x Objeto da Contratação x Tabelas Orçamentárias.
2) Priorizar item CATMAS com situação ATIVO; informar status e linhas de fornecimento.
3) Permitir múltiplas classificações quando aplicável.
4) Considerar conformidade com Lei 14.133/2021 e Resolução CNJ 370/2021.
5) Sinalizar riscos tributários e compatibilidade CNAE x objeto.
6) Diferenciar claramente se o item é MATERIAL ou SERVIÇO e justificar a escolha.
7) Informar explicitamente o número do CATMAS selecionado no campo item_catmas_codigo, sem texto adicional.

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

    def _fallback_response(self, context_payload: Dict[str, Any]) -> Dict[str, Any]:
        catmas = context_payload.get("catmas_candidates", [])
        t3 = context_payload.get("tabela_3", [])
        t4 = context_payload.get("tabela_4", [])
        t5 = context_payload.get("tabela_5", [])
        t7 = context_payload.get("tabela_7", [])
        t8 = context_payload.get("tabela_8", [])
        trib = context_payload.get("tributacao", [])

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
