# OpenCastor Open-Core Extraction Plan

**Goal:** OpenCastor's safety kernel is the open `robot-md-gateway`, not a private duplicate. After extraction, OpenCastor's commercial value is in operational ergonomics (drivers, fleet UI, cloud bridge, premium policies, support) — never structural safety.

**Source:** Spec §6 (open-core boundary at Layer 4); §9 Weeks 7–12 of the 12-week roadmap.

**Status:** authored 2026-05-04 (Plan 7 Phase 0 Task 1).

**Reconciliation note.** This is a working document that grounds the abstract Plan 7 plan-body schedule in the *actual* OpenCastor file layout. The Plan 7 plan body (`docs/superpowers/plans/2026-05-04-adjacent-and-demo.md` in `opencastor-ops`) was authored against an `opencastor/safety/{manifest,auth,gates,replay,keys,estop}.py` + `opencastor/audit/chain.py` module map that does not match reality. Real layout: package is `castor/`, the safety modules are `castor/safety/{anti_subversion,authorization,bounds,monitor,p66_manifest,protocol,state}.py`, and audit-chain code lives in `castor/authority.py`. This doc is the source of truth for the extraction effort; the plan body's task scaffolding stands but its file-path stanzas need amendment per Phase 0 Task 1.

**Existing entry point.** The Plan 6 Task 13b parity placeholder at `tests/cert/test_track_2_parity.py` already commits OpenCastor to a runtime-level integration via `robot_md_gateway.make_app(...)` exercising all 14 cert properties end-to-end. The module-by-module extraction below converges on that placeholder: each task fills in one slice of the parity surface, and Task 8's milestone declaration corresponds to the placeholder's `test_track_2_parity_full_suite_pending_plan_7` slot becoming a real suite.

---

## Migration patterns

Three patterns, depending on the OpenCastor side's current shape:

1. **Additive.** OpenCastor has no equivalent today; the extraction is purely "take the dependency + start using it." No deletion, no adapter. The first parity test asserts the gateway code path runs; subsequent tests assert behavior at OpenCastor's call sites.

2. **Replace-with-adapter.** OpenCastor has a private duplicate with a similar shape. Extract by: (a) keeping only the public symbol the OpenCastor side exposes today, (b) re-exporting it from the gateway module, (c) deleting OpenCastor's implementation, (d) parity test asserts identical behavior on shared fixtures.

3. **Format-conversion.** OpenCastor has a private duplicate but with an *incompatible* output format (e.g. audit chain serialized as `list[dict]` vs gateway's hash-linked signed bundle). Extraction requires changing OpenCastor's downstream consumers — cannot be a transparent adapter. Per-task acceptance: the gateway format becomes the on-disk format; OpenCastor's existing readers add a one-shot back-compat shim if needed for older bundles.

---

## Module-by-module schedule

| # | Module | Pattern | Week | OpenCastor source (real path) | Gateway source (`src/robot_md_gateway/`) | Notes |
|---|---|---|---|---|---|---|
| 1 | Manifest provenance verifier | **Additive** | 7 | (no module today) | `manifest_provenance.py` (Plan 3 Task 14) | OpenCastor has *no* signed-ROBOT.md verifier today. `castor/safety/p66_manifest.py` is a Protocol-66 conformance declaration — different concept. Extraction is "add a call site." |
| 2 | LoA / RBAC / tier policy | Replace-with-adapter | 8 | `castor/safety/authorization.py` (`WorkAuthority`, `WorkOrder`, `DestructiveActionDetector`) | `cert/policy.py` (`ToolAllowlist`, `check_tool`, `check_tier`) | Different axes today. OpenCastor's `WorkAuthority` is permission/work-order orchestration; gateway's `ToolAllowlist` is tier/tool gating per cert spec GW-002/GW-003. Extraction defines a thin OpenCastor-side function that delegates tier checks to the gateway, leaves WorkAuthority's order-orchestration locally. |
| 3 | Confidence + HiTL gates | Replace-with-adapter | 8 | `castor/confidence_gate.py` + `castor/hitl_gate.py` (`ConfidenceGate`, `ConfidenceGateManager`, `HiTLGate`, `HiTLGateManager`) | `cert/gates.py` (`ConfidencePolicy`, `check_confidence`, `HiTLPolicy`, `check_hitl`) | Functionally equivalent but different APIs (manager vs policy+function). Adapter wraps gateway's policy in a manager-shaped facade so existing OpenCastor callers don't change. Parity test: RC-003 below-threshold + RC-004 missing-chain produce identical decisions. |
| 4 | Replay protection | **Additive** | 9 | (no module today) | `cert/envelope.py` (`ReplayCache`, `check_replay`) | `castor/safety/anti_subversion.py` is prompt-injection scanning, NOT replay protection — *different concept entirely*. Extraction adds a replay-cache call site at OpenCastor's envelope-receiving boundary. |
| 5 | Key-state checks (revocation) | **Format-conversion** | 9 | `castor/apikeys.py` (`ApiKeyManager` — local API-key lifecycle) | `cert/revocation.py` (`RevocationCache`, `is_revoked`, `RRFRevocationResolver`) | Different trust models. OpenCastor's `apikeys.py` manages *local* API-key revocation; gateway's `revocation.py` does *kid* revocation via RRF. They coexist post-extraction; only the kid-revocation path moves to gateway. Adapter is conceptual: OpenCastor's runtime gains an RRFRevocationResolver instance for inbound envelopes. |
| 6 | ESTOP precedence + bounded action | Replace-with-adapter (partial) | 10 | `castor/safety/state.py` (`SafetyStateSnapshot`, `SafetyTelemetry`) + `castor/safety/bounds.py` (`BoundsChecker`, `JointBounds`) | `cert/safety.py` (`SafetyMonitor`, `GatewayState`, `on_estop_wire`, `can_actuate`) | Gateway's binary state machine (READY/SAFE_STOP/ESTOP_ACTIVE) + heartbeat-staleness rule extract cleanly. OpenCastor's workspace/joint/force bounds are out-of-scope — they stay in OpenCastor as runtime ergonomics. Adapter: OpenCastor's `state.py` becomes a wrapper that delegates ESTOP precedence to `cert.safety.SafetyMonitor` while keeping bounds-checking local. |
| 7 | Audit-bundle export | **Format-conversion** | 10 | `castor/authority.py` (`AuthorityResponseData.audit_chain` as `list[dict]`) | `cert/audit.py` (`AuditChain`, `AuditEntry`, `verify_audit_bundle` — hash-linked + Ed25519-signed) | **Incompatible serialization.** Gateway format becomes authoritative. OpenCastor's downstream consumers (Flutter client, cloud bridge) gain a one-shot reader for both formats during a deprecation window; new bundles emit only the gateway format. |

Per spec §9 Week 11 exit criterion: ≥80% of safety-kernel surface in gateway. Computed by line count of code that imports/delegates to `robot_md_gateway.cert.*` divided by total safety-kernel line count in `castor/safety/` + `castor/{authority,confidence_gate,hitl_gate,apikeys}.py`.

After each module's extraction, OpenCastor:
1. Replaces the local code path with a delegation to gateway (additive cases) or removes the duplicate behind an adapter (replace cases) or converts the format with an explicit transition window (format-conversion cases).
2. Files a per-module parity test under `tests/cert/test_track_2_parity_<module>.py` that exercises both code paths against the same fixtures.
3. Updates this doc's "Status" cell for the module from "planned" → "extracted."

---

## Parity-test contract

The Plan 6 Task 13b placeholder at `tests/cert/test_track_2_parity.py` already commits to:
1. The dependency on `robot-md-gateway>=0.4.0a1` in `pyproject.toml` (already pinned).
2. All cert sub-modules importable from the gateway (already passing).
3. `test_track_2_parity_full_suite_pending_plan_7` — the placeholder slot to fill.

The full-suite test, when filled in by Phase 1 Task 8, asserts:
- A signed ROBOT.md fixture (`signed-good.md` from gateway repo) is verified identically by gateway-direct call and OpenCastor-runtime call.
- All 14 cert property IDs (GW-001/002/003, MF-001/002, RC-001/002/003/004, RR-001/002, SF-001/002, AC-001) appear in the cert report after the suite runs through OpenCastor's `make_app(...)` integration.
- Every per-module parity test from Tasks 2-7 passes.

Per-module parity tests live at `tests/cert/test_track_2_parity_<module>.py`, with names matching the module column above (e.g. `test_track_2_parity_manifest_provenance.py`).

---

## Exit criteria

Per spec §9 Week 11 "≥80% of safety-kernel surface in gateway":

- All 7 modules above have a "extracted" status in this doc.
- OpenCastor's `castor/safety/` + audit code consists of:
  - **Local-only modules** that don't move to gateway (e.g. `castor/safety/bounds.py` workspace/joint/force, `castor/safety/p66_manifest.py` Protocol-66 conformance declaration, `castor/safety/protocol.py` configurable rule engine — these are runtime ergonomics, not safety-kernel proper).
  - **Adapter / delegation modules** that import from `robot_md_gateway.cert.*`.
- OpenCastor's full L1-L4 + Track 2 cert reports are signed by the OpenCastor release key and pass against the same ROBOT.md fixtures as the gateway.
- Track 2 NORMATIVE-conditional declaration in `~/opencastor-ops/operations/2026-05-04-track-2-normative.md` updates from "OpenCastor parity pending Plan 7 Phase 1" → "OpenCastor parity verified."

---

## Phase 1 + Phase 3 session plan (drafted 2026-05-04)

Today's audit (Phase 0 Task 1) reframes the extraction shape. The original Plan 7 plan body assumes 6 of 7 modules are "private duplicate replace-with-adapter" extractions; reality is that 5 of 7 are **additive** (OpenCastor has *no* equivalent today) and only 2 require true module replacement. This shifts the right execution order.

### Recommended Phase 1 sequence (revised)

| Order | Task | Pattern | Rationale |
|---|---|---|---|
| 1 | Task 4 — Confidence + HiTL gates | Replace-with-adapter | True duplicate. Cleanest first replace; lets us prove the adapter pattern on a low-risk module before touching format-sensitive ones. |
| 2 | Task 6 — ESTOP precedence (state-machine portion only) | Replace-with-adapter (partial) | Track 2 cert property SF-001 depends on this. Gateway's `SafetyMonitor` becomes the source of truth; bounds-checking stays local. |
| 3 | Task 3 — LoA / RBAC tier policy | **Additive** | Gateway's tier gating is new capability for OpenCastor. Wire in at the runtime envelope-receiving boundary alongside the existing `WorkAuthority`. |
| 4 | Task 5a — Replay protection | **Additive** | Same boundary as Task 3. Add `ReplayCache` instance to runtime. |
| 5 | Task 5b — Key-state / kid revocation | **Additive** | Same boundary. Add `RRFRevocationResolver`. Local API-key path stays untouched. |
| 6 | Task 7 — Audit-bundle export | **Format-conversion** (highest risk) | Last because downstream consumers (Flutter client, cloud bridge) need a back-compat reader during the transition. Plan 7 plan body should expect this to slip beyond Week 10. |
| 7 | Task 8 — ≥80% milestone declaration | Bookkeeping | Only meaningful after Tasks 3-7 land. |

### Recommended Phase 3 sequence

Two tasks (12, 13) sweeping 4 adjacent repos. Per Plan 2 lessons-learned doc §A: use **inline-form** workflow YAML, not the composite action that the Plan 7 plan body's Task 12 Step 2 currently prescribes — that is another Plan 7 plan-body inaccuracy worth amending when Phase 3 starts. Per repo:

| Order | Repo | Why this order |
|---|---|---|
| 1 | `robot-md-autoresearch` | Smallest public surface; quickest baseline for the lint pattern. |
| 2 | `robot-md-surfaces` | Thin wrapper repo. |
| 3 | `opencastor-autoresearch` | Adjacent-domain harness repo. |
| 4 | `opencastor-client` | Flutter app — per Plan 2 lessons §K, only the README + `lib/.../docs/*` are marketing surface. Largest copy footprint. |

Phase 3 is **independent of Phase 1** — it can be dispatched as a parallel subagent track per `superpowers:dispatching-parallel-agents` once Phase 0 ships.

### What stays out of scope this session

- All Phase 1 task execution (today is Phase 0 close; Phase 1 starts in a follow-up session against this revised order).
- Phase 2 (pendant firmware) — hardware-blocked on stuck BOOT button.
- Phase 4 (Week-12 demo) — gated on Plan 5 governance kickoff + Plan 6 Phase 5 ESTOP procurement.

---

## Out-of-scope (explicitly retained in OpenCastor)

These are *not* part of the extraction. They stay in OpenCastor because they're operational ergonomics, not safety-kernel structure:

- `castor/safety/bounds.py` — workspace + joint + force-limit geometry (per-robot configuration, not safety-policy).
- `castor/safety/p66_manifest.py` — Protocol-66 conformance declaration (a *list of which rules are implemented*, not an enforcement engine).
- `castor/safety/protocol.py` — configurable safety-rule engine (`SafetyRule`, `RuleViolation`); commercial differentiator.
- `castor/safety/anti_subversion.py` — prompt-injection scanning (not in the safety-kernel cert spec at all).
- `castor/apikeys.py` *local* API-key lifecycle (kid-revocation portion *does* move; local API-key management stays).
- All driver, fleet, cloud-bridge, premium-policy code.
