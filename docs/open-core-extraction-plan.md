# OpenCastor Open-Core Extraction Plan

**Goal:** OpenCastor's safety kernel is the open `robot-md-gateway`, not a private duplicate. After extraction, OpenCastor's commercial value is in operational ergonomics (drivers, fleet UI, cloud bridge, premium policies, support) — never structural safety.

**Source:** Spec §6 (open-core boundary at Layer 4); §9 Weeks 7–12 of the 12-week roadmap.

**Status:** authored 2026-05-04 (Plan 7 Phase 0 Task 1).

**Reconciliation note.** This is a working document that grounds the abstract Plan 7 plan-body schedule in the *actual* OpenCastor file layout. The Plan 7 plan body (`docs/superpowers/plans/2026-05-04-adjacent-and-demo.md` in `opencastor-ops`) was authored against an `opencastor/safety/{manifest,auth,gates,replay,keys,estop}.py` + `opencastor/audit/chain.py` module map that does not match reality. Real layout: package is `castor/`, the safety modules are `castor/safety/{anti_subversion,authorization,bounds,monitor,p66_manifest,protocol,state}.py`, and audit-chain code lives in `castor/authority.py`. This doc is the source of truth for the extraction effort; the plan body's task scaffolding stands but its file-path stanzas need amendment per Phase 0 Task 1.

**Existing entry point.** The Plan 6 Task 13b parity placeholder at `tests/cert/test_track_2_parity.py` already commits OpenCastor to a runtime-level integration via `robot_md_gateway.make_app(...)` exercising all 14 cert properties end-to-end. The module-by-module extraction below converges on that placeholder: each task fills in one slice of the parity surface, and Task 8's milestone declaration corresponds to the placeholder's `test_track_2_parity_full_suite_pending_plan_7` slot becoming a real suite.

---

## Architecture (revised 2026-05-04 after Phase 1 deeper audit)

> **Audit finding that supersedes the original plan-body framing.** Phase 1 Task 4's deeper read of `castor/confidence_gate.py` + `castor/hitl_gate.py` vs `robot_md_gateway/cert/gates.py` revealed that the OpenCastor and gateway modules are *at different layers, not duplicates*. The same shape applies to all 7 modules in the original schedule.
>
> **OpenCastor's `castor/safety/`, `castor/confidence_gate.py`, `castor/hitl_gate.py`, `castor/authority.py`, etc. are runtime orchestration** — they evaluate confidence in real time before driver dispatch, hold async pending queues for two-step §8 PENDING_AUTH/AUTHORIZE flow, route notifications to WhatsApp/Telegram, manage workspace + joint + force bounds, etc.
>
> **The gateway's `cert/*` modules are envelope-time cert-property verifiers** — they inspect a received envelope's payload, return `(bool, reason)`, and record to `cert_report` (singleton). They do not orchestrate; they verify proof-of-orchestration.
>
> Concrete divergence on the gates module alone:
>
> | Axis | OpenCastor `ConfidenceGateManager.check` | Gateway `check_confidence` |
> |---|---|---|
> | Return | `GateOutcome` enum (PASS / ESCALATE / BLOCK / BYPASS) | `tuple[bool, str]` |
> | Scope vocab | "control" / "config" / "training" / "status" | "READ" / "NAVIGATE" / "MANIPULATE" / "ESTOP" |
> | When called | Real-time, before driver dispatch (~20 call sites in `castor/`) | At envelope receive |
> | Side effect | Logs + flow control | Records to `cert_report` (RC-003) |
>
> Same divergence pattern on HiTL: `HiTLGateManager.check` is async with pending queues; `check_hitl` is sync envelope inspection.
>
> **The two layers complement each other; neither replaces the other.** The right "extraction" is *not* module-by-module replacement. It is a **runtime-level integration**: OpenCastor wires `robot_md_gateway.receiver.make_app(...)` as a cert-property verifier layer over its envelope-receive boundary. The existing OpenCastor runtime orchestration code stays.

## Integration boundary

The gateway exposes `make_app(...)` at `robot_md_gateway.receiver.make_app`. It returns a FastAPI app with a single `POST /v1/invoke` route that runs every received envelope through the full 14-property cert pipeline. Each property is opt-in via a constructor parameter:

| Cert property | `make_app(...)` parameter | Module |
|---|---|---|
| MF-001 / MF-002 (manifest provenance) | `resolver: RRFResolver` (required) | `manifest_provenance.py` |
| GW-002 / GW-003 (tier + tool allowlist) | `tool_allowlist`, `bearer_tiers` | `cert/policy.py` |
| RC-001 (envelope signature) | `require_envelope_signature` | `cert/envelope.py` |
| RC-002 (replay protection) | `replay_cache` | `cert/envelope.py` |
| RC-003 (confidence) | `confidence_policy` | `cert/gates.py` |
| RC-004 (HiTL chain inspection) | `hitl_policy` | `cert/gates.py` |
| RR-001 / RR-002 (revocation) | `revocation_resolver`, `revocation_cache` | `cert/revocation.py` |
| SF-001 / SF-002 (safety state) | `safety_monitor` | `cert/safety.py` |
| AC-001 (audit) | `audit_chain` | `cert/audit.py` |

OpenCastor's integration shape per spec §6 + §9 Weeks 7–12: route every incoming RCAN INVOKE envelope through this verifier layer **before** dispatching to OpenCastor's runtime orchestration. The existing runtime orchestration (HiTLGateManager, ConfidenceGateManager, BoundsChecker, SafetyLayer, etc.) stays intact and runs after the cert-property verifier passes the envelope through.

The "≥80% of safety-kernel surface in gateway" exit criterion (spec §9 Week 11) is satisfied because the **envelope-time cert-property surface lives in the gateway** — every cross-runtime promise OpenCastor makes about safety properties is structurally enforced by gateway code, not OpenCastor code. OpenCastor's local orchestration code remains as the runtime mechanism that satisfies those promises in real time.

---

## Revised Phase 1 schedule

Phase 1 is now a **single integration track**, not 6 module-by-module extractions. The track has 4 sub-tasks of increasing breadth, each opt-in via `make_app(...)` parameters:

| # | Sub-task | What it does | Cert properties exercised | Test deliverable |
|---|---|---|---|---|
| 1 | **Test fixture + minimal smoke** | Add a `make_app(...)` test fixture + TestClient. Smoke-test that gateway is reachable and tool-allowlist denies an unknown tool. | GW-002, GW-003 | `tests/cert/test_track_2_parity_gateway_smoke.py` |
| 2 | **Sign + replay + revoke** | Wire envelope-signature, replay-cache, revocation-resolver. Test envelopes round-trip through verifier; replay denied; revoked-kid denied. | RC-001, RC-002, RR-001, RR-002 | `tests/cert/test_track_2_parity_envelope_verification.py` |
| 3 | **Confidence + HiTL chain inspection** | Wire `confidence_policy` + `hitl_policy` cert-side verifiers (envelope-time) alongside OpenCastor's runtime `ConfidenceGateManager` + `HiTLGateManager` orchestration. Cert-side verifies the envelope's `inference_confidence` field meets the threshold for its scope, and that `delegation_chain` is properly formed. Runtime-side continues real-time orchestration unchanged. | RC-003, RC-004, MF-001, MF-002 | `tests/cert/test_track_2_parity_gates_envelope.py` |
| 4 | **Safety + audit** | Wire `safety_monitor` + `audit_chain`. Cert-side verifies envelope-time safety state (gateway's binary state machine — separate from OpenCastor's `SafetyLayer` runtime) and emits audit entries to a hash-linked Ed25519-signed chain. Audit chain is *additive* on top of OpenCastor's existing `castor/authority.py` `audit_chain` list — both run; the gateway-format bundle becomes the canonical Track 2 evidence artifact. | SF-001, SF-002, AC-001 | `tests/cert/test_track_2_parity_safety_audit.py` |

Each sub-task fills in a slice of the Plan 6 Task 13b parity placeholder at `tests/cert/test_track_2_parity.py::test_track_2_parity_full_suite_pending_plan_7`. Sub-task 4 also makes that placeholder name redundant — at completion it's renamed to `test_track_2_parity_full_suite` and the docstring updated.

**What this *isn't*:** there is no source-code refactor of `castor/confidence_gate.py`, `castor/hitl_gate.py`, `castor/safety/state.py`, `castor/authority.py`, etc. They keep their current shape. The integration is **at OpenCastor's RCAN INVOKE envelope-receive boundary** (likely `castor/api.py` or its routes module) — that's where `make_app(...)` hooks in.

**Production wiring is out of scope for Phase 1 (in this revised form).** Phase 1 ends with the integration tested in `tests/cert/`. Wiring `make_app(...)` into OpenCastor's production envelope-receive flow is a Phase 2 task that this doc adds when scoped.

Per spec §9 Week 11 exit criterion: ≥80% of safety-kernel surface in gateway. Under the revised framing this is satisfied because **the envelope-time cert-property surface (14 properties) is entirely in `robot-md-gateway`** and OpenCastor exercises that surface via `make_app(...)`. OpenCastor's runtime orchestration code is *not* part of "safety-kernel surface" in the spec's sense — it's the runtime mechanism that satisfies safety promises, not the structural enforcement layer.

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

- All 14 cert properties (MF-001/002, GW-002/003, RC-001/002/003/004, RR-001/002, SF-001/002, AC-001) exercised against OpenCastor's test envelopes via `robot_md_gateway.receiver.make_app(...)`. The full-suite parity test at `tests/cert/test_track_2_parity.py::test_track_2_parity_full_suite` (renamed from `_pending_plan_7`) passes.
- OpenCastor's full L1-L4 + Track 2 cert reports are signed by the OpenCastor release key and pass against the same ROBOT.md fixtures the gateway uses.
- Track 2 NORMATIVE-conditional declaration in `~/opencastor-ops/operations/2026-05-04-track-2-normative.md` updates from "OpenCastor parity pending Plan 7 Phase 1" → "OpenCastor parity verified — 14 cert properties exercised via runtime-level make_app(...) integration."
- Phase 2 (production wiring of `make_app(...)` into `castor/api.py`) is *not* part of Phase 1 exit. Phase 1 ships test-only integration; Phase 2 ships production wiring.

---

## Phase 1 + Phase 3 session plan (drafted 2026-05-04)

Today's audit (Phase 0 Task 1) reframes the extraction shape. The original Plan 7 plan body assumes 6 of 7 modules are "private duplicate replace-with-adapter" extractions; reality is that 5 of 7 are **additive** (OpenCastor has *no* equivalent today) and only 2 require true module replacement. This shifts the right execution order.

### Recommended Phase 1 sequence (revised 2026-05-04 after deeper audit)

| Order | Sub-task | What | Why this order |
|---|---|---|---|
| 1 | Sub-task 1 — Test fixture + smoke | Add a `make_app(...)` test fixture and a 1-3 test smoke that exercises the gateway's `/v1/invoke` route via TestClient with `tool_allowlist` only. | Lowest risk; proves the integration shape works in OpenCastor's test env. No production code change. |
| 2 | Sub-task 2 — Sign + replay + revoke | Add envelope signature + replay + revocation tests. Requires a signed envelope fixture + revocation resolver mock. | Validates the cert-property side of the integration without touching OpenCastor runtime. |
| 3 | Sub-task 3 — Confidence + HiTL chain | Add `confidence_policy` + `hitl_policy` to the fixture; assert RC-003/RC-004 fire correctly. | Most subtle layer: requires understanding OpenCastor's runtime gates *don't* move; the cert-side fires alongside them. |
| 4 | Sub-task 4 — Safety + audit | Add `safety_monitor` + `audit_chain` to the fixture; assert SF-001/SF-002/AC-001 fire and audit chain emits hash-linked entries. | Last because audit chain is the largest surface; gives complete 14-property coverage. |
| 5 | Milestone bookkeeping | Update `operations/2026-XX-XX-open-core-extraction-milestone.md`; rename `test_track_2_parity_full_suite_pending_plan_7` to `test_track_2_parity_full_suite`; update Track 2 NORMATIVE-conditional declaration to NORMATIVE. | After all 14 properties exercised. |

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

- All Phase 1 sub-task execution (today is Phase 0 close + audit-driven re-scope; Phase 1 sub-task 1 starts in a follow-up session).
- Production wiring of `make_app(...)` into OpenCastor's `castor/api.py` envelope-receive flow — this is Phase 2 in the revised plan.
- Phase 2 of the original Plan 7 plan body (pendant firmware) — hardware-blocked on stuck BOOT button.
- Phase 4 of the original Plan 7 plan body (Week-12 demo) — gated on Plan 5 governance kickoff + Plan 6 Phase 5 ESTOP procurement.

---

## What stays in OpenCastor

Under the runtime-level integration framing, *no source code moves out of OpenCastor* — the gateway runs alongside, not instead. OpenCastor's:

- **Runtime orchestration** stays as-is: `castor/confidence_gate.py`, `castor/hitl_gate.py`, `castor/authority.py`, `castor/safety/{state,bounds,monitor,authorization,p66_manifest,protocol,anti_subversion}.py`, `castor/apikeys.py`. These do real-time work the gateway never does.
- **Driver, fleet, cloud-bridge, premium-policy code** stays — commercial differentiator, never in scope for extraction.
- **Existing audit-chain export** (`castor/authority.py` `audit_chain` as `list[dict]`) stays. The gateway's hash-linked Ed25519-signed chain is *additive*, not a replacement. Phase 1 sub-task 4 wires both; downstream Phase 2 production-wiring task may decide to deprecate the OpenCastor-format chain after consumers migrate.

What changes structurally is **where OpenCastor's promises about envelope-time safety properties get enforced**: now those promises are routed through `robot-md-gateway` rather than satisfied by OpenCastor code that "looks the same as the gateway." That is the open-core boundary the spec §6 + §9 Week 11 are describing.
