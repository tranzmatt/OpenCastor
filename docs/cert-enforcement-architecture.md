# Cert-enforcement architecture

**Status:** authored 2026-05-04 (Plan 7 Phase 2 close).
**Refs:** `docs/open-core-extraction-plan.md`; spec §6 (open-core boundary at Layer 4); spec §9 Week 11 (≥80% safety-kernel surface in gateway).

---

## TL;DR

OpenCastor's Track 2 cert-property guarantees are enforced **by deployment topology**, not by in-process integration in `castor/api.py`. The `robot-md-gateway` runs as a separate systemd process in front of (or alongside) OpenCastor; it owns the actuator device files exclusively (proven by cert property GW-001), so any envelope-time cert check the gateway performs is structurally enforced for actuator-bound traffic — regardless of how the envelope reaches OpenCastor.

This document explains the topology and what it does + does not guarantee, so that operators and reviewers don't expect to find `make_app(...)` wiring inside `castor/api.py`.

---

## Production topology (Bob, RRN-000000000002)

```
                        ┌──────────────────────┐
   client ──RCAN INVOKE→│  robot-md-gateway    │── /v1/invoke ──┐
                        │  (systemd unit)      │                │
                        │  owns /dev/ttyACM0   │                │
                        └──────────────────────┘                │
                                  │                             │
                                  ▼                             ▼
                          actuator on ttyACM0           OpenCastor /rcan
                          (cert-enforced path)          (informational +
                                                         high-level routing)
```

Per `~/opencastor-ops/operations/2026-05-04-robot-md-gateway-on-bob-deploy.md`:
- `robot-md-gateway==0.4.0a1` runs as a systemd unit on Bob.
- udev rule grants the gateway exclusive access to `/dev/ttyACM0` (and other actuator-class device files); other processes get EACCES.
- Plan 6 Phase 4 Task 18 verified: 10/10 EACCES from non-gateway processes.

OpenCastor's existing `castor/api.py` `/rcan` endpoint accepts envelopes for high-level routing (registry resolution, skill invocation, status queries) but does **not** itself drive the cert-enforced actuator (the gateway does).

## What this topology guarantees

For any envelope that ultimately drives an **actuator owned by the gateway** (today: `/dev/ttyACM0` on Bob; per-rig udev rules elsewhere):

| Cert property | How it's enforced |
|---|---|
| GW-001 (device isolation) | Gateway exclusively owns the device file via udev. OS-level enforcement. |
| GW-002 (tier policy) | Gateway's `make_app(tool_allowlist=, bearer_tiers=)` runs at envelope receive. |
| GW-003 (tool allowlist) | Same. |
| MF-001 / MF-002 (manifest provenance) | Gateway's `verify_manifest()` runs first in the receiver pipeline. |
| RC-001 (envelope signature) | Gateway's `make_app(require_envelope_signature=True)`. |
| RC-002 (replay) | Gateway's `make_app(replay_cache=...)`. |
| RC-003 (confidence) | Gateway's `make_app(confidence_policy=...)`. |
| RC-004 (HiTL chain) | Gateway's `make_app(hitl_policy=...)`. |
| RR-001 / RR-002 (revocation) | Gateway's `make_app(revocation_resolver=...)` + `round_trip_register()`. |
| SF-001 / SF-002 (safety state) | Gateway's `make_app(safety_monitor=...)`. |
| EV-001 (audit bundle) | Gateway's `make_app(audit_chain=...)` + `chain.export_signed()`. |

The Track 2 NORMATIVE-conditional → NORMATIVE update (`opencastor-ops/operations/2026-05-04-track-2-normative.md`) captures this directly: OpenCastor's parity is established because OpenCastor exercises the **same `make_app(...)` factory** in `tests/cert/test_track_2_parity_*.py` that the gateway runs in production. Phase 1 closed the test-side proof; Phase 2 closes by reaffirming the deployment posture that makes the test-side proof meaningful in production.

## What this topology does *not* guarantee

The cert-enforcement is **per-actuator**, not per-OpenCastor-instance. Specifically:

1. **Actuators OpenCastor drives directly without going through the gateway** are not cert-enforced. On Bob, the SO-ARM101 servos are on `/dev/ttyUSB0` (Feetech STS3215 ×6) — a different device file. OpenCastor's existing servo drivers can open `/dev/ttyUSB0` directly, so envelopes reaching `/rcan` and dispatching to those drivers don't pass through the gateway's cert pipeline.

   For full Track 2 coverage of *all* OpenCastor-driven actuators, additional udev rules + corresponding `robot-md-gateway` units (or one gateway claiming multiple device files) would be required. This is a per-rig deployment decision; it is documented here so operators don't assume "Track 2 NORMATIVE" means "every OpenCastor-driven action is cert-enforced."

2. **High-level orchestration paths through `/rcan`** (registry queries, skill invocation, status reads) are not cert-enforced and were never intended to be. They run under OpenCastor's existing `verify_token` + bearer-tier auth — distinct from the gateway's cert pipeline. This is by design: cert properties in the spec §22-26 sense are about envelope-time safety claims (manifest signed, replay protected, ESTOP precedence, etc.), not about general API auth.

3. **Self-hosted OpenCastor deployments without a separate gateway process** do not inherit any cert enforcement automatically. Self-hosted operators must either:
   - Deploy `robot-md-gateway` as a sibling systemd unit and configure their actuator udev rules to grant the gateway exclusive ownership; or
   - Accept that their deployment is not Track 2 NORMATIVE.

   In-process integration of `make_app(...)` into `castor/api.py` was considered (interpretation 2 in Plan 7's Phase 2 framing) and rejected: it would have produced cert-property checks running in-process but no device-isolation enforcement, which would fail to satisfy GW-001 — the structural property that the others rest on. Interpretation 1 (this document) is the canonical Phase 2.

## Self-host operator checklist

For an OpenCastor deployment claiming Track 2 NORMATIVE on actuator(s) `<dev_paths>`:

- [ ] Install `robot-md-gateway>=0.4.0a1` as a systemd unit on the same host as OpenCastor.
- [ ] Configure udev rules so each `<dev_paths>` is owned by the gateway's user with `0660` mode (gateway-readable, not world-accessible).
- [ ] Verify EACCES from non-gateway processes: `sudo -u <opencastor_user> python -c "open('<dev_path>', 'rb').read(1)"` should fail with `PermissionError`.
- [ ] Configure OpenCastor's drivers for `<dev_paths>` to forward to the gateway's `/v1/invoke` instead of opening the device directly. (Driver-by-driver configuration; tracked in OpenCastor's per-driver docs as the gateway integration matures.)
- [ ] Run `tests/cert/test_track_2_parity_*.py` against the gateway version installed; confirm 28/28 green.
- [ ] Sign the resulting evidence bundle and attach to your deployment record per spec §22.

The Bob deployment serves as the reference implementation. See `opencastor-ops/operations/2026-05-04-plan-6-phase-4-prep.md` Task 18 for the GW-001 verification recording template.

## Future Phase

In-process integration of `make_app(...)` (Plan 7's original interpretation 2) is **not currently planned**. The deployment-topology approach satisfies Track 2 NORMATIVE without it, and adding in-process wiring would duplicate enforcement infrastructure without adding device-isolation guarantees. If a future use case (e.g. an OpenCastor-only Docker image targeting non-actuator deployments) wants to claim Track 2 NORMATIVE without a sibling gateway, in-process wiring of `make_app(...)` becomes the cleanest path. Until that need is concrete, this document is the canonical Phase 2 close.
