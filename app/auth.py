from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


class OIDCValidator:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_AUTH", "false").strip().lower() == "true"
        self.issuer = os.getenv("OIDC_ISSUER_URL", "").strip().rstrip("/")
        self.audience = os.getenv("OIDC_AUDIENCE", "").strip() or os.getenv("OIDC_CLIENT_ID", "").strip()
        self.algorithms = ["RS256"]
        self._jwks_client = None

        if self.enabled and self.issuer:
            jwks_url = f"{self.issuer}/protocol/openid-connect/certs"
            self._jwks_client = jwt.PyJWKClient(jwks_url)

    def _extract_token(self, request: Request) -> Optional[str]:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        return auth_header.replace("Bearer ", "", 1).strip() or None

    def validate_request(self, request: Request) -> dict:
        if not self.enabled:
            return {}

        if not self.issuer or not self.audience or not self._jwks_client:
            raise HTTPException(status_code=500, detail="OIDC mal configurado no servidor.")

        token = self._extract_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="Token Bearer obrigatorio.")

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=self.algorithms,
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "iss", "aud"]},
            )
            return payload
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Token invalido: {exc}") from exc


class OIDCAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exempt_paths: set[str] | None = None):
        super().__init__(app)
        self.validator = OIDCValidator()
        self.exempt_paths = exempt_paths or {"/", "/health"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path not in self.exempt_paths:
            self.validator.validate_request(request)
        return await call_next(request)
