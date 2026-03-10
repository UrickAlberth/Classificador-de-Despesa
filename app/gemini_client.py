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
8) NUNCA inventar código CATMAS. Use somente código existente nos catmas_candidates fornecidos.
9) Se não houver correspondência exata, selecionar os itens CATMAS reais mais próximos da busca e informar isso na justificativa.
10) Para cada sugestão, informe grau de similaridade CATMAS e se exige validação humana.
11) Quando houver ambiguidade, liste itens semelhantes em itens_semelhantes_catmas.
12) Retorne código e descrição separados para tabelas orçamentárias 3, 4, 5, 7 e 8.

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
            "correspondencia_exata_catmas": true,
            "grau_similaridade_catmas": 0.0,
            "categoria_economica_tabela_3_codigo": "",
            "categoria_economica_tabela_3_descricao": "",
            "grupo_natureza_despesa_tabela_4_codigo": "",
            "grupo_natureza_despesa_tabela_4_descricao": "",
            "modalidade_aplicacao_tabela_5_codigo": "",
            "modalidade_aplicacao_tabela_5_descricao": "",
            "elemento_despesa_tabela_7_codigo": "",
            "elemento_despesa_tabela_7_descricao": "",
            "item_despesa_tabela_8_codigo": "",
            "item_despesa_tabela_8_descricao": "",
      "codigo_tributacao_nacional": "",
            "codigo_tributacao_nacional_descricao": "",
            "linha_fornecimento_compativel": "",
            "requer_validacao_humana": false,
            "motivo_validacao_humana": "",
            "itens_semelhantes_catmas": [
                {{
                    "codigo": "",
                    "descricao": "",
                    "situacao": "",
                    "grau_similaridade": 0.0
                }}
            ],
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
                    "correspondencia_exata_catmas": False,
                    "grau_similaridade_catmas": float(first_catmas.get("score", 0)) if first_catmas else 0.0,
                    "categoria_economica_tabela_3_codigo": (t3[0].get("codigo", "N/A") if t3 else "N/A"),
                    "categoria_economica_tabela_3_descricao": (t3[0].get("descricao", "N/A") if t3 else "N/A"),
                    "grupo_natureza_despesa_tabela_4_codigo": (t4[0].get("codigo", "N/A") if t4 else "N/A"),
                    "grupo_natureza_despesa_tabela_4_descricao": (t4[0].get("descricao", "N/A") if t4 else "N/A"),
                    "modalidade_aplicacao_tabela_5_codigo": (t5[0].get("codigo", "N/A") if t5 else "N/A"),
                    "modalidade_aplicacao_tabela_5_descricao": (t5[0].get("descricao", "N/A") if t5 else "N/A"),
                    "elemento_despesa_tabela_7_codigo": (t7[0].get("codigo", "N/A") if t7 else "N/A"),
                    "elemento_despesa_tabela_7_descricao": (t7[0].get("descricao", "N/A") if t7 else "N/A"),
                    "item_despesa_tabela_8_codigo": (t8[0].get("codigo", "N/A") if t8 else "N/A"),
                    "item_despesa_tabela_8_descricao": (t8[0].get("descricao", "N/A") if t8 else "N/A"),
                    "codigo_tributacao_nacional": trib[0].get("codigo", "N/A") if trib else "N/A",
                    "codigo_tributacao_nacional_descricao": trib[0].get("descricao", "N/A") if trib else "N/A",
                    "linha_fornecimento_compativel": "Nao avaliado no fallback.",
                    "requer_validacao_humana": True,
                    "motivo_validacao_humana": "Fallback deterministico sem confirmacao semantica completa.",
                    "itens_semelhantes_catmas": [
                        {
                            "codigo": item.get("codigo_material_servico", ""),
                            "descricao": item.get("item", ""),
                            "situacao": item.get("situacao_item", ""),
                            "grau_similaridade": float(item.get("score", 0)),
                        }
                        for item in catmas[:5]
                    ],
                    "justificativa": "Sugestão gerada por fallback determinístico por ausência/erro na chamada Gemini.",
                }
            ],
            "compatibilidade_cnae": "Análise preliminar sem IA: revisar CNAE e objeto para aderência final.",
            "alertas": ["Verificar manualmente compatibilidade tributária antes da emissão fiscal."],
        }
