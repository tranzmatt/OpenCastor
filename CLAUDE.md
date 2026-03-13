# CLAUDE.md — OpenCastor Development Guide

> **Agent context file.** Read this before making any changes. Keep it up to date.

## What Is OpenCastor?

OpenCastor is the open-source **reference implementation of the RCAN protocol** (v1.4). It connects LLM "brains" to robot "bodies" through a plug-and-play architecture and exposes them to messaging platforms for remote control.

- **Version**: 2026.3.13.11 (date-based: `YYYY.MM.DD.patch`)
- **RCAN**: v1.4 — see [rcan.dev/spec](https://rcan.dev/spec/)
- **License**: Apache 2.0 | **Python**: 3.10+ | **Tests**: 105+ passing

## Quick Start

```bash
git clone https://github.com/craigm26/OpenCastor.git
cd OpenCastor
pip install -e ".[channels]"
cp .env.example .env
castor wizard        # interactive setup
castor gateway       # start API gateway
```

## Repository Layout

```
OpenCastor/
├── castor/                 # Core runtime
│   ├── api.py              # FastAPI gateway (main entry point)
│   ├── tiered_brain.py     # TieredBrain: fast/planner routing by task_category
│   ├── providers/          # LLM adapters (Gemini, Claude, GPT, Ollama, ...)
│   │   ├── task_router.py  # TaskRouter — routes tasks by category to providers
│   │   └── base.py         # BaseProvider ABC + Thought dataclass
│   ├── drivers/            # Hardware drivers (PCA9685, Dynamixel, ROS2, ...)
│   ├── channels/           # Messaging channels (WhatsApp, Telegram, Discord, ...)
│   ├── rcan/               # RCAN protocol implementation
│   │   ├── registry.py     # RRN validation, REGISTRY_REGISTER/RESOLVE (§21)
│   │   ├── invoke.py       # InvokeRequest/Result, SkillRegistry (§19)
│   │   ├── parallel_invoke.py  # invoke_all(), invoke_race()
│   │   ├── message.py      # MessageType enum, RCANMessage
│   │   └── sdk_compat.py   # Compatibility layer for rcan-py SDK
│   ├── fleet/              # Fleet management, group policies
│   ├── privacy_mode.py     # Privacy mode — blocks cloud egress
│   └── sdk/                # Python SDK wrapper
├── sdk/js/                 # TypeScript/JS SDK (@opencastor/sdk)
│   └── src/index.ts        # CastorClient — typed wrappers for all API endpoints
├── site/                   # OpenCastor website (static HTML/CSS)
│   ├── *.html              # 8 pages (index, docs, hardware, about, hub, ...)
│   └── styles.css          # Global stylesheet (dark/light theme, pill toggles)
├── tests/                  # Test suite (pytest)
├── config/presets/         # RCAN config presets for common hardware
├── bob.rcan.yaml           # Bob robot config (gitignored — device-specific)
└── CHANGELOG.md            # Version history
```

## Key Abstractions

| Class | File | What it does |
|---|---|---|
| `TieredBrain` | `castor/tiered_brain.py` | Routes prompts: fast model or planner based on `task_category` |
| `TaskRouter` | `castor/providers/task_router.py` | Selects provider by `TaskCategory` (SENSOR_POLL → local-only, SAFETY → planner) |
| `BaseProvider` | `castor/providers/base.py` | LLM adapter ABC: `think()`, `think_stream()`, `health_check()` |
| `DriverBase` | `castor/drivers/base.py` | Hardware ABC: `move()`, `stop()`, `close()`, `health_check()` |
| `RegistryMessage` | `castor/rcan/registry.py` | RCAN §21 wire message. `RRNCategory` enum, `_validate_rrn()`, `metadata` block |
| `InvokeRequest` | `castor/rcan/invoke.py` | §19 INVOKE — skill name + params + timeout |
| `SkillRegistry` | `castor/rcan/invoke.py` | Maps skill names to handler callables |
| `FleetManager` | `castor/fleet/group_policy.py` | Group policies, config deep-merge |
| `CastorClient` | `sdk/js/src/index.ts` | TypeScript SDK — `invoke()`, `invokeAll()`, `invokeRace()`, `registryRegister()`, `registryResolve()` |

## RCAN Protocol (v1.4)

OpenCastor implements **RCAN v1.4** full stack:

### MessageTypes
```python
DISCOVER = 1       # Robot announces presence
STATUS = 2         # Health/state query
COMMAND = 3        # Action instruction
STREAM = 4         # Continuous data stream
EVENT = 5          # Triggered state change
HANDOFF = 6        # Session transfer
ACK = 7            # Acknowledgment
ERROR = 8          # Error response
AUTHORIZE = 9      # HiTL approval (§8)
PENDING_AUTH = 10  # HiTL gate awaiting (§8)
INVOKE = 11        # Skill invocation (§19)
INVOKE_RESULT = 12 # Skill result (§19)
REGISTRY_REGISTER = 13    # Register with RRF (§21)
REGISTRY_RESOLVE = 14     # Resolve RRN→RURI (§21)
INVOKE_CANCEL = 15        # Cancel in-flight INVOKE (§19)
REGISTRY_REGISTER_RESULT = 16  # Registration result (§21)
REGISTRY_RESOLVE_RESULT = 17   # Resolution result (§21)
```

### Robot Registration Numbers (RRN)
Two formats, both accepted by `_validate_rrn()`:
```
RRN-000000000001                           # numeric (12 digits, RRF-assigned)
rrn://org/category/model/id               # URI 4-segment (recommended)
rrn://org/category/id                     # URI 3-segment
rrn://org/id                              # URI legacy 2-segment (category=robot)
```
Valid categories: `robot` | `component` | `sensor` | `assembly`

### Task Categories (TieredBrain routing)
```python
SENSOR_POLL  → fast model only (never escalates to planner — token budget guard)
NAVIGATION   → standard routing
REASONING    → planner preferred
CODE         → planner preferred
SAFETY       → planner ALWAYS (never downgraded)
VISION       → planner preferred
SEARCH       → planner preferred
```

## RCAN Config Format (v1.4)

```yaml
rcan_version: "1.4"  # Must match current spec
metadata:
  robot_name: my-robot
  rrn: RRN-000000000001               # RRF-assigned numeric RRN
  rrn_uri: rrn://org/robot/model/id   # URI-format RRN (structured)
  rcan_uri: rcan://robot.local:8000/my-robot
  version: 2026.3.13.11
agent:
  provider: google
  model: gemini-1.5-flash
task_routing:                          # Optional (PR #647)
  enabled: true
  categories:
    sensor_poll: {planner: false}
    safety:      {planner: true}
drivers:
  - id: wheels
    protocol: pca9685
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/                          # All tests
pytest tests/test_rcan_registry.py     # Registry + RRN tests (105 tests)
pytest tests/test_tiered_brain_task_routing.py  # Task routing (31 tests)
pytest tests/test_task_router.py       # TaskRouter (30 tests)
ruff check castor/                     # Lint
ruff format castor/                    # Format
```

**Key test gotchas:**
- `_reset_state_and_env` autouse fixture resets `AppState` before every test
- `MagicMock` answers `True` to any `hasattr()` — use `del mock._shared_state` to force False
- Error responses use `{"error": "...", "code": "HTTP_NNN"}` not `{"detail": "..."}`
- `tick_count = 998` not `999` in routing tests (999 is divisible by default interval 10)

## JS SDK (`sdk/js/`)

```typescript
import { CastorClient } from '@opencastor/sdk';
const client = new CastorClient({ baseUrl: 'http://robot.local:8000' });

// §19 INVOKE
await client.invoke({ skill: 'navigate_to', params: { x: 1, y: 2 }, timeoutMs: 5000 });
await client.invokeAll([{ skill: 'wave' }, { skill: 'speak', params: { text: 'hi' } }]);
const winner = await client.invokeRace([{ skill: 'plan_a' }, { skill: 'plan_b' }]);

// §21 Registry
await client.registryRegister({ rrn: 'RRN-000000000001', ruri: 'rcan://robot.local:8000/bob' });
const resolved = await client.registryResolve('RRN-000000000001');
```

Tests: `cd sdk/js && npm test` (13 tests, Jest + ts-jest)

## Website (`site/`)

8 static HTML pages. Theme: dark/light pill toggle (`☀·🌙`), stored in `localStorage('oc-theme')`.

**Key CSS patterns:**
- `.theme-pill` / `.theme-pill-opt[data-opt="light"|"dark"]` — pill toggle
- `.nav-end` — flex container for pill + hamburger (z-index: 1001 to stay above mobile nav)
- `.nav-theme-row` — shown only in mobile drawer (`display:none` on desktop)

**If adding a new page:** copy the nav structure from `index.html`, keep `.nav-end` group intact.

## CI/CD

| Workflow | Trigger | Action |
|---|---|---|
| `ci.yml` | Push / PR | pytest + ruff + mypy |
| `validate_rcan.yml` | `*.rcan.yaml` changes | JSON schema validation |
| `release.yml` | Tag push | PyPI publish |
| `deploy-pages.yml` | Main push | Cloudflare Pages (site/) |

Versioning: `YYYY.MM.DD.patch` — bump patch for each commit, date when date changes.

## Code Style

- **Python**: PEP 8, 100-char lines, snake_case, type hints on public signatures
- **Imports**: Ruff enforces — run `ruff format castor/ && ruff check castor/` before commit
- **Lazy imports**: `HAS_<NAME>` boolean pattern for optional hardware SDKs
- **Logging**: `logging.getLogger("OpenCastor.<Module>")`
- **TypeScript**: strict mode, no `any` on public surfaces

## Extending OpenCastor

### New Provider
1. `castor/providers/<name>_provider.py` → subclass `BaseProvider`
2. Implement `think()`, `think_stream()`, `health_check()`
3. Call `self._check_instruction_safety(instruction)` at start of `think()`
4. Register in `castor/providers/__init__.py` (`get_provider()`)
5. Add to `castor/auth.py` `PROVIDER_AUTH_MAP` + `.env.example`

### New Driver
1. `castor/drivers/<name>.py` → subclass `DriverBase`
2. Implement `move()`, `stop()`, `close()` with `HAS_<NAME>` mock fallback
3. Register in `castor/main.py` `get_driver()`

### New RCAN Skill (§19)
1. Define handler: `async def my_skill(params: dict) -> dict`
2. Register: `skill_registry.register("my_skill", my_skill)`
3. Test via `POST /rcan` with `{"msg_type": 11, "skill": "my_skill", "params": {...}}`

## Safety

- `_check_instruction_safety()` called at top of every `think()`/`think_stream()`
- `BoundsChecker` validates motor commands; `GuardianAgent` has veto
- `SENSOR_POLL` task category NEVER escalates to planner (TieredBrain hard override)
- `SAFETY` task category ALWAYS uses planner (never downgraded)
- `.env` in `.gitignore`; `bob.rcan.yaml`, `alex.rcan.yaml` gitignored (device-specific)

## Bob (the reference robot)

- **Hardware**: Raspberry Pi 5 16GB + Hailo-8 NPU + PCA9685 ESC/steering + CSI camera
- **RRN**: `RRN-000000000001` / `rrn://craigm26/robot/opencastor-rpi5-hailo/bob-001`
- **Config**: `~/opencastor/bob.rcan.yaml` (gitignored)
- **Host**: `robot.local` / `192.168.68.61`
- **RURI**: `rcan://robot.local:8000/bob`

## Useful Links

- Spec: https://rcan.dev/spec/
- §19 Invoke: https://rcan.dev/spec/section-19/
- §21 Registry: https://rcan.dev/spec/section-21/
- Robot Registry Foundation: https://robotregistryfoundation.org/
- rcan-py SDK: https://github.com/continuonai/rcan-py
