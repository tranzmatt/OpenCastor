"""Unit tests for castor.hitl_gate."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from castor.hitl_gate import HiTLGate, HiTLGateManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_thought(thought_id: str = "t-001") -> Any:
    t = MagicMock()
    t.id = thought_id
    return t


def make_action(action_type: str = "grip") -> dict:
    return {"type": action_type}


# ---------------------------------------------------------------------------
# No gate → allow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_matching_gate_allows():
    mgr = HiTLGateManager(gates=[HiTLGate(action_types=["grip"], require_auth=True)])
    result = await mgr.check(make_action("move"), make_thought())
    assert result is True


# ---------------------------------------------------------------------------
# require_auth=False → allow without callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_auth_false_allows():
    mgr = HiTLGateManager(gates=[HiTLGate(action_types=["grip"], require_auth=False)])
    result = await mgr.check(make_action("grip"), make_thought())
    assert result is True


# ---------------------------------------------------------------------------
# approval_required=True invokes callback (approve path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_required_approve():
    mgr = HiTLGateManager(
        gates=[HiTLGate(action_types=["grip"], require_auth=True, auth_timeout_ms=5000)]
    )

    async def approve_soon():
        await asyncio.sleep(0.05)
        # Find the pending_id
        pending_id = next(iter(mgr._pending))
        mgr.authorize(pending_id, "approve")

    result_holder = []

    async def run():
        task = asyncio.create_task(mgr.check(make_action("grip"), make_thought()))
        await approve_soon()
        result_holder.append(await task)

    await run()
    assert result_holder[0] is True


# ---------------------------------------------------------------------------
# approval_required=True — deny path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_required_deny():
    mgr = HiTLGateManager(
        gates=[HiTLGate(action_types=["grip"], require_auth=True, auth_timeout_ms=5000)]
    )

    async def deny_soon():
        await asyncio.sleep(0.05)
        pending_id = next(iter(mgr._pending))
        mgr.authorize(pending_id, "deny")

    result_holder = []

    async def run():
        task = asyncio.create_task(mgr.check(make_action("grip"), make_thought()))
        await deny_soon()
        result_holder.append(await task)

    await run()
    assert result_holder[0] is False


# ---------------------------------------------------------------------------
# Timeout path — on_timeout=block → returns False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_blocks():
    mgr = HiTLGateManager(
        gates=[
            HiTLGate(
                action_types=["grip"],
                require_auth=True,
                auth_timeout_ms=50,  # 50 ms timeout
                on_timeout="block",
            )
        ]
    )
    result = await mgr.check(make_action("grip"), make_thought())
    assert result is False


# ---------------------------------------------------------------------------
# Timeout path — on_timeout=allow → returns True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_allows_when_on_timeout_allow():
    mgr = HiTLGateManager(
        gates=[
            HiTLGate(
                action_types=["grip"],
                require_auth=True,
                auth_timeout_ms=50,
                on_timeout="allow",
            )
        ]
    )
    result = await mgr.check(make_action("grip"), make_thought())
    assert result is True


# ---------------------------------------------------------------------------
# authorize() returns False for unknown pending_id
# ---------------------------------------------------------------------------


def test_authorize_unknown_pending_id():
    mgr = HiTLGateManager(gates=[])
    assert mgr.authorize("no-such-id", "approve") is False
