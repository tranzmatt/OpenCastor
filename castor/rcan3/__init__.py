"""castor.rcan3 — Integration layer wrapping rcan-py 3.3+ for the 3.0 migration.

Each submodule is a single-responsibility adapter:
- reader      : ROBOT.md frontmatter parsing (wraps rcan.from_manifest)
- identity    : PQ keypair generation + local persistence at ~/.castor/keys/
- signer      : Dict-level hybrid signing (wraps rcan.sign_body)
- rrf_client  : RRF v2 registration + lookup
- compliance  : §22-26 builder pass-through + RRF intake submission
- harness_protocol : Harness Protocol + Observation/Thought/ActionResult dataclasses
- castor_harness   : opencastor's native think/do implementation
"""

from __future__ import annotations

# Lazy-load all submodule symbols so intermediate TDD RED states stay isolated.
# Each name is resolved on first access; missing submodules only error when
# that specific symbol is used, not when the package is imported.

_LAZY: dict[str, str] = {
    "RcanManifest": "castor.rcan3.reader",
    "read_robot_md": "castor.rcan3.reader",
    "CastorIdentity": "castor.rcan3.identity",
    "load_or_generate_identity": "castor.rcan3.identity",
    "Harness": "castor.rcan3.harness_protocol",
    "Observation": "castor.rcan3.harness_protocol",
    "Thought": "castor.rcan3.harness_protocol",
    "ActionResult": "castor.rcan3.harness_protocol",
    "CastorDefaultHarness": "castor.rcan3.castor_harness",
}

__all__ = list(_LAZY)


def __getattr__(name: str) -> object:
    if name in _LAZY:
        from importlib import import_module

        mod = import_module(_LAZY[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
