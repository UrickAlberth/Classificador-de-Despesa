from __future__ import annotations

import hashlib
import os
from typing import Dict, List
from urllib.parse import parse_qs, urlencode, urlparse

import pandas as pd
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from openai import AzureOpenAI


DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1piA8VQoSYKq7vi-ILmS1my50TdxhaFXL/"
DEFAULT_INDEX_NAME = "catmas-index"
DEFAULT_TOP = 1000


def _build_google_sheets_csv_url(sheet_url: str) -> str:
    parsed = urlparse(sheet_url)
    path_parts = [part for part in parsed.path.split("/") if part]

    sheet_id = ""
    if "d" in path_parts:
        idx = path_parts.index("d")
        if idx + 1 < len(path_parts):
            sheet_id = path_parts[idx + 1]

    if not sheet_id:
        raise ValueError("Nao foi possivel identificar o ID da planilha Google Sheets.")

    query_params = parse_qs(parsed.query)
    gid = query_params.get("gid", [None])[0]

    export_params = {"format": "csv"}
    if gid:
        export_params["gid"] = gid

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?{urlencode(export_params)}"


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _make_doc_id(code: str, item: str, complemento: str) -> str:
    raw = f"{code}|{item}|{complemento}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _build_embedding_text(row: Dict[str, object]) -> str:
    chunks = [
        _normalize_text(row.get("Código Material ou Serviço", "")),
        _normalize_text(row.get("Descrição Material ou Serviço", "")),
        _normalize_text(row.get("Item", "")),
        _normalize_text(row.get("Complementação da Especificação", "")),
        _normalize_text(row.get("Linhas de Fornecimento", "")),
        _normalize_text(row.get("Natureza da Despesa", "")),
    ]
    return " | ".join(part for part in chunks if part)


def _load_catmas(sheet_url: str) -> pd.DataFrame:
    csv_url = _build_google_sheets_csv_url(sheet_url)
    df = pd.read_csv(csv_url, sep=None, engine="python")

    required_columns = [
        "Código Material ou Serviço",
        "Descrição Material ou Serviço",
        "Item",
        "Complementação da Especificação",
        "Situação do Item",
        "Linhas de Fornecimento",
        "Natureza da Despesa",
    ]
    for column in required_columns:
        if column not in df.columns:
            df[column] = ""

    return df.fillna("")


def _build_openai_client() -> AzureOpenAI:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21").strip() or "2024-10-21"

    if not endpoint or not api_key:
        raise ValueError("Defina AZURE_OPENAI_ENDPOINT e AZURE_OPENAI_API_KEY.")

    return AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint)


def _generate_embeddings(client: AzureOpenAI, deployment: str, texts: List[str], batch_size: int = 32) -> List[List[float]]:
    vectors: List[List[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(model=deployment, input=batch)
        for item in response.data:
            vectors.append(item.embedding)
    return vectors


def _get_search_clients() -> tuple[SearchIndexClient, SearchClient, str]:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "").strip()
    api_key = os.getenv("AZURE_SEARCH_API_KEY", "").strip()
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", DEFAULT_INDEX_NAME).strip() or DEFAULT_INDEX_NAME

    if not endpoint or not api_key:
        raise ValueError("Defina AZURE_SEARCH_ENDPOINT e AZURE_SEARCH_API_KEY.")

    credential = AzureKeyCredential(api_key)
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
    return index_client, search_client, index_name


def _ensure_index(index_client: SearchIndexClient, index_name: str, dimensions: int) -> None:
    existing_names = {item.name for item in index_client.list_indexes()}
    if index_name in existing_names:
        return

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True, sortable=True),
        SearchableField(name="codigo", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="descricao", type=SearchFieldDataType.String),
        SearchableField(name="item", type=SearchFieldDataType.String),
        SearchableField(name="complementacao", type=SearchFieldDataType.String),
        SearchableField(name="situacao", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="linhas_fornecimento", type=SearchFieldDataType.String),
        SearchableField(name="natureza_despesa", type=SearchFieldDataType.String),
        SearchableField(name="embedding_text", type=SearchFieldDataType.String),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=dimensions,
            vector_search_profile_name="catmas-vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="catmas-vector-profile",
                algorithm_configuration_name="catmas-hnsw",
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(
                name="catmas-hnsw",
            )
        ],
    )

    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
    index_client.create_index(index)


def _build_documents(df: pd.DataFrame, embeddings: List[List[float]]) -> List[Dict[str, object]]:
    docs: List[Dict[str, object]] = []
    records = df.to_dict(orient="records")
    for row, vector in zip(records, embeddings):
        codigo = _normalize_text(row.get("Código Material ou Serviço", ""))
        item = _normalize_text(row.get("Item", ""))
        complemento = _normalize_text(row.get("Complementação da Especificação", ""))
        descricao = _normalize_text(row.get("Descrição Material ou Serviço", ""))
        situacao = _normalize_text(row.get("Situação do Item", ""))
        linhas = _normalize_text(row.get("Linhas de Fornecimento", ""))
        natureza = _normalize_text(row.get("Natureza da Despesa", ""))
        embedding_text = _build_embedding_text(row)

        docs.append(
            {
                "id": _make_doc_id(codigo, item, complemento),
                "codigo": codigo,
                "descricao": descricao,
                "item": item,
                "complementacao": complemento,
                "situacao": situacao,
                "linhas_fornecimento": linhas,
                "natureza_despesa": natureza,
                "embedding_text": embedding_text,
                "embedding": vector,
            }
        )
    return docs


def _upload_in_batches(search_client: SearchClient, documents: List[Dict[str, object]], batch_size: int = DEFAULT_TOP) -> int:
    total_uploaded = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        result = search_client.upload_documents(documents=batch)
        total_uploaded += sum(1 for item in result if item.succeeded)
    return total_uploaded


def main() -> None:
    sheet_url = os.getenv("CATMAS_GOOGLE_SHEETS_URL", DEFAULT_SHEET_URL).strip() or DEFAULT_SHEET_URL
    embedding_deployment = (
        os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "").strip()
        or os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
    )
    if not embedding_deployment:
        raise ValueError("Defina AZURE_OPENAI_EMBEDDING_DEPLOYMENT.")

    print("[1/5] Carregando base CATMAS do Google Sheets...")
    catmas_df = _load_catmas(sheet_url)
    if catmas_df.empty:
        print("Base CATMAS vazia. Nada para indexar.")
        return

    print("[2/5] Gerando textos para embeddings...")
    texts = [_build_embedding_text(row) for row in catmas_df.to_dict(orient="records")]

    print("[3/5] Gerando embeddings no Azure OpenAI...")
    aoai_client = _build_openai_client()
    embeddings = _generate_embeddings(aoai_client, embedding_deployment, texts)
    if not embeddings:
        raise RuntimeError("Nao foi possivel gerar embeddings.")

    print("[4/5] Criando/validando indice no Azure AI Search...")
    index_client, search_client, index_name = _get_search_clients()
    _ensure_index(index_client, index_name, dimensions=len(embeddings[0]))

    print("[5/5] Enviando documentos vetorizados para o indice...")
    documents = _build_documents(catmas_df, embeddings)
    uploaded = _upload_in_batches(search_client, documents)

    print(f"Concluido. Documentos enviados com sucesso: {uploaded}")


if __name__ == "__main__":
    main()
