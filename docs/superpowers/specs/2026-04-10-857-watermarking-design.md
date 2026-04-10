# Design: AI Output Watermarking (craigm26/OpenCastor#857)

**Date:** 2026-04-10
**Issue:** craigm26/OpenCastor#857
**Related spec:** continuonai/rcan-spec#194 (§16.5)
**Status:** Approved — pending implementation plan
**Scope:** craigm26/OpenCastor · continuonai/rcan-py · continuonai/rcan-ts · continuonai/rcan-spec

---

## 1. Problem Statement

EU AI Act Art. 50 requires that AI-generated content be machine-detectable. RCAN's audit chain records every command with ML-DSA-65 signatures and HMAC-SHA256 chain integrity, but no per-output watermark token is embedded in AI-generated `COMMAND` message payloads. A compliance auditor or third-party tool receiving a RCAN COMMAND payload has no machine-readable way to confirm it originated from an AI agent rather than a human operator.

This design closes that gap across the full ecosystem: OpenCastor runtime (embed + verify), rcan-py and rcan-ts SDKs (compute + API verification), and rcan-spec §16.5 (protocol definition).

---

## 2. Approach

**Approach B — Dedicated `castor/watermark.py` module** (chosen over inline and audit-extension alternatives).

A new module owns all watermark logic: token computation, format verification, and HMAC index management. Each downstream component (main.py, audit.py, api.py, SDKs) calls the module rather than embedding watermark logic inline. This creates a clean, testable surface and a consistent interface for SDK parity.

Verification is **audit-chain-backed**: the verify endpoint looks up the token in an in-memory HMAC index built from the audit log, then returns the full audit entry. This proves two things simultaneously — the token is cryptographically valid AND the command is in the tamper-evident audit record (satisfying both Art. 50 and Art. 12).

The verify endpoint is **public** (no auth required) so external compliance tools, notified bodies, and RRF registry integrations can verify tokens without robot credentials.

---

## 3. Token Format

```
rcan-wm-v1:{hex(hmac_sha256(rrn + ":" + thought_id + ":" + timestamp_iso, ml_dsa_private_bytes)[:16])}
```

Example: `rcan-wm-v1:a3f9c1d2b8e47f20`

| Field | Value |
|---|---|
| Prefix | `rcan-wm-v1:` — makes tokens format-detectable by machines (Art. 50); version-upgradeable |
| HMAC key | `RobotKeyPair.ml_dsa_private` bytes from `castor/crypto/pqc.py` — already loaded at runtime, no new key material |
| HMAC input | `rrn + ":" + thought_id + ":" + timestamp_iso` — all fields present in the audit record so verify can recompute without caller providing them |
| Truncation | First 16 bytes → 32 hex chars — compact for payloads; sufficient collision resistance for tamper detection |

The `rcan-wm-v1:` prefix makes the token format-detectable by regex: `^rcan-wm-v1:[0-9a-f]{32}$`.

---

## 4. Architecture

Seven components, each with one responsibility:

| Component | Repo | Change | Responsibility |
|---|---|---|---|
| `castor/watermark.py` | OpenCastor | New | `compute_watermark_token()`, `verify_watermark_token()`, HMAC index management |
| `castor/main.py` | OpenCastor | Modify | Call compute at COMMAND dispatch; embed token in action dict; fix `ai_confidence` propagation |
| `castor/audit.py` | OpenCastor | Modify | Accept `watermark_token` param; write to log entry; update HMAC index |
| `castor/api.py` | OpenCastor | Modify | `GET /api/v1/watermark/verify` — public, no auth; delegates to `verify_watermark_token()` |
| `rcan/watermark.py` | rcan-py | New | `compute_watermark_token()`, `verify_token_format()`, `verify_via_api()` |
| `src/watermark.ts` | rcan-ts | New | `computeWatermarkToken()`, `verifyTokenFormat()`, `verifyViaApi()` |
| `src/pages/spec/section-16.astro` | rcan-spec | Modify | Add §16.5 subsection: token format, audit field, verify endpoint contract, Art. 50 note |

---

## 5. Data Flow

### 5.1 Watermark Computation (OpenCastor runtime)

At COMMAND dispatch in `castor/main.py` (~line 1409), after `brain.think()` returns:

```python
# 1. Fix ai_confidence propagation (prerequisite — never set previously)
action_to_execute["ai_confidence"] = thought.confidence  # fixes SOFTWARE_002 safety rule

# 2. Compute watermark token
from castor.watermark import compute_watermark_token
watermark_token = compute_watermark_token(
    rrn=config["metadata"]["rrn"],
    thought_id=thought.id,
    timestamp=thought.timestamp.isoformat(),
    private_key_bytes=keypair.ml_dsa_private,
)
action_to_execute["watermark_token"] = watermark_token

# 3. Audit (modified call)
audit.log_motor_command(safe_action, thought=thought, watermark_token=watermark_token)
```

`keypair` is already loaded via `load_or_generate_robot_keypair()` in the main loop — no new I/O at dispatch time.

### 5.2 Audit Storage

`AuditLog.log_motor_command()` gains `watermark_token: str | None = None`. When present:
- Written as top-level `"watermark_token"` field in the JSONL log entry (alongside existing `"ai"` block)
- Added to `self._watermark_index[watermark_token] = entry_dict`

`AuditLog._watermark_index: dict[str, dict]` is built by scanning the log file on `AuditLog.__init__` and updated on each write. O(1) lookup for the verify endpoint.

### 5.3 Verification (API endpoint)

```
GET /api/v1/watermark/verify?token=rcan-wm-v1:a3f9c1d2b8e47f20&rrn=RRN-000000000001
```

No authentication required. Response:

```json
{
  "valid": true,
  "rrn": "RRN-000000000001",
  "watermark_token": "rcan-wm-v1:a3f9c1d2b8e47f20",
  "audit_entry": {
    "timestamp": "2026-04-10T14:32:01.123Z",
    "source": "brain",
    "event": "motor_command",
    "watermark_token": "rcan-wm-v1:a3f9c1d2b8e47f20",
    "ai": {
      "thought_id": "thought-abc123",
      "confidence": 0.91,
      "model": "claude-sonnet-4-6"
    },
    "action": { "type": "navigate", "speed": 0.3 },
    "signature": "pqc-v1.<ml_dsa_sig>"
  }
}
```

404 if token not found in index (command not in audit log — token is invalid or not from this robot).

---

## 6. `castor/watermark.py` Module

```python
import hashlib
import hmac
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from castor.audit import AuditLog

WATERMARK_VERSION = "rcan-wm-v1"
WATERMARK_PATTERN = re.compile(r"^rcan-wm-v1:[0-9a-f]{32}$")


def compute_watermark_token(
    rrn: str,
    thought_id: str,
    timestamp: str,
    private_key_bytes: bytes,
) -> str:
    """Compute RCAN AI output watermark token per §16.5."""
    message = f"{rrn}:{thought_id}:{timestamp}".encode()
    digest = hmac.new(private_key_bytes, message, hashlib.sha256).digest()
    return f"{WATERMARK_VERSION}:{digest[:16].hex()}"


def verify_token_format(token: str) -> bool:
    """Return True if token matches rcan-wm-v1:{32 hex chars}."""
    return bool(WATERMARK_PATTERN.match(token))


def verify_watermark_token(token: str, audit_log: "AuditLog") -> dict | None:
    """Look up token in audit HMAC index. Returns audit entry dict or None."""
    if not verify_token_format(token):
        return None
    return audit_log._watermark_index.get(token)
```

---

## 7. SDK Surface

### rcan-py (`rcan/watermark.py`)

```python
def compute_watermark_token(rrn: str, thought_id: str, timestamp: str, private_key_bytes: bytes) -> str: ...
def verify_token_format(token: str) -> bool: ...
async def verify_via_api(token: str, rrn: str, base_url: str) -> dict | None:
    """Call GET /api/v1/watermark/verify. Returns audit entry or None."""
```

Exported from `rcan/__init__.py` alongside existing exports (`RobotURI`, `RCANMessage`, etc.).

### rcan-ts (`src/watermark.ts`)

```typescript
export function computeWatermarkToken(
  rrn: string, thoughtId: string, timestamp: string, privateKeyBytes: Uint8Array
): string

export function verifyTokenFormat(token: string): boolean

export async function verifyViaApi(
  token: string, rrn: string, baseUrl: string
): Promise<Record<string, unknown> | null>
```

Exported from `src/index.ts`. Uses Node.js `crypto` (for `computeWatermarkToken`) with a browser-safe HMAC fallback via `SubtleCrypto`.

**SDK scope**: SDKs provide `compute` for runtime consumers that hold the private key, and `verifyViaApi` for external tools that call the robot's public endpoint. Local HMAC verification is not provided — SDKs do not hold robot private keys.

---

## 8. rcan-spec §16.5

New subsection added to `src/pages/spec/section-16.astro` (the existing AI & Autonomy Controls section):

**§16.5 — AI Output Watermarking**

Defines:
- Token format and computation algorithm
- Required `watermark_token` field in COMMAND message payloads and audit records
- `GET /api/v1/watermark/verify` endpoint contract (request params, response schema, 404 semantics)
- EU AI Act Art. 50 compliance note: "RCAN §16.5 satisfies the machine-detectability requirement for AI-generated content in robot command pipelines"
- Conformance: required at L2+ (Secure tier and above)

---

## 9. Prerequisite Fix

**`action_to_execute["ai_confidence"]` propagation gap** (no issue number — inline fix in this PR):

`castor/safety/protocol.py` `SOFTWARE_002` rule checks `action.get("ai_confidence")` against threshold 0.7, but this field has never been set from `thought.confidence` in the main dispatch loop. The watermark implementation fixes this as part of the same dispatch-loop edit (step 2 in §5.1 above). This is not a separate commit — it ships as part of the watermark feature since they touch the same lines.

---

## 10. Testing

| Test file | What it covers |
|---|---|
| `tests/test_watermark.py` (new) | `compute_watermark_token` determinism, `verify_token_format` valid/invalid patterns, `verify_watermark_token` hit/miss, HMAC index build on init |
| `tests/test_audit.py` (modify) | `log_motor_command` with `watermark_token` writes field to JSONL entry; index updated |
| `tests/test_api_endpoints.py` (modify) | `GET /api/v1/watermark/verify` — valid token returns 200 + audit entry; invalid token returns 404; no auth required |
| `tests/test_main.py` (modify) | Dispatch loop sets `ai_confidence` and `watermark_token` on action dict |
| rcan-py `tests/test_watermark.py` (new) | compute, format check, verify_via_api mock |
| rcan-ts `tests/watermark.test.ts` (new) | computeWatermarkToken, verifyTokenFormat, verifyViaApi mock |

---

## 11. Out of Scope

- RRF registry integration for cross-robot token verification (follow-on)
- rcan-spec §16.5 as a full dedicated section page (subsection of section-16.astro is sufficient)
- Watermark verification in the RCAN conformance test suite (tracked separately)
- SDK changes to rcan-py or rcan-ts beyond the `watermark` module
