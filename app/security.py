from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


CPF_PATTERN = re.compile(r"\b(\d{3})\.?\d{3}\.?\d{3}-?(\d{2})\b")


def mask_sensitive_data(value: str) -> str:
    if not value:
        return value

    def _cpf_repl(match: re.Match[str]) -> str:
        head = match.group(1)
        tail = match.group(2)
        return f"{head}.***.***-{tail}"

    return CPF_PATTERN.sub(_cpf_repl, value)


def build_audit_logger() -> logging.Logger:
    logger = logging.getLogger("tjmg_audit")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    # Emit audit events to stdout to avoid providers classifying them as errors.
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class AuditLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = build_audit_logger()

    async def dispatch(self, request: Request, call_next):
        started_at = datetime.now(timezone.utc)
        user_id = request.headers.get("x-user-id") or request.headers.get("x-forwarded-user") or "anonymous"
        forwarded_for = request.headers.get("x-forwarded-for", "")
        source_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else "unknown")

        response = await call_next(request)

        event = {
            "quando": started_at.isoformat(),
            "quem": user_id,
            "onde": source_ip,
            "o_que": f"{request.method} {request.url.path}",
            "status_code": response.status_code,
            "user_agent": mask_sensitive_data(request.headers.get("user-agent", "")),
        }
        self.logger.info(json.dumps(event, ensure_ascii=False))

        return response


class HSTSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
