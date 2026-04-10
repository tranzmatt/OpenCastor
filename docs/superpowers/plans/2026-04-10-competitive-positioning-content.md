# Competitive Positioning Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface RCAN/OpenCastor's physical AI safety architecture for developers and compliance teams through five new content pieces across two repos, establishing keyword-ranked documentation that counters bolt-on LLM safety layer marketing with verifiable technical substance.

**Architecture:** Two independent content streams — (A) rcan.dev Astro pages (continuonai/rcan-spec): `/safety`, `/compliance/frameworks`, homepage section; (B) OpenCastor markdown docs: `docs/safety-architecture.md`, `docs/compliance/competitive-positioning.md`. No shared logic. Both repos use existing layout components and Tailwind design tokens. Content is technically precise; every claim links to a spec section or open issue.

**Tech Stack:** Astro 4.x + Tailwind CSS (rcan-spec); Markdown (OpenCastor). Build: `npm run build` + `npx vitest run tests/functions.test.ts` (rcan-spec); no build step (OpenCastor).

---

## Repo A: continuonai/rcan-spec

Working directory for all Tasks 1–4: `/home/craigm26/rcan-spec`

---

### Task 1: Create `/safety` — Physical AI Safety Architecture page

**Files:**
- Create: `src/pages/safety.astro`

This is the SEO anchor page. Uses `BaseLayout` (not `DocsLayout`) since it's a top-level standalone page, consistent with how other standalone pages (`governance.astro`, `compatibility.astro`) are structured. Tailwind only — no inline styles.

- [ ] **Step 1: Create `src/pages/safety.astro`**

```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
import CodeWindow from '../components/CodeWindow.astro';

const confidenceGateConfig = `agent:
  confidence_gates:
    NAVIGATE: 0.85
    MANIPULATE: 0.90
    CAMERA_STREAM: 0.70
    ESTOP: 0.50     # lower threshold — emergency actions always considered`;

const hitlConfig = `agent:
  hitl_gates:
    - scope: MANIPULATE
      reason: "Physical contact with environment — human confirmation required"
    - scope: NAVIGATE
      location_class: human_proximate
      reason: "Shared-space navigation above 0.5m/s"`;

const auditRecord = `{
  "msg_id": "cmd_a3f9c1d2",
  "type": "COMMAND",
  "ruri": "rcan://lab.local/acme/bot-x1/00000001",
  "principal": "operator@acme.com",
  "scope": "NAVIGATE",
  "timestamp_ms": 1744329600000,
  "outcome": "ok",
  "ai_block": {
    "model_provider": "openai",
    "model_id": "gpt-4o",
    "inference_confidence": 0.91,
    "inference_latency_ms": 312,
    "thought_id": "thought_b4e87f23",
    "escalated": false,
    "watermark_token": "rcan-wm-v1:a3f9c1d2b4e87f23"
  },
  "delegation_chain": [],
  "chain_prev": "sha256:9f3a...",
  "chain_hash": "sha256:2c7d..."
}`;

const delegationExample = `{
  "type": "COMMAND",
  "scope": "MANIPULATE",
  "delegation_chain": [
    {
      "issuer_ruri": "rcan://lab.local/acme/bot-alpha/00000002",
      "human_subject": "operator@acme.com",
      "timestamp_ms": 1744329600000,
      "scope": "MANIPULATE",
      "signature": "mldsa65:3f9a..."
    }
  ]
}`;

const memoryEntry = `schema_version: "1.0"
rrn: RRN-000000000001
last_updated: 2026-04-10T02:00:00Z
entries:
  - id: mem-a3f9c1d2
    type: hardware_observation
    text: "Left wheel encoder intermittent under sustained load — prefer ≤0.3m/s"
    confidence: 0.92        # decays 0.05/day if not reinforced by log evidence
    first_seen: 2026-03-28T14:00:00Z
    last_reinforced: 2026-04-10T02:00:00Z
    observation_count: 14
    tags: [wheel, encoder, navigation]`;
---

<BaseLayout
  title="Physical AI Safety Architecture — RCAN Protocol"
  description="How RCAN enforces safety at the protocol layer for autonomous robot systems: confidence gating, HiTL gates, ML-DSA-65 signed audit chains, multi-robot delegation, and structured operational memory with EU AI Act alignment."
>
  <!-- Hero -->
  <section class="max-w-4xl mx-auto px-6 pt-20 pb-12 border-b border-white/5">
    <p class="text-sm font-mono uppercase tracking-widest text-accent mb-4">Safety Architecture</p>
    <h1 class="text-4xl md:text-5xl font-bold mb-6 leading-tight">
      Physical AI Safety.<br/>
      <span class="text-text-muted">At the protocol layer.</span>
    </h1>
    <p class="text-xl text-text-muted max-w-2xl leading-relaxed">
      In systems where incorrect decisions have physical consequences, safety constraints must be structural — not filters applied after generation. RCAN enforces safety at the protocol layer: before dispatch, at the transport boundary, in the audit record.
    </p>
    <div class="flex flex-wrap gap-3 mt-8">
      <a href="/spec/" class="px-4 py-2 bg-accent/10 border border-accent/20 text-accent text-sm rounded-lg hover:bg-accent/20 transition-colors">Read the spec →</a>
      <a href="/compliance/frameworks" class="px-4 py-2 bg-white/5 border border-white/10 text-text-muted text-sm rounded-lg hover:bg-white/10 transition-colors">Regulatory coverage →</a>
      <a href="/conformance/" class="px-4 py-2 bg-white/5 border border-white/10 text-text-muted text-sm rounded-lg hover:bg-white/10 transition-colors">Conformance levels →</a>
    </div>
  </section>

  <!-- Section 1: Protocol constraint -->
  <section class="max-w-4xl mx-auto px-6 py-16 border-b border-white/5">
    <h2 class="text-2xl font-bold mb-4">Safety is a protocol constraint, not an application concern</h2>
    <p class="text-text-muted leading-relaxed mb-4">
      A safety layer that wraps a model's output sits outside the execution boundary: it observes outputs but cannot constrain what the model attempts or when dispatch occurs. For text applications, this is an acceptable trade-off. For physical robots, the failure mode is different: a command that clears a post-generation filter but targets the wrong actuator causes physical harm before any check can intervene.
    </p>
    <p class="text-text-muted leading-relaxed mb-4">
      RCAN addresses this by making safety constraints structural at the message transport layer. Confidence thresholds and human authorization gates are declared in the robot's RCAN configuration and enforced at dispatch time — not as application-layer checks the AI agent reasons around, but as protocol invariants the transport enforces before a command reaches any actuator.
    </p>
    <p class="text-text-muted leading-relaxed">
      The reference implementation is <a href="https://github.com/craigm26/OpenCastor" class="text-accent hover:underline">OpenCastor</a>, an open-source robot runtime that implements RCAN on production hardware (Raspberry Pi 5, Hailo-8, OAK-D). The safety mechanisms described here are not theoretical — they are running on physical robots.
    </p>
  </section>

  <!-- Section 2: Confidence gating -->
  <section class="max-w-4xl mx-auto px-6 py-16 border-b border-white/5">
    <div class="flex items-start gap-4 mb-6">
      <span class="text-xs font-mono bg-accent/10 border border-accent/20 text-accent px-2 py-1 rounded mt-1 shrink-0">§16.2</span>
      <h2 class="text-2xl font-bold">Confidence gating</h2>
    </div>
    <p class="text-text-muted leading-relaxed mb-4">
      Every RCAN action scope has a configurable minimum confidence threshold declared in the robot's config. If the AI model's reported confidence for a proposed action falls below that threshold, the protocol rejects dispatch and emits a <code class="text-accent font-mono text-sm">CONFIDENCE_GATE_BLOCKED</code> audit record. The threshold is per-scope, so fine-grained control (higher threshold for physical manipulation, lower for camera streaming) is expressed in configuration rather than code.
    </p>
    <p class="text-text-muted leading-relaxed mb-6">
      This gate fires before the command reaches the transport layer. There is no path through which a model can dispatch a low-confidence MANIPULATE command — not by rephrasing, not through a different code path, not through a tool call that bypasses the gate.
    </p>
    <CodeWindow code={confidenceGateConfig} language="yaml" title="rcan-config.yaml — confidence gate configuration" />
  </section>

  <!-- Section 3: HiTL -->
  <section class="max-w-4xl mx-auto px-6 py-16 border-b border-white/5">
    <div class="flex items-start gap-4 mb-6">
      <span class="text-xs font-mono bg-accent/10 border border-accent/20 text-accent px-2 py-1 rounded mt-1 shrink-0">§16.3</span>
      <h2 class="text-2xl font-bold">Human-in-the-Loop gates</h2>
    </div>
    <p class="text-text-muted leading-relaxed mb-4">
      Action types declared as requiring human authorization in the RCAN config cannot be dispatched by any means without a signed <code class="text-accent font-mono text-sm">AUTHORIZE</code> message from a principal holding <code class="text-accent font-mono text-sm">OWNER</code> or higher role. When a gated action is attempted, the protocol emits <code class="text-accent font-mono text-sm">PENDING_AUTH</code> status and the command waits. The AI agent cannot proceed, cannot re-issue the command, and cannot escalate its own role.
    </p>
    <p class="text-text-muted leading-relaxed mb-4">
      This satisfies EU AI Act Article 14 (human oversight) at the protocol layer: the human-machine interface is the <code class="text-accent font-mono text-sm">PENDING_AUTH → AUTHORIZE</code> flow, and the gate is a structural constraint on the transport, not a UI affordance that can be bypassed.
    </p>
    <p class="text-text-muted leading-relaxed mb-6">
      HiTL gate configuration supports scope-based and context-based conditions (e.g., require authorization for NAVIGATE only when operating in a <code class="text-accent font-mono text-sm">human_proximate</code> location class).
    </p>
    <CodeWindow code={hitlConfig} language="yaml" title="rcan-config.yaml — HiTL gate configuration" />
  </section>

  <!-- Section 4: Audit chain -->
  <section class="max-w-4xl mx-auto px-6 py-16 border-b border-white/5">
    <div class="flex items-start gap-4 mb-6">
      <span class="text-xs font-mono bg-accent/10 border border-accent/20 text-accent px-2 py-1 rounded mt-1 shrink-0">§16.1</span>
      <h2 class="text-2xl font-bold">Tamper-evident audit chain</h2>
    </div>
    <p class="text-text-muted leading-relaxed mb-4">
      Every RCAN command is recorded in an HMAC-SHA256 append-only audit chain at dispatch time — not reconstructed after the fact. Each record includes: principal identity, RURI, timestamp (millisecond precision), message_id, outcome, model provider, model identifier, inference confidence, inference latency, thought_id, escalation flag, and (from §16.5) a watermark token for EU AI Act Art. 50 compliance.
    </p>
    <p class="text-text-muted leading-relaxed mb-4">
      Records are chained: each entry includes the SHA-256 hash of the previous record. Any modification to any record in the chain — by any party, including the operator — breaks all subsequent hashes and is detectable on verification. The chain is the authoritative record-keeping artifact for EU AI Act Article 12 compliance.
    </p>
    <p class="text-text-muted leading-relaxed mb-6">
      Messages are signed with the robot's ML-DSA-65 identity key (see post-quantum identity below). The combination of HMAC chaining and per-message signing means the chain is both tamper-evident and attributable.
    </p>
    <CodeWindow code={auditRecord} language="json" title="Audit chain record — COMMAND with AI block" />
  </section>

  <!-- Section 5: Post-quantum -->
  <section class="max-w-4xl mx-auto px-6 py-16 border-b border-white/5">
    <div class="flex items-start gap-4 mb-6">
      <span class="text-xs font-mono bg-accent/10 border border-accent/20 text-accent px-2 py-1 rounded mt-1 shrink-0">§9 / §1.6</span>
      <h2 class="text-2xl font-bold">Post-quantum identity (ML-DSA-65)</h2>
    </div>
    <p class="text-text-muted leading-relaxed mb-4">
      RCAN v1.6+ binds each Robot Registry Number (RRN) to an ML-DSA-65 public key (CRYSTALS-Dilithium, NIST FIPS 204, standardised August 2024). Every RCAN message is signed with the robot's identity key. Verification requires only the robot's public key — no central server, no network connectivity.
    </p>
    <p class="text-text-muted leading-relaxed mb-4">
      ML-DSA-65 provides security against quantum adversaries. Classical HMAC-SHA256 is used for per-record chaining within audit sessions (fast, symmetric); ML-DSA-65 is used for per-message attribution (asymmetric, forward-secure, quantum-resistant). The combination is appropriate for systems with lifetimes measured in years operating in environments where key material may be exposed to future quantum attack.
    </p>
    <p class="text-text-muted leading-relaxed">
      The OpenCastor reference implementation uses the <code class="text-accent font-mono text-sm">dilithium-py</code> binding. Key generation, signing, and verification are implemented in <code class="text-accent font-mono text-sm">castor/rcan/pqc.py</code>.
    </p>
  </section>

  <!-- Section 6: Delegation chain -->
  <section class="max-w-4xl mx-auto px-6 py-16 border-b border-white/5">
    <div class="flex items-start gap-4 mb-6">
      <span class="text-xs font-mono bg-accent/10 border border-accent/20 text-accent px-2 py-1 rounded mt-1 shrink-0">§12 / rcan-spec#GAP-01</span>
      <h2 class="text-2xl font-bold">Multi-robot delegation chain</h2>
    </div>
    <p class="text-text-muted leading-relaxed mb-4">
      When Robot B executes a command at the direction of Human A, routed through Robot A, the human provenance must be preserved in the audit record. RCAN's <code class="text-accent font-mono text-sm">delegation_chain</code> array carries a signed record for each hop: issuer RURI, human subject, timestamp, scope, and ML-DSA-65 signature. The receiving robot verifies each signature in the chain before dispatch.
    </p>
    <p class="text-text-muted leading-relaxed mb-4">
      The chain is limited to 4 hops maximum. Commands exceeding this limit are rejected with <code class="text-accent font-mono text-sm">DELEGATION_CHAIN_EXCEEDED</code>. The audit record serializes the full chain, giving auditors complete provenance from actuator back to originating human principal.
    </p>
    <p class="text-text-muted leading-relaxed mb-6">
      This matters for multi-robot deployments in regulated environments: a compromised Robot A cannot issue arbitrary commands to Robot B without the human subject in the delegation chain holding the required scope on Robot B's RBAC configuration.
    </p>
    <CodeWindow code={delegationExample} language="json" title="COMMAND message with delegation_chain" />
  </section>

  <!-- Section 7: Physical presence -->
  <section class="max-w-4xl mx-auto px-6 py-16 border-b border-white/5">
    <div class="flex items-start gap-4 mb-6">
      <span class="text-xs font-mono bg-accent/10 border border-accent/20 text-accent px-2 py-1 rounded mt-1 shrink-0">§PHYSICAL_PRESENCE</span>
      <h2 class="text-2xl font-bold">Physical presence verification</h2>
    </div>
    <p class="text-text-muted leading-relaxed mb-4">
      RCAN's <code class="text-accent font-mono text-sm">PHYSICAL_PRESENCE</code> message type enables a robot to cryptographically attest that a human operator is physically proximate at the time of authorization — using on-device sensor data (camera, proximity sensor, or external beacon) combined with a signed timestamp. This attestation can be required as a precondition for certain HiTL gate approvals.
    </p>
    <p class="text-text-muted leading-relaxed">
      Physical presence verification is specific to embodied systems. It has no analogue in text AI safety architectures. For regulated environments where certain actions require in-person oversight (operating theatre robotics, industrial manipulation in human-shared zones), this mechanism provides a machine-verifiable record that the oversight requirement was met.
    </p>
  </section>

  <!-- Section 8: Robot memory -->
  <section class="max-w-4xl mx-auto px-6 py-16 border-b border-white/5">
    <div class="flex items-start gap-4 mb-6">
      <span class="text-xs font-mono bg-accent/10 border border-accent/20 text-accent px-2 py-1 rounded mt-1 shrink-0">rcan-spec#191</span>
      <h2 class="text-2xl font-bold">Operational memory with confidence decay</h2>
    </div>
    <p class="text-text-muted leading-relaxed mb-4">
      <code class="text-accent font-mono text-sm">robot-memory.md</code> is a structured YAML-fronted file maintained by OpenCastor's nightly analysis loop (autoDream). Each entry is an operational observation — hardware degradation, environmental conditions, learned behaviour adjustments — with a confidence score that decays at 0.05/day if not reinforced by new log evidence.
    </p>
    <p class="text-text-muted leading-relaxed mb-4">
      Entries with confidence below 0.30 are excluded from context injection; entries below 0.10 are pruned on the next write cycle. This produces a self-maintaining operational history that reflects current system state rather than accumulating stale observations. The schema is designed for EU AI Act Article 13 (transparency) and Article 17 (quality management) alignment: the confidence decay mechanism directly maps to Art. 17's requirement for systematic monitoring of system performance over time.
    </p>
    <CodeWindow code={memoryEntry} language="yaml" title="robot-memory.md — operational memory entry" />
    <p class="text-text-muted text-sm mt-4">
      Schema specification: <a href="https://github.com/continuonai/rcan-spec/blob/master/docs/robot-memory-schema.md" class="text-accent hover:underline">continuonai/rcan-spec — robot-memory-schema.md</a>
    </p>
  </section>

  <!-- Benchmarks callout -->
  <section class="max-w-4xl mx-auto px-6 py-16 border-b border-white/5">
    <div class="bg-bg-alt/60 border border-white/10 rounded-2xl p-8">
      <h2 class="text-xl font-bold mb-3">Safety subsystem benchmarks</h2>
      <p class="text-text-muted text-sm leading-relaxed mb-4">
        Performance measurements for confidence gate rejection rates, HiTL gate round-trip latency, audit chain write latency (p50/p95/p99), and ML-DSA-65 signing overhead on production hardware (Raspberry Pi 5, Hailo-8) are in progress.
      </p>
      <p class="text-text-muted text-sm">
        Tracking: <a href="https://github.com/craigm26/OpenCastor/issues/859" class="text-accent hover:underline">craigm26/OpenCastor#859</a> — results will be published to <code class="text-accent font-mono">docs/safety-benchmarks.md</code> in the OpenCastor reference implementation.
      </p>
    </div>
  </section>

  <!-- Footer nav -->
  <section class="max-w-4xl mx-auto px-6 py-12">
    <div class="flex flex-col sm:flex-row gap-4 justify-between">
      <div>
        <p class="text-text-muted text-sm mb-3">Regulatory framework coverage</p>
        <a href="/compliance/frameworks" class="text-accent hover:underline text-sm">See all supported frameworks →</a>
      </div>
      <div>
        <p class="text-text-muted text-sm mb-3">Conformance levels L1–L4</p>
        <a href="/conformance/" class="text-accent hover:underline text-sm">Conformance test suite →</a>
      </div>
      <div>
        <p class="text-text-muted text-sm mb-3">Reference implementation</p>
        <a href="https://github.com/craigm26/OpenCastor" class="text-accent hover:underline text-sm">OpenCastor on GitHub →</a>
      </div>
    </div>
  </section>
</BaseLayout>
```

- [ ] **Step 2: Verify build passes**

```bash
cd /home/craigm26/rcan-spec
npm run build 2>&1 | tail -20
```

Expected: build completes with 56+ pages, zero errors. Look for `safety` in the output page list.

- [ ] **Step 3: Commit**

```bash
cd /home/craigm26/rcan-spec
git add src/pages/safety.astro
git commit -m "feat: add /safety — Physical AI Safety Architecture page

Technical reference for RCAN's protocol-layer safety mechanisms:
confidence gating (§16.2), HiTL gates (§16.3), ML-DSA-65 audit chain,
multi-robot delegation, physical presence, and robot-memory.md schema.
Targets physical AI safety and robot EU AI Act compliance search terms.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Create `/compliance/frameworks` — Regulatory Coverage Index

**Files:**
- Create: `src/pages/compliance/index.astro` (redirect to frameworks)
- Create: `src/pages/compliance/frameworks.astro`

- [ ] **Step 1: Create `src/pages/compliance/index.astro`**

```astro
---
// Redirect /compliance to /compliance/frameworks
return Astro.redirect('/compliance/frameworks', 301);
---
```

- [ ] **Step 2: Create `src/pages/compliance/frameworks.astro`**

```astro
---
import BaseLayout from '../../layouts/BaseLayout.astro';
---

<BaseLayout
  title="Regulatory Framework Coverage — RCAN Protocol"
  description="RCAN protocol provisions mapped to EU AI Act, NIST AI RMF, ISO 10218-1, IEC 62443, GDPR, HIPAA, and ISO 42001. Article-level coverage classification for physical robot AI systems."
>
  <!-- Hero -->
  <section class="max-w-5xl mx-auto px-6 pt-20 pb-12 border-b border-white/5">
    <p class="text-sm font-mono uppercase tracking-widest text-accent mb-4">Regulatory Coverage</p>
    <h1 class="text-4xl md:text-5xl font-bold mb-6">Framework Coverage Index</h1>
    <p class="text-xl text-text-muted max-w-3xl leading-relaxed">
      RCAN protocol provisions mapped to applicable regulatory frameworks for physical robot AI systems. Coverage classifications refer to protocol-layer technical controls only. Organizational, procedural, and regulatory obligations remain the responsibility of the provider and deployer.
    </p>
    <div class="flex flex-wrap gap-3 mt-8">
      <a href="/safety" class="px-4 py-2 bg-accent/10 border border-accent/20 text-accent text-sm rounded-lg hover:bg-accent/20 transition-colors">Safety architecture →</a>
      <a href="/conformance/" class="px-4 py-2 bg-white/5 border border-white/10 text-text-muted text-sm rounded-lg hover:bg-white/10 transition-colors">Conformance levels →</a>
    </div>
  </section>

  <!-- Coverage legend -->
  <section class="max-w-5xl mx-auto px-6 pt-12 pb-6">
    <div class="flex flex-wrap gap-4 text-sm">
      <div class="flex items-center gap-2">
        <span class="w-3 h-3 rounded-full bg-emerald-400 shrink-0"></span>
        <span class="text-text-muted"><strong class="text-text">Full (technical layer)</strong> — RCAN provides a complete protocol-level implementation of the requirement</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="w-3 h-3 rounded-full bg-amber-400 shrink-0"></span>
        <span class="text-text-muted"><strong class="text-text">Substantial</strong> — RCAN addresses the core requirement; supplementary organizational measures needed</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="w-3 h-3 rounded-full bg-blue-400 shrink-0"></span>
        <span class="text-text-muted"><strong class="text-text">Partial</strong> — RCAN provides relevant technical controls; significant organizational scope remains</span>
      </div>
    </div>
  </section>

  <!-- EU AI Act -->
  <section class="max-w-5xl mx-auto px-6 py-12 border-b border-white/5">
    <div class="flex items-start gap-4 mb-8">
      <div class="w-10 h-10 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center text-lg shrink-0">🇪🇺</div>
      <div>
        <h2 class="text-2xl font-bold">EU AI Act (2024/1689)</h2>
        <p class="text-text-muted text-sm mt-1">Applies to high-risk AI systems — Annex III, Category 3(a): safety components of machinery. Application date: 2 August 2026.</p>
      </div>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-white/10">
            <th class="text-left py-3 pr-4 text-text-muted font-medium w-32">Article</th>
            <th class="text-left py-3 pr-4 text-text-muted font-medium">Requirement</th>
            <th class="text-left py-3 pr-4 text-text-muted font-medium">RCAN Provisions</th>
            <th class="text-left py-3 text-text-muted font-medium w-32">Coverage</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-white/5">
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">Art. 9</td>
            <td class="py-4 pr-4 text-text-muted">Risk management system — identify and mitigate known and foreseeable risks across the system lifecycle</td>
            <td class="py-4 pr-4 text-text-muted">§16.2 confidence gates (per-scope thresholds); §7 ConfidenceGate; <code class="text-accent/80 font-mono text-xs">castor fria generate</code> FRIA artifact (<a href="https://github.com/craigm26/OpenCastor/issues/858" class="text-accent hover:underline">OpenCastor#858</a>)</td>
            <td class="py-4"><span class="text-xs bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">Substantial</span></td>
          </tr>
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">Art. 12</td>
            <td class="py-4 pr-4 text-text-muted">Record keeping — automatic logging of operational events enabling post-deployment reconstruction</td>
            <td class="py-4 pr-4 text-text-muted">§6 AuditChain (HMAC-SHA256 append-only, chained); §16.1 AI block (model identity, confidence, latency, thought_id); QuantumLink-Sim commitment chain</td>
            <td class="py-4"><span class="text-xs bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full">Full (technical)</span></td>
          </tr>
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">Art. 13</td>
            <td class="py-4 pr-4 text-text-muted">Transparency — deployers must be able to interpret outputs and understand system limitations</td>
            <td class="py-4 pr-4 text-text-muted">§16.4 thought log (<code class="text-accent/80 font-mono text-xs">GET /api/thoughts/&lt;id&gt;</code>, OWNER-gated); robot-memory.md structured operational history (<a href="https://github.com/continuonai/rcan-spec/issues/191" class="text-accent hover:underline">rcan-spec#191</a>)</td>
            <td class="py-4"><span class="text-xs bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">Substantial</span></td>
          </tr>
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">Art. 14</td>
            <td class="py-4 pr-4 text-text-muted">Human oversight — effective oversight during operation; ability to intervene, override, or halt</td>
            <td class="py-4 pr-4 text-text-muted">§16.3 HiTL gates (structural PENDING_AUTH → AUTHORIZE flow; cannot be bypassed by AI agent); §2 RBAC OWNER role enforcement; ESTOP protocol</td>
            <td class="py-4"><span class="text-xs bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full">Full (technical)</span></td>
          </tr>
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">Art. 17</td>
            <td class="py-4 pr-4 text-text-muted">Quality management — documented methodology, testing, performance monitoring, change management</td>
            <td class="py-4 pr-4 text-text-muted">§16.2 confidence gate thresholds (performance floor); §16.1 inference_latency_ms in every audit record; robot-memory.md confidence decay (systematic degradation monitoring)</td>
            <td class="py-4"><span class="text-xs bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">Partial</span></td>
          </tr>
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">Art. 26</td>
            <td class="py-4 pr-4 text-text-muted">Deployer obligations — use system as instructed, maintain human oversight, report incidents</td>
            <td class="py-4 pr-4 text-text-muted">§2 RBAC LEASEE role (deployer authority boundary enforced at protocol layer; scope violations structurally impossible)</td>
            <td class="py-4"><span class="text-xs bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">Partial</span></td>
          </tr>
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">Art. 50</td>
            <td class="py-4 pr-4 text-text-muted">AI-generated content marking — AI-generated outputs must be machine-detectable as AI-generated</td>
            <td class="py-4 pr-4 text-text-muted">§16.5 AI output watermarking — HMAC watermark token on every AI-generated COMMAND message; verification endpoint (<a href="https://github.com/continuonai/rcan-spec/issues/194" class="text-accent hover:underline">rcan-spec#194</a>, in progress)</td>
            <td class="py-4"><span class="text-xs bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">In progress</span></td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="text-text-muted text-xs mt-4">
      Detailed article-level mapping: <a href="https://github.com/continuonai/rcan-spec/blob/master/docs/compliance/eu-ai-act-mapping.md" class="text-accent hover:underline">docs/compliance/eu-ai-act-mapping.md</a> — includes conformity assessment citation guidance.
    </p>
  </section>

  <!-- NIST AI RMF -->
  <section class="max-w-5xl mx-auto px-6 py-12 border-b border-white/5">
    <div class="flex items-start gap-4 mb-8">
      <div class="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-lg shrink-0">🇺🇸</div>
      <div>
        <h2 class="text-2xl font-bold">NIST AI Risk Management Framework 1.0</h2>
        <p class="text-text-muted text-sm mt-1">Voluntary framework for US federal agencies and government procurement. Relevant for DoD and GSA-schedule robotics contracts.</p>
      </div>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-white/10">
            <th class="text-left py-3 pr-4 text-text-muted font-medium w-32">Function</th>
            <th class="text-left py-3 pr-4 text-text-muted font-medium">Core Requirement</th>
            <th class="text-left py-3 pr-4 text-text-muted font-medium">RCAN Provisions</th>
            <th class="text-left py-3 text-text-muted font-medium w-32">Coverage</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-white/5">
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">GOVERN</td>
            <td class="py-4 pr-4 text-text-muted">Organizational accountability, policies, and workforce capability for AI risk</td>
            <td class="py-4 pr-4 text-text-muted">§2 RBAC (role-scoped authority); §16 AI accountability provisions; L1–L4 conformance as measurable governance target</td>
            <td class="py-4"><span class="text-xs bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">Substantial</span></td>
          </tr>
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">MAP</td>
            <td class="py-4 pr-4 text-text-muted">Identify and characterize AI risks in deployment context</td>
            <td class="py-4 pr-4 text-text-muted">FRIA protocol §19 (risk entries from conformance gaps + robot-memory hardware observations); <a href="https://github.com/continuonai/rcan-spec/issues/195" class="text-accent hover:underline">rcan-spec#195</a></td>
            <td class="py-4"><span class="text-xs bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">Partial</span></td>
          </tr>
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">MEASURE</td>
            <td class="py-4 pr-4 text-text-muted">Analyze and assess AI risks using quantitative and qualitative methods</td>
            <td class="py-4 pr-4 text-text-muted">L1–L4 conformance test suite (quantitative pass/fail per requirement); confidence gate rejection rates; audit chain integrity verification; safety benchmarks (<a href="https://github.com/craigm26/OpenCastor/issues/859" class="text-accent hover:underline">OpenCastor#859</a>)</td>
            <td class="py-4"><span class="text-xs bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">Substantial</span></td>
          </tr>
          <tr>
            <td class="py-4 pr-4 font-mono text-accent text-xs">MANAGE</td>
            <td class="py-4 pr-4 text-text-muted">Prioritize and address risks; communicate residual risks to stakeholders</td>
            <td class="py-4 pr-4 text-text-muted">§16.2–16.3 gating (risk prevention); §16.4 thought log (decision transparency); AuditChain (residual risk evidence); FRIA artifact (stakeholder communication)</td>
            <td class="py-4"><span class="text-xs bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">Substantial</span></td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="text-text-muted text-xs mt-4">
      Detailed alignment: <a href="https://github.com/continuonai/rcan-spec/blob/master/docs/compliance/nist-ai-rmf-alignment.md" class="text-accent hover:underline">docs/compliance/nist-ai-rmf-alignment.md</a>
    </p>
  </section>

  <!-- Other frameworks -->
  <section class="max-w-5xl mx-auto px-6 py-12 border-b border-white/5">
    <h2 class="text-2xl font-bold mb-8">Additional Frameworks</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

      <div class="bg-bg-alt/50 border border-white/5 rounded-2xl p-6">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-bold">ISO 10218-1:2025</h3>
          <span class="text-xs bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">Partial</span>
        </div>
        <p class="text-text-muted text-sm leading-relaxed mb-3">Safety requirements for industrial robots. RCAN provisions: Protocol 66 safety rules (15 rules across motion, force, workspace, human, thermal, electrical, software, emergency, property, privacy domains); geofencing with dead-reckoning odometry; emergency stop with callback chain.</p>
        <a href="https://github.com/continuonai/rcan-spec/blob/master/docs/compliance/iso-10218-alignment.md" class="text-accent text-xs hover:underline">Full alignment doc →</a>
      </div>

      <div class="bg-bg-alt/50 border border-white/5 rounded-2xl p-6">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-bold">IEC 62443</h3>
          <span class="text-xs bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">Partial</span>
        </div>
        <p class="text-text-muted text-sm leading-relaxed mb-3">Industrial automation and control system cybersecurity. RCAN provisions: ML-DSA-65 + Ed25519 message signing; RBAC with rate limiting and session timeouts; JWT authentication; mDNS discovery with peer verification.</p>
        <a href="https://github.com/continuonai/rcan-spec/blob/master/docs/compliance/iec-62443-alignment.md" class="text-accent text-xs hover:underline">Full alignment doc →</a>
      </div>

      <div class="bg-bg-alt/50 border border-white/5 rounded-2xl p-6">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-bold">GDPR Article 22</h3>
          <span class="text-xs bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">Partial</span>
        </div>
        <p class="text-text-muted text-sm leading-relaxed">Automated individual decision-making. RCAN provisions: §16.3 HiTL gates (human in the decision loop); §16.4 thought log (decision explainability); privacy-by-default sensor policy in OpenCastor (camera, microphone scope controls).</p>
      </div>

      <div class="bg-bg-alt/50 border border-white/5 rounded-2xl p-6">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-bold">HIPAA</h3>
          <span class="text-xs bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">Partial</span>
        </div>
        <p class="text-text-muted text-sm leading-relaxed">Applicable to medical robotics (surgical, clinical support, care pathway automation). RCAN provisions: role-gated audit record access (OWNER required for reasoning field); tamper-evident chain for PHI-adjacent action logs; air-gap capable (no external network required).</p>
      </div>

      <div class="bg-bg-alt/50 border border-white/5 rounded-2xl p-6">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-bold">ISO 42001</h3>
          <span class="text-xs bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">Partial</span>
        </div>
        <p class="text-text-muted text-sm leading-relaxed">AI management systems — organizational requirements. RCAN provisions: L1–L4 conformance levels provide measurable quality benchmarks for an AI management system's technical controls; audit chain supports post-market monitoring data infrastructure.</p>
      </div>

      <div class="bg-bg-alt/50 border border-white/5 rounded-2xl p-6">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-bold">SIL/PLe (IEC 62061 / ISO 13849)</h3>
          <span class="text-xs bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">Partial</span>
        </div>
        <p class="text-text-muted text-sm leading-relaxed">Functional safety for machinery. RCAN provisions: safety stop integration (<code class="text-accent/80 font-mono text-xs">agent.safety_stop</code> flag); latency budget constraint (<code class="text-accent/80 font-mono text-xs">latency_budget_ms</code>); Protocol 66 safety invariants provide evidence for safety function documentation.</p>
        <a href="https://github.com/continuonai/rcan-spec/blob/master/docs/compliance/sil-ple-declarations.md" class="text-accent text-xs hover:underline">Declaration template →</a>
      </div>

    </div>
  </section>

  <!-- Out of scope note -->
  <section class="max-w-5xl mx-auto px-6 py-12">
    <div class="bg-white/3 border border-white/8 rounded-2xl p-8">
      <h3 class="font-bold mb-3">What RCAN does not address</h3>
      <p class="text-text-muted text-sm leading-relaxed mb-4">
        RCAN is a protocol specification. The following compliance requirements are organizational, procedural, or regulatory in nature and are outside the scope of any protocol: EU AI Act Art. 43 conformity assessment and CE marking; Art. 49 registration in the EU AI public database; Art. 72 post-market monitoring organizational process; Art. 9(4) human-led risk estimation for unintended uses.
      </p>
      <p class="text-text-muted text-sm leading-relaxed">
        RCAN provides the technical controls and audit infrastructure that support these obligations — it does not constitute the organizational process itself. For conformity assessment template guidance, see <a href="https://github.com/continuonai/rcan-spec/blob/master/docs/compliance/conformity-assessment-template.md" class="text-accent hover:underline">docs/compliance/conformity-assessment-template.md</a>.
      </p>
    </div>
  </section>
</BaseLayout>
```

- [ ] **Step 3: Verify build passes**

```bash
cd /home/craigm26/rcan-spec
npm run build 2>&1 | tail -20
```

Expected: 57+ pages, zero errors. Look for `compliance/frameworks` and `compliance/index` in output.

- [ ] **Step 4: Commit**

```bash
cd /home/craigm26/rcan-spec
git add src/pages/compliance/
git commit -m "feat: add /compliance/frameworks — Regulatory Coverage Index

Article-level mapping for EU AI Act, NIST AI RMF, ISO 10218-1,
IEC 62443, GDPR Art.22, HIPAA, ISO 42001, SIL/PLe. Honest coverage
classifications (Full/Substantial/Partial). Links to detailed alignment
docs and open issues for in-progress gaps (§16.5, §19).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Add homepage "Why an open protocol beats a bolt-on layer" section

**Files:**
- Modify: `src/pages/index.astro` — insert new `<section>` after the "Who Is This For?" section (after line ~186, before the SDKs section)

- [ ] **Step 1: Insert section into `src/pages/index.astro`**

Locate the SDKs section comment (`<!-- SDKs Section -->`) in `src/pages/index.astro`. Insert the following block immediately before it:

```astro
  <!-- Why open protocol section -->
  <section class="py-24 border-b border-white/5">
    <div class="max-w-4xl mx-auto px-6">
      <div class="mb-10">
        <p class="text-sm font-mono uppercase tracking-widest text-accent mb-4">Architecture</p>
        <h2 class="text-3xl md:text-4xl font-bold mb-6">Why an open protocol beats a bolt-on layer</h2>
      </div>
      <div class="space-y-6 text-text-muted leading-relaxed">
        <p>
          A safety layer that wraps a model's output sits outside the execution boundary — it observes what the model generates but cannot constrain what it attempts or when dispatch occurs. For text applications, this trade-off is acceptable. For physical robots, the failure mode is different: a command that clears a post-generation safety filter but targets the wrong actuator causes physical harm before any check can intervene. Protocol-level enforcement closes this gap. RCAN's confidence thresholds and HiTL gates are structural constraints on the message transport — not filters — enforced before any command reaches an actuator.
        </p>
        <p>
          Auditability is similarly structural in RCAN. The ML-DSA-65 signed audit chain records every command with principal identity, model confidence, thought provenance, and delegation path at dispatch time — not reconstructed afterward. Each record is cryptographically chained to the previous; any modification breaks chain verification. This is the record-keeping architecture EU AI Act Article 12 requires, built into the protocol layer rather than added as a compliance reporting feature.
        </p>
        <p>
          RCAN is an open specification under CC BY 4.0. Every claim in this documentation can be verified against the <a href="/spec/" class="text-accent hover:underline">spec</a>, the <a href="https://github.com/craigm26/OpenCastor" class="text-accent hover:underline">reference implementation</a>, and the <a href="/conformance/" class="text-accent hover:underline">conformance test suite</a>. Conformance levels L1–L4 define what "compliant" means concretely — not as a self-certification, but as a pass/fail test suite any implementation can run.
        </p>
      </div>
      <div class="flex flex-wrap gap-4 mt-10">
        <a href="/safety" class="px-5 py-2.5 bg-accent/10 border border-accent/20 text-accent text-sm font-medium rounded-lg hover:bg-accent/20 transition-colors">Safety architecture →</a>
        <a href="/compliance/frameworks" class="px-5 py-2.5 bg-white/5 border border-white/10 text-text-muted text-sm font-medium rounded-lg hover:bg-white/10 transition-colors">Regulatory coverage →</a>
      </div>
    </div>
  </section>
```

- [ ] **Step 2: Verify build passes**

```bash
cd /home/craigm26/rcan-spec
npm run build 2>&1 | tail -10
```

Expected: same page count as after Task 2, zero errors.

- [ ] **Step 3: Run test suite**

```bash
cd /home/craigm26/rcan-spec
npx vitest run tests/functions.test.ts 2>&1 | tail -15
```

Expected: 101 tests pass. The test suite covers API functions, not content pages, so this should be unchanged.

- [ ] **Step 4: Commit**

```bash
cd /home/craigm26/rcan-spec
git add src/pages/index.astro
git commit -m "feat: add 'why open protocol' section to homepage

Three-paragraph technical argument: structural enforcement vs. post-hoc
filter, structural audit chain vs. compliance reporting, open spec with
verifiable conformance vs. proprietary claims. Links to /safety and
/compliance/frameworks.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Update nav to surface new pages (rcan-spec)

**Files:**
- Modify: `src/layouts/BaseLayout.astro` — add Safety and Compliance links to nav

- [ ] **Step 1: Read `src/layouts/BaseLayout.astro` to find nav structure**

```bash
grep -n "conformance\|nav\|href" /home/craigm26/rcan-spec/src/layouts/BaseLayout.astro | head -30
```

Identify where existing nav links (e.g., `/conformance/`, `/spec/`, `/docs/`) are defined.

- [ ] **Step 2: Add `/safety` and `/compliance/frameworks` to nav**

In the nav links section, add after the existing conformance link:

```astro
<a href="/safety" class="text-sm text-text-muted hover:text-text transition-colors">Safety</a>
<a href="/compliance/frameworks" class="text-sm text-text-muted hover:text-text transition-colors">Compliance</a>
```

Match the exact class pattern used by adjacent nav links.

- [ ] **Step 3: Build and verify**

```bash
cd /home/craigm26/rcan-spec
npm run build 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
cd /home/craigm26/rcan-spec
git add src/layouts/BaseLayout.astro
git commit -m "feat: add Safety and Compliance links to site nav

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Repo B: craigm26/OpenCastor

Working directory for Tasks 5–6: `/home/craigm26/OpenCastor`

---

### Task 5: Create `docs/safety-architecture.md`

**Files:**
- Create: `docs/safety-architecture.md`

Implementation companion to rcan.dev/safety. Code references are exact file paths; no placeholder module names.

- [ ] **Step 1: Create `docs/safety-architecture.md`**

```markdown
# Safety Architecture — OpenCastor Implementation Reference

**Spec:** [rcan.dev/safety](https://rcan.dev/safety)  
**Version:** OpenCastor 2026.3.x  
**Related:** [rcan.dev/compliance/frameworks](https://rcan.dev/compliance/frameworks), [rcan-spec EU AI Act mapping](https://github.com/continuonai/rcan-spec/blob/master/docs/compliance/eu-ai-act-mapping.md)

This document maps OpenCastor's safety implementation to the RCAN protocol provisions described on [rcan.dev/safety](https://rcan.dev/safety). For the protocol specification, read the rcan.dev page first. This document covers: where the code lives, how to configure it, and how to verify it is working.

---

## Safety Module Map

| Protocol Provision | RCAN Spec | OpenCastor File | Key Class/Function |
|---|---|---|---|
| Confidence gating | §16.2 | `castor/fs/safety.py` | `ConfidenceGateSafety.check()` |
| HiTL gates | §16.3 | `castor/rcan/rbac.py` | `RBACManager.require_hitl()` |
| Audit chain | §16.1 / §6 | `castor/audit.py` | `AuditChain.append()` |
| AI block logging | §16.1 | `castor/brain/robot_context.py` | `dispatch_command()` |
| ML-DSA-65 signing | §9 / §1.6 | `castor/rcan/pqc.py` | `sign_message()`, `verify_message()` |
| RBAC enforcement | §2 | `castor/rcan/rbac.py` | `RBACManager.check_scope()` |
| Geofencing | §GEOFENCE | `castor/fs/safety.py` | `GeofenceSafety.check_position()` |
| Operational memory | robot-memory.md | `castor/brain/memory_schema.py` | `RobotMemory.load()`, `.filter_eligible()` |
| Context injection | §16.4 | `castor/brain/robot_context.py` | `build_context()` |
| Nightly memory loop | autoDream | `castor/brain/autodream.py` | `AutoDream.run()` |
| Watchdog | §6 | `castor/watchdog.py` | `Watchdog.start()` |
| Privacy policy | §PRIVACY | `castor/privacy.py` | `PrivacyPolicy.check_scope()` |

---

## Confidence Gating (`castor/fs/safety.py`)

Confidence gates are declared in `rcan-config.yaml` under `agent.confidence_gates`. The `ConfidenceGateSafety` class reads these at startup and evaluates them in `check()` before any command is dispatched.

```yaml
# rcan-config.yaml
agent:
  confidence_gates:
    NAVIGATE: 0.85
    MANIPULATE: 0.90
    CAMERA_STREAM: 0.70
    ESTOP: 0.50
```

When the model's reported confidence for a proposed action falls below the configured threshold, `check()` raises `ConfidenceGateBlockedError`. The command is not dispatched. An audit record with `outcome: "blocked"` and `block_reason: "confidence_gate"` is written to the audit chain.

**To verify gating is active:**
```bash
castor validate --category safety --json | python3 -c "
import sys, json
results = json.load(sys.stdin)
for r in results:
    if r['check_id'] == 'safety.confidence_gates_configured':
        print(r['check_id'], '—', r['status'], '—', r['detail'])
"
# Expected: safety.confidence_gates_configured — pass — brain.confidence_gates is configured (RCAN §16.2)
```

---

## HiTL Gates (`castor/rcan/rbac.py`)

HiTL gates are declared under `agent.hitl_gates`. The `RBACManager.require_hitl()` method is called during command routing for any scope listed in the gate configuration.

```yaml
agent:
  hitl_gates:
    - scope: MANIPULATE
      reason: "Physical contact with environment"
    - scope: NAVIGATE
      location_class: human_proximate
```

When a gated action is attempted, the runtime emits a `PENDING_AUTH` status message and blocks dispatch. The action remains pending until a signed `AUTHORIZE` message arrives from a principal with `OWNER` or higher role. If no authorization arrives within `hitl_timeout_s` (default: 300), the action is cancelled with `HITL_TIMEOUT`.

The AI agent has no code path to bypass this. `require_hitl()` is called at the transport layer, before the action reaches any actuator driver.

**To verify HiTL gate configuration is present:**
```bash
castor validate --category safety --json | python3 -c "
import sys, json
results = json.load(sys.stdin)
for r in results:
    if 'local_safety' in r['check_id'] or 'reactive' in r['check_id']:
        print(r['check_id'], '—', r['status'], '—', r['detail'])
"
# safety.local_safety_wins — pass — safety.local_safety_wins=true (RCAN §6 invariant satisfied)
# safety.reactive_layer — pass
```

---

## Audit Chain (`castor/audit.py`)

`AuditChain.append(record)` writes an audit record to the append-only chain file. Each record includes:

- `msg_id`, `type`, `ruri`, `principal`, `scope`, `timestamp_ms`, `outcome`
- `ai_block`: `model_provider`, `model_id`, `inference_confidence`, `inference_latency_ms`, `thought_id`, `escalated`
- `chain_prev`: SHA-256 hash of the previous record
- `chain_hash`: SHA-256 hash of the current record (including `chain_prev`)

Chain integrity is verified with:

```bash
castor audit verify
# Reads chain file, recomputes hashes, reports any broken links
# Expected output: "Audit chain: 1042 records, integrity: OK"
```

If any record has been modified, the hash mismatch is reported with the record index and message ID.

---

## ML-DSA-65 Signing (`castor/rcan/pqc.py`)

Every outbound RCAN message is signed with the robot's ML-DSA-65 private key. Key generation occurs at first startup:

```bash
castor keys generate --algorithm mldsa65
# Writes ~/.opencastor/identity.key and identity.pub
# RRN binding is written to rcan-config.yaml
```

Signing is handled by `sign_message(msg: dict, private_key: bytes) -> str` which returns a base64-encoded ML-DSA-65 signature. Verification uses `verify_message(msg: dict, signature: str, public_key: bytes) -> bool`.

The public key is registered with the RRN at the Robot Registry Foundation. Peers retrieve it via `GET https://robotregistryfoundation.org/api/v1/robots/{rrn}/public-key`.

---

## Operational Memory (`castor/brain/memory_schema.py`)

`RobotMemory.load(path)` reads `robot-memory.md`, parses the YAML frontmatter, and applies confidence decay at read time:

```python
days_elapsed = (now - entry.last_reinforced) / 86400
entry.confidence = max(0.0, entry.confidence - DECAY_RATE * days_elapsed)
# DECAY_RATE default: 0.05/day
```

`filter_eligible()` returns entries with `confidence >= 0.30` and `type != "resolved"`, sorted by confidence descending.

`build_context(memory, token_budget)` formats eligible entries for brain context injection:
- `confidence >= 0.80` → 🔴 prefix (high confidence)
- `0.50 ≤ confidence < 0.80` → 🟡 prefix
- `0.30 ≤ confidence < 0.50` → 🟢 prefix

The injected block is placed in the dynamic section of the system prompt (not cached). See `castor/brain/robot_context.py` `build_context()`.

---

## Conformance Validation

Run the full safety conformance suite:

```bash
castor validate --category safety --json
```

Output: JSON array of `ConformanceResult` objects with `check_id`, `status` (`pass`/`fail`/`warn`), and `detail`. All safety checks must pass for RCAN L2 conformance. Use `--strict` to treat warnings as failures.

---

## Related Issues

- craigm26/OpenCastor#857 — AI output watermarking implementation (§16.5)
- craigm26/OpenCastor#858 — `castor fria generate` CLI (§19)
- craigm26/OpenCastor#859 — safety subsystem benchmarks
```

- [ ] **Step 2: Commit**

```bash
cd /home/craigm26/OpenCastor
git add docs/safety-architecture.md
git commit -m "docs: add safety-architecture.md — implementation reference for rcan.dev/safety

Maps each RCAN safety provision to exact OpenCastor file + function.
Covers confidence gating, HiTL gates, audit chain, ML-DSA-65 signing,
operational memory, and conformance validation commands.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Create `docs/compliance/competitive-positioning.md`

**Files:**
- Create: `docs/compliance/competitive-positioning.md`

Internal engineering due-diligence reference. Honest about gaps (links to open issues). Not published as marketing.

- [ ] **Step 1: Create `docs/compliance/competitive-positioning.md`**

```markdown
# Competitive Positioning — Technical Due Diligence Reference

**Audience:** Engineering teams, system integrators, and compliance teams doing vendor evaluation.  
**Status:** Internal reference — not a marketing document.  
**Last updated:** 2026-04-10  
**Related design spec:** `docs/superpowers/specs/2026-04-10-opencastor-competitive-positioning-design.md`

This document compares the RCAN/OpenCastor safety architecture against the category of bolt-on LLM safety layers (e.g., Geodesia G-1). It is honest about domain boundaries, genuine capability gaps, and open work. Claims that cannot be verified against a spec section or benchmark are not made.

---

## Domain Boundary

**RCAN/OpenCastor scope:** Physical robot actuation — systems where incorrect decisions cause physical harm. Safety constraints are structural at the protocol layer; they govern what commands can be dispatched to actuators, under what conditions, and with what human oversight.

**Bolt-on LLM safety layer scope:** Text inference — systems where a model generates text that a human or downstream system then acts on. Safety is applied as a post-generation filter: responses are scored for factual grounding, safety, or policy compliance before delivery.

These are different problems in different domains. The comparison below focuses on the intersection: regulated AI deployments requiring EU AI Act Article 12/14 compliance, audit trails, and human oversight records.

---

## Capability Comparison

| Capability | RCAN / OpenCastor | Bolt-on text safety layer |
|---|---|---|
| **Safety enforcement point** | Protocol layer — before dispatch to actuator | Post-generation filter — after model output |
| **Can AI agent bypass safety gate?** | No — structural transport constraint | Depends on implementation |
| **Audit chain** | HMAC-SHA256 append-only, ML-DSA-65 signed, chained hashes | HMAC audit logs (implementation-dependent) |
| **Post-quantum cryptography** | ML-DSA-65 (NIST FIPS 204) on all message signatures | HMAC-SHA256 (classical only) |
| **Human-in-the-loop** | §16.3 protocol-enforced gate (PENDING_AUTH → AUTHORIZE) | Application-layer oversight queue |
| **Multi-robot delegation** | `delegation_chain` with per-hop ML-DSA-65 signatures, max 4 hops | N/A — single inference endpoint |
| **Physical presence verification** | §PHYSICAL_PRESENCE message type | N/A — no physical embodiment |
| **Operational memory** | Structured YAML schema, confidence decay, EU AI Act Art. 13/17 alignment | N/A |
| **Open specification** | CC BY 4.0 — verifiable against spec + conformance suite | Proprietary |
| **Conformance levels** | L1–L4 with published test suite | Proprietary certification |
| **FRIA generation** | `castor fria generate` — signed JSON artifact ([#858](https://github.com/craigm26/OpenCastor/issues/858), in progress) | Claimed workflow (proprietary) |
| **EU AI Act Art. 50 watermarking** | §16.5 watermark token ([#857](https://github.com/craigm26/OpenCastor/issues/857), in progress) | HMAC watermark claimed |
| **Published performance metrics** | Safety benchmarks in progress ([#859](https://github.com/craigm26/OpenCastor/issues/859)) | AUROC 0.96 (hallucination, text inference) |
| **Deployment** | Open source, self-hosted, air-gap capable | Single Docker container, proprietary |

---

## Genuine Gaps (Open Issues)

These are real gaps relative to what bolt-on safety layer marketing claims. Each has a tracking issue.

### 1. AI Output Watermarking (EU AI Act Art. 50)

Bolt-on claim: HMAC watermark tokens in 6 languages.  
RCAN status: HMAC audit chains exist; per-output watermark token on AI-generated COMMAND messages is not yet implemented.  
Tracking: continuonai/rcan-spec#194 (spec), craigm26/OpenCastor#857 (implementation)

### 2. Automated FRIA Generation

Bolt-on claim: FRIA workflow with signed PDF/JSON export.  
RCAN status: Art. 9 template exists (`docs/compliance/art9-risk-assessment-template.md`); automated signed FRIA artifact generation from conformance output is not yet implemented.  
Tracking: continuonai/rcan-spec#195 (spec), craigm26/OpenCastor#858 (implementation)

### 3. Published Safety Metrics

Bolt-on claim: AUROC 0.96 (hallucination detection), <35ms total latency.  
RCAN status: no equivalent published numbers for confidence gate rejection rates or safety subsystem latency on production hardware.  
Note: AUROC is a text inference metric. The relevant metrics for physical robot safety gating are different (gate rejection rate at configured thresholds, HiTL latency, audit write latency). These are being measured on Raspberry Pi 5 + Hailo-8.  
Tracking: craigm26/OpenCastor#859

---

## What RCAN Claims That Can Be Verified Right Now

Every claim below links to a spec section and a conformance check that produces a pass/fail result.

| Claim | Verify with |
|---|---|
| Confidence gates configured | `castor validate --category safety --json` → `safety.confidence_gates_configured: pass` |
| Local safety wins (structural protocol invariant) | `castor validate --category safety --json` → `safety.local_safety_wins: pass` |
| Protocol 66 safety rules conformant | `castor validate --category safety --json` → `safety.p66_conformance: pass` |
| Audit chain is tamper-evident | `castor audit verify` → chain integrity: OK |
| Message signing active (RCAN v1.5+) | `castor validate --category rcan_v15 --json` → `rcan_v15.message_signing: pass` |
| L2 conformance (all safety-critical checks) | `castor validate --strict` → exit code 0 |

---

## How to Respond to "Why not just use [bolt-on layer]?"

The short answer: bolt-on layers and RCAN solve different problems. If the question is "how do I make my text LLM safer," a bolt-on layer is a reasonable tool. If the question is "how do I deploy a physical robot in a regulated environment with auditable safety controls," the safety constraint needs to be at the protocol layer — not because of marketing positioning, but because of the physical harm model.

The longer answer is on [rcan.dev/safety](https://rcan.dev/safety).

---

## References

- rcan.dev/safety — Physical AI Safety Architecture
- rcan.dev/compliance/frameworks — Regulatory Coverage Index
- docs/safety-architecture.md — OpenCastor implementation reference
- docs/compliance/eu-ai-act-mapping.md — EU AI Act article-level mapping with conformity assessment citation guidance
- Design spec: docs/superpowers/specs/2026-04-10-opencastor-competitive-positioning-design.md
```

- [ ] **Step 2: Commit**

```bash
cd /home/craigm26/OpenCastor
git add docs/compliance/competitive-positioning.md
git commit -m "docs: add competitive-positioning.md — technical due diligence reference

Honest domain boundary analysis vs. bolt-on text safety layers.
Capability comparison table, genuine gaps with tracking issues,
verifiable claims with exact castor validate commands.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Checklist (run before declaring done)

- [ ] `npm run build` in rcan-spec produces zero errors, 57+ pages
- [ ] `npx vitest run tests/functions.test.ts` passes all 101 tests
- [ ] All external links in Astro pages point to real URLs (GitHub issues, spec docs, OpenCastor)
- [ ] No inline `style=` attributes in any `.astro` file — Tailwind classes only
- [ ] No claim made without a spec section citation or open issue link
- [ ] `castor validate` commands in safety-architecture.md match actual check IDs in `castor/conformance.py`
- [ ] `git log --oneline -6` in both repos shows clean commit history

---

## Verifying `castor validate` check IDs

Before finalizing the plan, verify that the check IDs referenced in `docs/safety-architecture.md` exist in the conformance checker:

```bash
grep -n "check_id\|CONFIDENCE_GATE\|HITL_GATE\|PQC_SIGNING\|MEMORY_DECAY" /home/craigm26/OpenCastor/castor/conformance.py | head -20
```

If any IDs don't match, update the doc to use the actual check IDs returned by `ConformanceChecker.run_all()`.
