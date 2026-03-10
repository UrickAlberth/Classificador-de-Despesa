from __future__ import annotations

import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlencode, urlparse

import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


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


class KnowledgeRepository:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.catmas_df = self._load_catmas()
        self.tables = self._load_budget_tables()
        self.process_docs_text = self._load_process_documents_text()

    def _load_catmas(self) -> pd.DataFrame:
        default_sheet_url = (
            "https://docs.google.com/spreadsheets/d/1piA8VQoSYKq7vi-ILmS1my50TdxhaFXL/edit?gid=1011457846#gid=1011457846"
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

        for _, row in df.head(5000).iterrows():
            description = _normalize_spaces(
                f"{row.get('Descrição Material ou Serviço', '')} {row.get('Item', '')} {row.get('Complementação da Especificação', '')}"
            )
            score = _score_text(query, description)
            row_code = _normalize_digits(row.get("Código Material ou Serviço", ""))
            row_kind = str(row.get("_tipo_item", ""))

            if query_digits and row_code:
                if row_code == query_digits:
                    score += 2.0
                elif row_code.startswith(query_digits) or query_digits.startswith(row_code):
                    score += 1.2
                elif query_digits in row_code:
                    score += 0.8

            if query_kind and row_kind == query_kind:
                score += 0.25

            if score <= 0 and not query_digits:
                continue
            candidates.append(self._row_to_candidate(row, score=score))

        if not candidates:
            for _, row in base_df.head(1200).iterrows():
                description = _normalize_spaces(
                    f"{row.get('Descrição Material ou Serviço', '')} {row.get('Item', '')} {row.get('Complementação da Especificação', '')}"
                )
                score = _score_text(query, description)
                candidates.append(self._row_to_candidate(row, score=score))

        candidates.sort(key=lambda item: float(item["score"]), reverse=True)
        return candidates[:max_results]

    def rank_table_entries(self, table_df: pd.DataFrame, query: str, max_results: int = 8) -> List[Dict[str, str]]:
        entries: List[Dict[str, str]] = []
        for _, row in table_df.iterrows():
            joined = _normalize_spaces(" ".join(str(v) for v in row.tolist()))
            score = _score_text(query, joined)
            if score <= 0:
                continue
            entries.append({"valor": joined, "score": f"{score:.4f}"})

        entries.sort(key=lambda item: float(item["score"]), reverse=True)
        return entries[:max_results]
