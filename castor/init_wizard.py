"""castor.init_wizard — interactive ROBOT.md generator.

Writes a v3.2 ROBOT.md (rcan-spec §8.6 agent.runtimes[]) to the target
path. Entry points:

- ``cmd_init(args)``       — full interactive or flag-driven init
- ``cmd_quickstart(args)`` — abbreviated quickstart (same emission, fewer prompts)

Both accept an ``argparse.Namespace`` and return an exit code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

_ROBOT_MD_TEMPLATE = """\
# {robot_name}

A {manufacturer} {model} declared for the RCAN ecosystem.

## Runtime

Select with:

```bash
castor run --runtime opencastor
```
"""


def _build_frontmatter(
    *,
    robot_name: str,
    manufacturer: str,
    model: str,
    version: str,
    device_id: str,
    provider: str,
    llm_model: str,
) -> dict[str, Any]:
    """Construct the v3.2 frontmatter dict."""
    return {
        "rcan_version": "3.2",
        "metadata": {
            "robot_name": robot_name,
            "manufacturer": manufacturer,
            "model": model,
            "version": version,
            "device_id": device_id,
        },
        "network": {
            "rrf_endpoint": "https://rcan.dev",
            "signing_alg": "pqc-hybrid-v1",
        },
        "agent": {
            "runtimes": [
                {
                    "id": "opencastor",
                    "harness": "castor-default",
                    "default": True,
                    "models": [
                        {"provider": provider, "model": llm_model, "role": "primary"},
                    ],
                },
            ],
        },
        "safety": {
            "estop": {"software": True, "response_ms": 100},
        },
    }


def _write_robot_md(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    serialized = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    path.write_text(f"---\n{serialized}---\n\n{body}")


def _prompt(prompt: str, default: str, non_interactive: bool) -> str:
    if non_interactive:
        return default
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def cmd_init(args: argparse.Namespace) -> int:
    """Write a ROBOT.md manifest. Returns a POSIX exit code."""
    non_interactive = bool(getattr(args, "non_interactive", False))
    path = Path(getattr(args, "path", "ROBOT.md"))
    force = bool(getattr(args, "force", False))

    if path.exists() and not force:
        sys.stderr.write(f"refusing to overwrite existing {path}. Pass --force to replace.\n")
        return 2

    robot_name = _prompt("Robot name", getattr(args, "robot_name", "bob"), non_interactive)
    manufacturer = _prompt(
        "Manufacturer", getattr(args, "manufacturer", "craigm26"), non_interactive
    )
    model = _prompt("Model", getattr(args, "model", "so-arm101"), non_interactive)
    version = _prompt("Version", getattr(args, "version", "1.0.0"), non_interactive)
    device_id = _prompt("Device ID", getattr(args, "device_id", "bob-001"), non_interactive)
    provider = _prompt("LLM provider", getattr(args, "provider", "anthropic"), non_interactive)
    llm_model = _prompt(
        "LLM model", getattr(args, "llm_model", "claude-sonnet-4-6"), non_interactive
    )

    fm = _build_frontmatter(
        robot_name=robot_name,
        manufacturer=manufacturer,
        model=model,
        version=version,
        device_id=device_id,
        provider=provider,
        llm_model=llm_model,
    )
    body = _ROBOT_MD_TEMPLATE.format(robot_name=robot_name, manufacturer=manufacturer, model=model)
    _write_robot_md(path, fm, body)
    sys.stdout.write(f"wrote {path}\n")
    return 0


def cmd_quickstart(args: argparse.Namespace) -> int:
    """Abbreviated quickstart: same emission, bob/opencastor defaults."""
    args.non_interactive = True
    for field, default in [
        ("robot_name", "bob"),
        ("manufacturer", "craigm26"),
        ("model", "so-arm101"),
        ("version", "1.0.0"),
        ("device_id", "bob-001"),
        ("provider", "anthropic"),
        ("llm_model", "claude-sonnet-4-6"),
        ("path", "ROBOT.md"),
    ]:
        if getattr(args, field, None) is None:
            setattr(args, field, default)
    return cmd_init(args)
