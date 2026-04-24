"""castor.rcan3.rrf_client — async client for Robot Registry Foundation v2.

Endpoints used:
- POST /v2/robots/register
- GET  /v2/robots/{rrn}
- POST /v2/compliance/{artifact}
    where artifact ∈ {fria, safety-benchmark, ifu, incident-report, eu-register}
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("OpenCastor.RrfClient")

_COMPLIANCE_ARTIFACTS = {
    "fria",
    "safety-benchmark",
    "ifu",
    "incident-report",
    "eu-register",
}


class RrfError(RuntimeError):
    """Raised when an RRF call returns a non-2xx response."""


class RrfClient:
    """Async RRF v2 client. Use as an ``async with`` context manager."""

    def __init__(
        self,
        base_url: str = "https://rcan.dev",
        timeout: float = 10.0,
        auth_token: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._auth_token = auth_token
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> RrfClient:
        headers = {"content-type": "application/json"}
        if self._auth_token:
            headers["authorization"] = f"Bearer {self._auth_token}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            headers=headers,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _require(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("RrfClient must be used as `async with`")
        return self._client

    async def register(self, signed_body: dict[str, Any]) -> dict[str, Any]:
        resp = await self._require().post("/v2/robots/register", json=signed_body)
        if resp.status_code >= 400:
            logger.warning("RRF register failed: %d %s", resp.status_code, resp.text)
            raise RrfError(f"{resp.status_code}: {resp.text}")
        result = resp.json()
        logger.info("RRF register: %s → rrn=%s", self._base_url, result.get("rrn"))
        return result

    async def get_robot(self, rrn: str) -> dict[str, Any]:
        resp = await self._require().get(f"/v2/robots/{rrn}")
        if resp.status_code >= 400:
            raise RrfError(f"{resp.status_code}: {resp.text}")
        return resp.json()

    async def submit_compliance(self, artifact: str, signed_body: dict[str, Any]) -> dict[str, Any]:
        if artifact not in _COMPLIANCE_ARTIFACTS:
            raise ValueError(
                f"unknown compliance artifact {artifact!r}; must be one of "
                f"{sorted(_COMPLIANCE_ARTIFACTS)}"
            )
        resp = await self._require().post(f"/v2/compliance/{artifact}", json=signed_body)
        if resp.status_code >= 400:
            logger.warning("RRF compliance submit failed: %d %s", resp.status_code, resp.text)
            raise RrfError(f"{resp.status_code}: {resp.text}")
        result = resp.json()
        logger.info("RRF compliance submit: artifact=%s → %s", artifact, result)
        return result
