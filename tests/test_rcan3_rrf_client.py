"""Tests for castor.rcan3.rrf_client — RRF v2 client."""

from __future__ import annotations

import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
@respx.mock
async def test_register_posts_signed_body_and_returns_rrn():
    from castor.rcan3.rrf_client import RrfClient

    route = respx.post("https://rcan.dev/v2/robots/register").mock(
        return_value=Response(
            201,
            json={
                "rrn": "RRN-000000000001",
                "rcan_uri": "rcan://rcan.dev/craigm26/so-arm101/1-0-0/bob-001",
            },
        )
    )

    async with RrfClient(base_url="https://rcan.dev") as c:
        out = await c.register({"signature": {"alg": "hybrid-ed25519-mldsa65"}, "data": {}})

    assert route.called
    assert out["rrn"] == "RRN-000000000001"


@pytest.mark.asyncio
@respx.mock
async def test_get_robot_returns_record():
    from castor.rcan3.rrf_client import RrfClient

    respx.get("https://rcan.dev/v2/robots/RRN-000000000001").mock(
        return_value=Response(200, json={"rrn": "RRN-000000000001", "robot_name": "bob"})
    )
    async with RrfClient(base_url="https://rcan.dev") as c:
        out = await c.get_robot("RRN-000000000001")
    assert out["robot_name"] == "bob"


@pytest.mark.asyncio
@respx.mock
async def test_register_raises_on_http_error():
    from castor.rcan3.rrf_client import RrfClient, RrfError

    respx.post("https://rcan.dev/v2/robots/register").mock(
        return_value=Response(400, json={"error": "invalid signature"})
    )
    async with RrfClient(base_url="https://rcan.dev") as c:
        with pytest.raises(RrfError, match="400"):
            await c.register({"signature": {}})


@pytest.mark.asyncio
@respx.mock
async def test_submit_compliance_posts_to_artifact_endpoint():
    """§23 safety-benchmark goes to /v2/compliance/safety-benchmark."""
    from castor.rcan3.rrf_client import RrfClient

    respx.post("https://rcan.dev/v2/compliance/safety-benchmark").mock(
        return_value=Response(202, json={"accepted": True, "artifact_id": "sb-001"})
    )
    async with RrfClient(base_url="https://rcan.dev") as c:
        out = await c.submit_compliance("safety-benchmark", {"signature": {}, "data": {}})
    assert out["accepted"] is True
