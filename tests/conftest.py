"""Shared pytest fixtures and stubs for OpenCastor tests.

Provides a lightweight ``openai`` stub so provider tests run without the
optional ``openai`` package installed.  Tests that exercise real OpenAI API
behaviour (e.g. integration tests) should skip via ``pytest.importorskip``.
"""

import sys
import types
from unittest.mock import MagicMock


def _make_openai_stub() -> types.ModuleType:
    """Return a minimal ``openai`` package stub."""
    openai_mod = types.ModuleType("openai")
    openai_mod.OpenAI = MagicMock(name="OpenAI")
    openai_mod.AsyncOpenAI = MagicMock(name="AsyncOpenAI")
    openai_mod.APIError = type("APIError", (Exception,), {})
    openai_mod.AuthenticationError = type("AuthenticationError", (Exception,), {})
    openai_mod.RateLimitError = type("RateLimitError", (Exception,), {})
    return openai_mod


# Only inject stub when the real package is absent.
if "openai" not in sys.modules:
    sys.modules["openai"] = _make_openai_stub()
