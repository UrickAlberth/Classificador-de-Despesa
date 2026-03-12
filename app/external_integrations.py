from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Dict, List


def _normalize_digits(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isdigit())


def _http_get_json(url: str, timeout: int = 20):
    request = urllib.request.Request(url, headers={"User-Agent": "tjmg-classificador-ia/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def consultar_cnae_ibge(termo: str, limite: int = 5) -> List[Dict[str, str]]:
    encoded = urllib.parse.quote(termo.strip())
    base_url = "https://servicodados.ibge.gov.br/api/v2/cnae/subclasses"
    url = f"{base_url}?busca={encoded}"
    try:
        data = _http_get_json(url)
    except Exception:
        return []

    resultados: List[Dict[str, str]] = []
    for item in data[:limite]:
        resultados.append(
            {
                "id": str(item.get("id", "")),
                "descricao": str(item.get("descricao", "")),
                "grupo": str(item.get("grupo", {}).get("descricao", "")),
            }
        )
    return resultados


def consultar_codigo_tributacao_nacional(termo: str) -> List[Dict[str, str]]:
    base_url = os.getenv("NFSE_NACIONAL_BASE_URL", "").strip()
    if not base_url:
        return []

    url = f"{base_url.rstrip('/')}/search?query={urllib.parse.quote(termo.strip())}"
    try:
        data = _http_get_json(url)
    except Exception:
        return []

    if isinstance(data, list):
        return [{"codigo": str(item.get("codigo", "")), "descricao": str(item.get("descricao", ""))} for item in data[:10]]
    return []


def validar_cnae_e_tributacao(objeto_contratacao: str, cnae_empresa: str | None = None) -> Dict[str, object]:
    cnaes_ibge = consultar_cnae_ibge(objeto_contratacao)
    codigos_tributacao = consultar_codigo_tributacao_nacional(objeto_contratacao)

    compatibilidade = "CNAE da empresa nao informado."
    if cnae_empresa:
        cnae_empresa_clean = _normalize_digits(cnae_empresa)
        if not cnaes_ibge:
            compatibilidade = "Sem retorno IBGE no momento para comparacao automatica."
        else:
            compatibilidade = "Potencial incompatibilidade entre CNAE informado e objeto contratado."
            for item in cnaes_ibge:
                suggested = _normalize_digits(str(item.get("id", "")))
                if not suggested or not cnae_empresa_clean:
                    continue
                if cnae_empresa_clean.startswith(suggested[:5]) or suggested.startswith(cnae_empresa_clean[:5]):
                    compatibilidade = "Compativel (correspondencia aproximada entre CNAE da empresa e CNAE sugerido pelo IBGE)."
                    break

    return {
        "cnaes_ibge": cnaes_ibge,
        "codigos_tributacao_nacional": codigos_tributacao,
        "compatibilidade_cnae": compatibilidade,
    }
