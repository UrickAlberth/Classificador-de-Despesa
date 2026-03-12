from __future__ import annotations

import base64
import json
import os
import re
import urllib.request
from io import BytesIO
from typing import Iterable, List, Tuple

from fastapi import UploadFile
from pypdf import PdfReader


_TEXT_EXTENSIONS = {".txt", ".csv", ".md", ".json", ".xml", ".html", ".htm"}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_preserve_lines(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in (value or "").splitlines()]
    compact = "\n".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", compact).strip()


def _extract_text_from_pdf_bytes(content: bytes, max_pages: int = 20) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        parts: List[str] = []
        for page in reader.pages[:max_pages]:
            parts.append(page.extract_text() or "")
        return _normalize_preserve_lines("\n".join(parts))
    except Exception:
        return ""


def _extract_text_locally(filename: str, content_type: str, content: bytes) -> str:
    lower = filename.lower()

    if any(lower.endswith(ext) for ext in _TEXT_EXTENSIONS):
        try:
            return _normalize_preserve_lines(content.decode("utf-8", errors="ignore"))
        except Exception:
            return ""

    if lower.endswith(".pdf") or content_type == "application/pdf":
        return _extract_text_from_pdf_bytes(content)

    return ""


def _mistral_ocr(content: bytes, filename: str, content_type: str) -> str:
    api_key = os.getenv("MISTRAL_API_KEY", "").strip()
    model_name = os.getenv("MISTRAL_DOCUMENT_MODEL", "mistral-document-ai-2512").strip() or "mistral-document-ai-2512"
    endpoint = os.getenv("MISTRAL_OCR_ENDPOINT", "https://api.mistral.ai/v1/ocr").strip() or "https://api.mistral.ai/v1/ocr"

    if not api_key:
        return ""

    mime = content_type.strip() or "application/octet-stream"
    payload_document_type = "image_url" if mime.startswith("image/") else "document_url"
    b64 = base64.b64encode(content).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    payload = {
        "model": model_name,
        "document": {
            "type": payload_document_type,
            payload_document_type: data_url,
        },
    }

    request = urllib.request.Request(
        endpoint,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8", errors="ignore")
        data = json.loads(raw)
    except Exception:
        return ""

    if isinstance(data, dict):
        if isinstance(data.get("text"), str):
            return _normalize_preserve_lines(data["text"])

        pages = data.get("pages")
        if isinstance(pages, list):
            parts: List[str] = []
            for page in pages:
                if not isinstance(page, dict):
                    continue
                for key in ("markdown", "text", "content"):
                    value = page.get(key)
                    if isinstance(value, str) and value.strip():
                        parts.append(value)
                        break
            return _normalize_preserve_lines("\n".join(parts))

        outputs = data.get("outputs")
        if isinstance(outputs, list):
            parts = [str(item.get("text", "")) for item in outputs if isinstance(item, dict)]
            return _normalize_preserve_lines("\n".join(parts))

    return ""


def _prefer_ocr_for(content_type: str, filename: str) -> bool:
    lower = filename.lower()
    if content_type.startswith("image/"):
        return True
    return lower.endswith(".pdf")


def extract_text_from_uploaded_files(files: Iterable[UploadFile]) -> Tuple[str, List[str]]:
    extracted_chunks: List[str] = []
    metadata: List[str] = []

    for file in files:
        filename = file.filename or "arquivo-sem-nome"
        content_type = (file.content_type or "application/octet-stream").lower()
        content = file.file.read()

        local_text = _extract_text_locally(filename, content_type, content)
        ocr_text = ""
        if _prefer_ocr_for(content_type, filename):
            ocr_text = _mistral_ocr(content, filename, content_type)

        final_text = ocr_text or local_text
        if final_text:
            extracted_chunks.append(f"[{filename}] {final_text}")
            metadata.append(f"{filename}: texto extraido")
        else:
            metadata.append(f"{filename}: sem texto extraivel")

    return "\n\n".join(extracted_chunks), metadata


def infer_objeto_contratacao_from_text(text: str) -> str:
    normalized = _normalize_preserve_lines(text.replace("\r", "\n"))
    patterns = [
        r"(?im)^\s*objeto\s*(?:da\s*contratacao|do\s*contrato)?\s*[:\-]\s*(.+)$",
        r"(?im)^\s*objeto\s*[:\-]\s*(.+)$",
        r"(?im)^\s*descricao\s*do\s*objeto\s*[:\-]\s*(.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return _normalize_text(match.group(1))

    # Busca por secao numerada (ex.: "1. OBJETO") e captura o conteudo ate a proxima secao.
    section_match = re.search(
        r"(?ims)^\s*\d{0,2}\.?\s*objeto\b\s*[:\-]?\s*(.*?)\s*(?=^\s*\d{1,2}\.?\s*[A-ZÀ-Ü][^\n]{0,80}$|\Z)",
        normalized,
    )
    if section_match:
        raw_section = section_match.group(1).strip()
        section_lines = [line.strip(" -\t") for line in raw_section.splitlines() if len(line.strip()) >= 20]
        if section_lines:
            return _normalize_text(section_lines[0])

    # Busca por linhas com enunciados contratuais usuais de objeto.
    for line in normalized.splitlines():
        candidate = line.strip(" -\t")
        lower = candidate.lower()
        if len(candidate) < 30:
            continue
        if (
            "contratacao" in lower
            or "fornecimento" in lower
            or "prestacao" in lower
            or "servico" in lower
            or "aquisição" in lower
            or "aquisicao" in lower
        ):
            return _normalize_text(candidate)

    # Fallback: usa as primeiras linhas mais informativas do texto extraido.
    candidate_lines = [line.strip() for line in normalized.split("\n") if len(line.strip()) >= 25]
    if candidate_lines:
        return _normalize_text(candidate_lines[0])

    return ""
