from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from openai import AzureOpenAI, OpenAI
from pypdf import PdfReader


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_only.lower()).strip("_")


def _tokenize(value: str) -> List[str]:
    cleaned = re.sub(r"[^a-zA-ZÀ-ÿ0-9 ]+", " ", value.lower())
    return [token for token in cleaned.split() if len(token) > 2]


def _score_text(query: str, target: str) -> float:
    query_tokens = set(_tokenize(query))
    target_tokens = set(_tokenize(target))
    if not query_tokens or not target_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(target_tokens))
    return overlap / max(len(query_tokens), 1)


def _normalize_digits(value: str) -> str:
    return re.sub(r"\D+", "", str(value))


def _split_code_description(row_values: List[str]) -> tuple[str, str]:
    non_empty = [_normalize_spaces(value) for value in row_values if _normalize_spaces(value)]
    if not non_empty:
        return "N/A", "N/A"

    code_candidate = non_empty[0]
    description_parts = non_empty[1:]

    if not re.search(r"\d", code_candidate):
        tokens = code_candidate.split(" ", 1)
        if len(tokens) == 2 and re.search(r"\d", tokens[0]):
            code_candidate, first_description = tokens[0], tokens[1]
            description_parts = [first_description, *description_parts]

    if not description_parts:
        return code_candidate, code_candidate

    return code_candidate, _normalize_spaces(" ".join(description_parts))


def _detect_query_kind(query: str) -> str | None:
    query_lower = query.lower()
    if any(token in query_lower for token in ["serviço", "servico", "prestação", "prestacao"]):
        return "SERVICO"
    if "material" in query_lower:
        return "MATERIAL"
    return None


@dataclass
class OfficialTables:
    tabela_3: pd.DataFrame
    tabela_4: pd.DataFrame
    tabela_5: pd.DataFrame
    tabela_7: pd.DataFrame
    tabela_8: pd.DataFrame


class CatmasVectorStore:
    def __init__(
        self,
        db_path: Path,
        api_key: str,
        embedding_model: str,
        provider: str = "openai",
        azure_endpoint: str = "",
        azure_api_version: str = "2024-10-21",
    ):
        self.db_path = db_path
        self.embedding_model = embedding_model
        self.provider = provider
        self.enabled = bool(api_key and (provider != "azure" or azure_endpoint))
        if self.enabled and provider == "azure":
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=azure_api_version,
                azure_endpoint=azure_endpoint,
            )
        elif self.enabled:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
        if self.enabled:
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                self._init_db()
            except OSError as exc:
                warnings.warn(
                    f"Desativando busca vetorial CATMAS: caminho nao gravavel em runtime ({self.db_path}): {exc}",
                    RuntimeWarning,
                )
                self.enabled = False
                self.client = None

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS catmas_embeddings (
                    row_key TEXT PRIMARY KEY,
                    text_hash TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    tipo_item TEXT,
                    situacao_item TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_catmas_tipo ON catmas_embeddings(tipo_item)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_catmas_situacao ON catmas_embeddings(situacao_item)"
            )
            conn.commit()

    def _embed_texts(self, texts: List[str], batch_size: int = 96) -> List[List[float]]:
        if not self.client:
            return []

        vectors: List[List[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            try:
                response = self.client.embeddings.create(model=self.embedding_model, input=batch)
            except Exception:
                return []
            for item in response.data:
                vec = np.asarray(item.embedding, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                vectors.append(vec.tolist())
        return vectors

    def sync(self, records: List[Dict[str, str]]) -> None:
        if not self.enabled or not records:
            return

        with self._connect() as conn:
            existing = {
                key: text_hash
                for key, text_hash in conn.execute("SELECT row_key, text_hash FROM catmas_embeddings")
            }

            incoming_keys = {record["row_key"] for record in records}
            stale_keys = [key for key in existing.keys() if key not in incoming_keys]
            if stale_keys:
                conn.executemany("DELETE FROM catmas_embeddings WHERE row_key = ?", [(key,) for key in stale_keys])

            to_upsert: List[Dict[str, str]] = []
            for record in records:
                if existing.get(record["row_key"]) != record["text_hash"]:
                    to_upsert.append(record)

            if not to_upsert:
                return

            vectors = self._embed_texts([record["embedding_text"] for record in to_upsert])
            rows = []
            for record, vector in zip(to_upsert, vectors):
                rows.append(
                    (
                        record["row_key"],
                        record["text_hash"],
                        json.dumps(vector, ensure_ascii=False),
                        record["tipo_item"],
                        record["situacao_item"],
                    )
                )

            conn.executemany(
                """
                INSERT INTO catmas_embeddings (row_key, text_hash, embedding, tipo_item, situacao_item)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(row_key) DO UPDATE SET
                    text_hash=excluded.text_hash,
                    embedding=excluded.embedding,
                    tipo_item=excluded.tipo_item,
                    situacao_item=excluded.situacao_item
                """,
                rows,
            )
            conn.commit()

    def search(self, query: str, only_active: bool, query_kind: str | None, max_results: int) -> List[Tuple[str, float]]:
        if not self.enabled or not self.client:
            return []

        try:
            query_response = self.client.embeddings.create(model=self.embedding_model, input=[query])
        except Exception:
            return []
        query_vector = np.asarray(query_response.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(query_vector)
        if norm == 0:
            return []
        query_vector = query_vector / norm

        where_clauses = []
        params: List[str] = []
        if only_active:
            where_clauses.append("UPPER(situacao_item) LIKE ?")
            params.append("%ATIVO%")
        if query_kind:
            where_clauses.append("tipo_item = ?")
            params.append(query_kind)

        sql = "SELECT row_key, embedding FROM catmas_embeddings"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        scored: List[Tuple[str, float]] = []
        with self._connect() as conn:
            for row_key, embedding_json in conn.execute(sql, params):
                embedding = np.asarray(json.loads(embedding_json), dtype=np.float32)
                score = float(np.dot(query_vector, embedding))
                scored.append((row_key, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:max_results]


class KnowledgeRepository:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        provider = os.getenv("AI_PROVIDER", "").strip().lower()
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
        azure_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not provider:
            provider = "azure" if azure_endpoint and azure_key else "openai"

        vector_api_key = azure_key if provider == "azure" else openai_key
        if not vector_api_key:
            vector_api_key = openai_key or azure_key

        embedding_model = (
            os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "").strip()
            if provider == "azure"
            else ""
        ) or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large").strip() or "text-embedding-3-large"

        self.catmas_df = self._load_catmas()
        self.catmas_by_row_key = {
            str(row.get("_row_key", "")): row
            for _, row in self.catmas_df.iterrows()
            if str(row.get("_row_key", ""))
        }
        self.vector_store = CatmasVectorStore(
            db_path=self._resolve_vector_db_path(),
            api_key=vector_api_key,
            embedding_model=embedding_model,
            provider=provider,
            azure_endpoint=azure_endpoint,
            azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21").strip() or "2024-10-21",
        )
        self.vector_search_enabled = os.getenv("ENABLE_CATMAS_VECTOR_SEARCH", "true").lower() == "true"
        self.vector_sync_on_startup = self._resolve_vector_sync_default()
        if self.vector_sync_on_startup:
            self._sync_catmas_vectors()
        self.tables = self._load_budget_tables()
        self.process_docs_text = self._load_process_documents_text()

    def _resolve_vector_db_path(self) -> Path:
        configured = os.getenv("CATMAS_VECTOR_DB_PATH", "").strip()
        if configured:
            return Path(configured)

        # Em Vercel, /var/task eh somente leitura; usar /tmp evita falha no cold start.
        running_on_vercel = bool(os.getenv("VERCEL", "").strip())
        if running_on_vercel:
            return Path("/tmp") / "data" / "catmas_vectors.db"

        # Em App Service, HOME aponta para armazenamento persistente compartilhado.
        home_dir = os.getenv("HOME", "").strip()
        if home_dir:
            return Path(home_dir) / "data" / "catmas_vectors.db"

        return self.base_dir / "data" / "catmas_vectors.db"

    def _resolve_vector_sync_default(self) -> bool:
        raw = os.getenv("ENABLE_CATMAS_VECTOR_SYNC_ON_STARTUP", "").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False

        # Evita startup caro em App Service quando nao houver configuracao explicita.
        running_on_azure = bool(os.getenv("WEBSITE_SITE_NAME", "").strip())
        return not running_on_azure

    def _make_row_key(self, row: pd.Series) -> str:
        raw = "|".join(
            [
                _normalize_spaces(str(row.get("Código Material ou Serviço", ""))),
                _normalize_spaces(str(row.get("Descrição Material ou Serviço", ""))),
                _normalize_spaces(str(row.get("Item", ""))),
                _normalize_spaces(str(row.get("Complementação da Especificação", ""))),
                _normalize_spaces(str(row.get("Natureza da Despesa", ""))),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()

    def _build_embedding_text(self, row: pd.Series) -> str:
        return _normalize_spaces(
            " ".join(
                [
                    str(row.get("Descrição Material ou Serviço", "")),
                    str(row.get("Item", "")),
                    str(row.get("Complementação da Especificação", "")),
                    str(row.get("Linhas de Fornecimento", "")),
                    str(row.get("Natureza da Despesa", "")),
                ]
            )
        )

    def _sync_catmas_vectors(self) -> None:
        if self.catmas_df.empty or not self.vector_store.enabled or not self.vector_search_enabled:
            return

        records: List[Dict[str, str]] = []
        for _, row in self.catmas_df.iterrows():
            row_key = str(row.get("_row_key", ""))
            text = self._build_embedding_text(row)
            text_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
            records.append(
                {
                    "row_key": row_key,
                    "embedding_text": text,
                    "text_hash": text_hash,
                    "tipo_item": str(row.get("_tipo_item", "")),
                    "situacao_item": str(row.get("Situação do Item", "")),
                }
            )

        try:
            self.vector_store.sync(records)
        except Exception as exc:
            warnings.warn(f"Nao foi possivel sincronizar vetores CATMAS: {exc}", RuntimeWarning)

    def _load_catmas(self) -> pd.DataFrame:
        default_sheet_url = (
            "https://docs.google.com/spreadsheets/d/1piA8VQoSYKq7vi-ILmS1my50TdxhaFXL/"
        )
        sheet_url = os.getenv("CATMAS_GOOGLE_SHEETS_URL", default_sheet_url).strip()
        csv_path = self.base_dir / "Retrato do Catmas - Fevereiro25 - v3.xlsx - Geral.csv"
        df: pd.DataFrame | None = None
        load_error: Exception | None = None

        if sheet_url:
            try:
                df = pd.read_csv(self._build_google_sheets_csv_url(sheet_url), sep=None, engine="python")
            except Exception as exc:
                load_error = exc

        if df is None:
            if not csv_path.exists():
                warning_msg = "CATMAS indisponivel: usando base vazia temporariamente."
                if load_error is not None:
                    warning_msg += f" Erro remoto: {load_error}"
                warnings.warn(warning_msg, RuntimeWarning)
                return self._empty_catmas_df()
            df = pd.read_csv(csv_path, sep=None, engine="python")

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

        df.columns = [str(column).strip() for column in df.columns]
        df = df.fillna("")
        df["_status"] = df["Situação do Item"].astype(str).str.upper()
        df["_search_text"] = (
            df["Descrição Material ou Serviço"].astype(str)
            + " "
            + df["Item"].astype(str)
            + " "
            + df["Complementação da Especificação"].astype(str)
        ).str.lower()
        df["_codigo_limpo"] = df["Código Material ou Serviço"].astype(str).apply(_normalize_digits)

        tipo_col = (
            df["Descrição Material ou Serviço"].astype(str)
            + " "
            + df["Item"].astype(str)
            + " "
            + df["Complementação da Especificação"].astype(str)
        ).str.lower()
        df["_tipo_item"] = ""
        df.loc[tipo_col.str.contains(r"servi[çc]o|prestac", regex=True, na=False), "_tipo_item"] = "SERVICO"
        df.loc[(df["_tipo_item"] == "") & tipo_col.str.contains("material", regex=False, na=False), "_tipo_item"] = "MATERIAL"
        df["_row_key"] = df.apply(self._make_row_key, axis=1)
        return df

    def _empty_catmas_df(self) -> pd.DataFrame:
        df = pd.DataFrame(
            columns=[
                "Código Material ou Serviço",
                "Descrição Material ou Serviço",
                "Item",
                "Complementação da Especificação",
                "Situação do Item",
                "Linhas de Fornecimento",
                "Natureza da Despesa",
            ]
        )
        df["_status"] = ""
        df["_search_text"] = ""
        df["_codigo_limpo"] = ""
        df["_tipo_item"] = ""
        df["_row_key"] = ""
        return df

    def _build_google_sheets_csv_url(self, sheet_url: str) -> str:
        if "format=csv" in sheet_url and "/export" in sheet_url:
            return sheet_url

        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", sheet_url)
        if not match:
            return sheet_url

        doc_id = match.group(1)
        parsed = urlparse(sheet_url)
        query = parse_qs(parsed.query)

        gid = query.get("gid", [""])[0]
        if not gid and parsed.fragment.startswith("gid="):
            gid = parsed.fragment.split("=", 1)[1]

        params = {"format": "csv"}
        if gid:
            params["gid"] = gid

        return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?{urlencode(params)}"

    def _prepare_sheet(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        header_row = 0
        for index in range(min(len(raw_df), 10)):
            row_values = [str(value).upper() for value in raw_df.iloc[index].tolist()]
            if any("CD_" in value for value in row_values):
                header_row = index
                break
        df = raw_df.iloc[header_row + 1 :].copy()
        df.columns = [str(column).strip() for column in raw_df.iloc[header_row].tolist()]
        df = df.dropna(how="all")
        return df.fillna("")

    def _load_budget_tables(self) -> OfficialTables:
        xlsx_path = self.base_dir / "[03]-25502051_Anexo_Tabela_orcamentaria.xlsx"
        tabela_3 = self._prepare_sheet(pd.read_excel(xlsx_path, sheet_name="3", header=None))
        tabela_4 = self._prepare_sheet(pd.read_excel(xlsx_path, sheet_name="4", header=None))
        tabela_5 = self._prepare_sheet(pd.read_excel(xlsx_path, sheet_name="5", header=None))
        tabela_7 = self._prepare_sheet(pd.read_excel(xlsx_path, sheet_name="7", header=None))
        tabela_8 = self._prepare_sheet(pd.read_excel(xlsx_path, sheet_name="8", header=None))
        return OfficialTables(
            tabela_3=tabela_3,
            tabela_4=tabela_4,
            tabela_5=tabela_5,
            tabela_7=tabela_7,
            tabela_8=tabela_8,
        )

    def _load_process_documents_text(self) -> str:
        chunks: List[str] = []

        html_path = self.base_dir / "[01]-25481830_Oficio_9692.html"
        if html_path.exists():
            soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
            chunks.append(_normalize_spaces(soup.get_text(" ", strip=True)))

        for pdf_path in sorted(self.base_dir.glob("*.pdf")):
            if "Tabela_orcamentaria" in pdf_path.name:
                continue
            try:
                reader = PdfReader(str(pdf_path))
                text_parts: List[str] = []
                for page in reader.pages[:4]:
                    text_parts.append(page.extract_text() or "")
                chunks.append(f"[{pdf_path.name}] {_normalize_spaces(' '.join(text_parts))}")
            except Exception:
                continue

        return "\n\n".join(chunks)

    def _row_to_candidate(self, row: pd.Series, score: float) -> Dict[str, str]:
        row_kind = str(row.get("_tipo_item", ""))
        return {
            "codigo_material_servico": str(row.get("Código Material ou Serviço", "")).strip(),
            "descricao_material_servico": str(row.get("Descrição Material ou Serviço", "")).strip(),
            "item": str(row.get("Item", "")).strip(),
            "tipo_item": row_kind,
            "situacao_item": str(row.get("Situação do Item", "")).strip(),
            "linhas_fornecimento": str(row.get("Linhas de Fornecimento", "")).strip(),
            "natureza_despesa": str(row.get("Natureza da Despesa", "")).strip(),
            "score": f"{score:.4f}",
        }

    def _score_catmas_candidate(
        self,
        query: str,
        row: pd.Series,
        query_digits: str,
        query_kind: str | None,
    ) -> float:
        descricao_ms = _normalize_spaces(str(row.get("Descrição Material ou Serviço", "")))
        item = _normalize_spaces(str(row.get("Item", "")))
        complemento = _normalize_spaces(str(row.get("Complementação da Especificação", "")))
        row_code = _normalize_digits(row.get("Código Material ou Serviço", ""))
        row_kind = str(row.get("_tipo_item", ""))

        # Priorizacao forte da descricao do material/servico para aderencia ao objeto.
        desc_score = _score_text(query, descricao_ms)
        item_score = _score_text(query, item)
        comp_score = _score_text(query, complemento)
        combined_score = (desc_score * 0.65) + (item_score * 0.25) + (comp_score * 0.10)

        query_tokens = _tokenize(query)
        target_text = f"{descricao_ms} {item} {complemento}".lower()
        if query_tokens:
            covered = sum(1 for token in query_tokens if token in target_text)
            combined_score += (covered / len(query_tokens)) * 0.35

        if query_digits and row_code:
            if row_code == query_digits:
                combined_score += 2.0
            elif row_code.startswith(query_digits) or query_digits.startswith(row_code):
                combined_score += 1.2
            elif query_digits in row_code:
                combined_score += 0.8

        if query_kind and row_kind == query_kind:
            combined_score += 0.2

        return combined_score

    def get_catmas_by_code(self, code: str, only_active: bool = True) -> Dict[str, str] | None:
        clean_code = _normalize_digits(code)
        if not clean_code:
            return None

        df = self.catmas_df
        if only_active:
            df = df[df["_status"].str.contains("ATIVO", na=False)]

        exact = df[df["_codigo_limpo"] == clean_code]
        if exact.empty:
            return None

        row = exact.iloc[0]
        return self._row_to_candidate(row, score=1.0)

    def search_catmas(self, query: str, max_results: int = 15, only_active: bool = True) -> List[Dict[str, str]]:
        candidates: List[Dict[str, str]] = []
        used_row_keys: set[str] = set()
        token_list = _tokenize(query)[:8]
        text_tokens = [token for token in token_list if not token.isdigit()]
        query_digits = _normalize_digits(query)
        query_kind = _detect_query_kind(query)
        code_locked = False

        df = self.catmas_df
        if only_active:
            df = df[df["_status"].str.contains("ATIVO", na=False)]

        if query_kind:
            kind_df = df[df["_tipo_item"] == query_kind]
            if not kind_df.empty:
                df = kind_df

        if query_digits and len(query_digits) >= 4:
            exact = df[df["_codigo_limpo"] == query_digits]
            if not exact.empty:
                df = exact
                code_locked = True
            else:
                partial = df[df["_codigo_limpo"].str.contains(query_digits, regex=False, na=False)]
                if not partial.empty:
                    df = partial

        base_df = df.copy()

        if text_tokens and not code_locked:
            mask = df["_search_text"].str.contains(text_tokens[0], regex=False, na=False)
            for token in text_tokens[1:]:
                mask = mask | df["_search_text"].str.contains(token, regex=False, na=False)
            df = df[mask]

        if df.empty:
            df = base_df

        if df.empty:
            return []

        if self.vector_search_enabled and self.vector_store.enabled and not code_locked:
            try:
                allowed_row_keys = set(df["_row_key"].astype(str).tolist())
                for row_key, similarity in self.vector_store.search(
                    query=query,
                    only_active=only_active,
                    query_kind=query_kind,
                    max_results=max_results * 3,
                ):
                    if row_key not in allowed_row_keys:
                        continue
                    row = self.catmas_by_row_key.get(row_key)
                    if row is None:
                        continue
                    vector_score = max(0.0, (similarity + 1.0) / 2.0)
                    lexical_score = self._score_catmas_candidate(query, row, query_digits, query_kind)
                    score = lexical_score + (vector_score * 0.8)
                    candidates.append(self._row_to_candidate(row, score=score))
                    used_row_keys.add(row_key)
            except Exception as exc:
                warnings.warn(f"Falha na busca vetorial CATMAS, usando fallback textual: {exc}", RuntimeWarning)

        for _, row in df.head(5000).iterrows():
            row_key = str(row.get("_row_key", ""))
            if row_key and row_key in used_row_keys:
                continue
            score = self._score_catmas_candidate(query, row, query_digits, query_kind)

            if score <= 0 and not query_digits:
                continue
            candidates.append(self._row_to_candidate(row, score=score))
            if row_key:
                used_row_keys.add(row_key)

        if not candidates:
            for _, row in base_df.head(1200).iterrows():
                score = self._score_catmas_candidate(query, row, query_digits, query_kind)
                candidates.append(self._row_to_candidate(row, score=score))

        candidates.sort(key=lambda item: float(item["score"]), reverse=True)
        return candidates[:max_results]

    def rank_table_entries(self, table_df: pd.DataFrame, query: str, max_results: int = 8) -> List[Dict[str, str]]:
        normalized_columns = {
            _normalize_label(column): str(column)
            for column in table_df.columns
        }
        interpretacao_col = next(
            (
                original
                for normalized, original in normalized_columns.items()
                if "interpret" in normalized
            ),
            "",
        )
        item_codigo_col = normalized_columns.get("cd_item_despesa", "")
        item_descricao_col = normalized_columns.get("denominacao_item_despesa", "")
        elemento_codigo_col = normalized_columns.get("cd_elemento_despesa", "")

        query_tokens = _tokenize(query)
        entries: List[Dict[str, str]] = []
        for _, row in table_df.iterrows():
            values = [str(v) for v in row.tolist()]
            joined = _normalize_spaces(" ".join(values))
            score = _score_text(query, joined)

            interpretacao = _normalize_spaces(str(row.get(interpretacao_col, ""))) if interpretacao_col else ""
            item_descricao = _normalize_spaces(str(row.get(item_descricao_col, ""))) if item_descricao_col else ""
            item_codigo = _normalize_spaces(str(row.get(item_codigo_col, ""))) if item_codigo_col else ""
            elemento_codigo = _normalize_spaces(str(row.get(elemento_codigo_col, ""))) if elemento_codigo_col else ""

            if interpretacao:
                interpretacao_score = _score_text(query, interpretacao)
                item_desc_score = _score_text(query, item_descricao)
                score = max(score, (interpretacao_score * 0.60) + (item_desc_score * 0.25) + (score * 0.15))

                if query_tokens:
                    lowered = interpretacao.lower()
                    covered = sum(1 for token in query_tokens if token in lowered)
                    score += (covered / max(len(query_tokens), 1)) * 0.25

            if score <= 0:
                continue

            codigo, descricao = _split_code_description(values)
            if item_codigo:
                codigo = item_codigo
            if item_descricao:
                descricao = item_descricao

            entries.append(
                {
                    "valor": joined,
                    "codigo": codigo,
                    "descricao": descricao,
                    "cd_elemento_despesa": elemento_codigo,
                    "cd_item_despesa": item_codigo,
                    "denominacao_item_despesa": item_descricao,
                    "interpretacao": interpretacao,
                    "score": f"{score:.4f}",
                }
            )

        entries.sort(key=lambda item: float(item["score"]), reverse=True)
        return entries[:max_results]
