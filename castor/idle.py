"""
castor/idle.py — Robot idle detection and optimizer scheduling.

The per-robot optimizer (#697) must only run when the robot is genuinely
idle — not during active conversations, physical operations, or when battery
is low.

Usage::

    from castor.idle import is_robot_idle, IdleGuard

    # Simple check
    if await is_robot_idle():
        await run_optimizer(...)

    # Context manager — monitors for activity during a long operation
    async with IdleGuard() as guard:
        await run_optimizer(...)
        if guard.interrupted:
            print("Activity detected mid-pass — rolling back")

Safety:
  - P66: if ESTOP received during optimization pass → caller must check
    guard.interrupted and restore backup
  - Never blocks or delays ESTOP handling
  - Fail-open: if idle state cannot be determined, returns True (safe to proceed)
    because it's better to occasionally run than to permanently block.

Cron scheduling::

    # ~/.config/opencastor/crontab (appended by castor optimize --schedule)
    # Optimizer: run at 3am if idle
    0 3 * * * castor optimize >> ~/.config/opencastor/optimizer.log 2>&1
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

logger = logging.getLogger("OpenCastor.Idle")

__all__ = ["is_robot_idle", "IdleGuard", "IdleState", "install_cron_schedule"]

# Inactivity window: no API requests in this many seconds = idle
_IDLE_WINDOW_S = 5 * 60  # 5 minutes

# Battery minimum for optimizer to run
_BATTERY_MIN_PCT = 20

# Business hours: optimizer won't run during these hours (local time)
_BUSINESS_HOURS_START = 8  # 8 AM
_BUSINESS_HOURS_END = 22  # 10 PM

# Trajectory DB location (shared with optimizer)
_TRAJECTORY_DB = Path.home() / ".config" / "opencastor" / "trajectories.db"


# ── Idle state dataclass ──────────────────────────────────────────────────────


class IdleState:
    """Snapshot of the robot's idle state with reasoning."""

    def __init__(self) -> None:
        self.is_idle: bool = True
        self.reasons_blocked: list[str] = []
        self.battery_pct: Optional[float] = None
        self.last_activity_s: Optional[float] = None
        self.local_hour: int = datetime.datetime.now().hour
        self.checked_at: float = time.time()

    @property
    def summary(self) -> str:
        if self.is_idle:
            return "idle ✓"
        return "not idle — " + "; ".join(self.reasons_blocked)

    def __bool__(self) -> bool:
        return self.is_idle


# ── Main check ────────────────────────────────────────────────────────────────


async def is_robot_idle(
    min_idle_s: float = _IDLE_WINDOW_S,
    battery_min: float = _BATTERY_MIN_PCT,
    respect_hours: bool = True,
) -> IdleState:
    """Check whether the robot is idle enough to run the optimizer.

    Checks (all must pass):
      1. No recent API/bridge activity (last min_idle_s seconds)
      2. Battery > battery_min percent
      3. Not during business hours (8am–10pm local) if respect_hours=True
      4. No active P66 session (scope=control or safety in last turn)

    Returns an IdleState (truthy if idle).
    Fail-open: unknown = idle (returns True on errors).
    """
    state = IdleState()

    # Check 1: recent API activity via trajectory DB
    try:
        activity_s = await asyncio.to_thread(_last_activity_seconds, _TRAJECTORY_DB)
        state.last_activity_s = activity_s
        if activity_s is not None and activity_s < min_idle_s:
            state.is_idle = False
            state.reasons_blocked.append(
                f"active {activity_s:.0f}s ago (min idle: {min_idle_s:.0f}s)"
            )
    except Exception as exc:
        logger.debug("idle check (activity): %s", exc)

    # Check 2: battery level
    try:
        battery = await asyncio.to_thread(_get_battery_pct)
        state.battery_pct = battery
        if battery is not None and battery < battery_min:
            state.is_idle = False
            state.reasons_blocked.append(f"battery {battery:.0f}% < {battery_min:.0f}% minimum")
    except Exception as exc:
        logger.debug("idle check (battery): %s", exc)

    # Check 3: business hours
    if respect_hours:
        local_hour = state.local_hour
        if _BUSINESS_HOURS_START <= local_hour < _BUSINESS_HOURS_END:
            state.is_idle = False
            state.reasons_blocked.append(
                f"business hours ({local_hour}:00 local, "
                f"optimizer only runs {_BUSINESS_HOURS_END}:00–{_BUSINESS_HOURS_START}:00)"
            )

    # Check 4: active P66 session
    try:
        p66_active = await asyncio.to_thread(_check_p66_active, _TRAJECTORY_DB)
        if p66_active:
            state.is_idle = False
            state.reasons_blocked.append("active P66 control/safety session in progress")
    except Exception as exc:
        logger.debug("idle check (p66): %s", exc)

    if state.is_idle:
        logger.debug("Idle check passed — robot is idle")
    else:
        logger.info("Idle check failed: %s", "; ".join(state.reasons_blocked))

    return state


# ── Context manager for mid-pass interruption ─────────────────────────────────


class IdleGuard:
    """Async context manager that monitors for activity during an optimizer pass.

    If the robot becomes active mid-pass (new trajectory entry appears),
    sets ``self.interrupted = True`` so the caller can rollback.

    Usage::

        async with IdleGuard(poll_interval_s=10.0) as guard:
            await run_optimization_pass()
            if guard.interrupted:
                restore_backup()
    """

    def __init__(self, poll_interval_s: float = 10.0) -> None:
        self._poll_interval = poll_interval_s
        self.interrupted: bool = False
        self._task: Optional[asyncio.Task] = None
        self._baseline_ts: Optional[float] = None

    async def __aenter__(self) -> IdleGuard:
        self._baseline_ts = _latest_trajectory_ts(_TRAJECTORY_DB)
        self._task = asyncio.create_task(self._monitor())
        return self

    async def __aexit__(self, *_) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitor(self) -> None:
        """Poll for new trajectory entries while the optimizer runs."""
        while True:
            await asyncio.sleep(self._poll_interval)
            try:
                latest = _latest_trajectory_ts(_TRAJECTORY_DB)
                if latest is not None and (self._baseline_ts is None or latest > self._baseline_ts):
                    logger.info(
                        "IdleGuard: new activity detected during optimization pass — flagging interrupt"
                    )
                    self.interrupted = True
                    return
            except Exception:
                pass  # fail-open — don't interrupt on DB errors


# ── Cron scheduling ───────────────────────────────────────────────────────────


def install_cron_schedule(hour: int = 3, minute: int = 0) -> str:
    """Add a cron entry to run the optimizer at the given time.

    Writes to the user's crontab via ``crontab -l`` + ``crontab -``.
    Returns the cron line that was added (or 'already installed').

    Args:
        hour:   Hour (0–23, local time) to run the optimizer. Default: 3 AM.
        minute: Minute (0–59). Default: 0.
    """
    import subprocess

    log_path = Path.home() / ".config" / "opencastor" / "optimizer.log"
    cron_line = f"{minute} {hour} * * * castor optimize >> {log_path} 2>&1"
    marker = "castor optimize"

    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        existing = result.stdout if result.returncode == 0 else ""
    except Exception:
        existing = ""

    if marker in existing:
        return "already installed"

    new_crontab = existing.rstrip() + f"\n{cron_line}\n"
    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if proc.returncode == 0:
        logger.info("Cron schedule installed: %s", cron_line)
        return cron_line
    else:
        raise RuntimeError(f"Failed to install cron: {proc.stderr}")


def uninstall_cron_schedule() -> bool:
    """Remove the castor optimize cron entry. Returns True if removed."""
    import subprocess

    marker = "castor optimize"
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0 or marker not in result.stdout:
            return False

        lines = [ln for ln in result.stdout.splitlines() if marker not in ln]
        new_crontab = "\n".join(lines) + "\n"
        proc = subprocess.run(
            ["crontab", "-"], input=new_crontab, capture_output=True, text=True, timeout=5
        )
        return proc.returncode == 0
    except Exception:
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────


def _last_activity_seconds(db_path: Path) -> Optional[float]:
    """Return seconds since the most recent trajectory entry, or None if no DB."""
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT timestamp FROM trajectories ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row and row[0]:
            # Timestamp is ISO string
            last = datetime.datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            now = datetime.datetime.now(datetime.timezone.utc)
            return (now - last).total_seconds()
    except Exception:
        pass
    return None


def _latest_trajectory_ts(db_path: Path) -> Optional[str]:
    """Return the raw timestamp of the most recent trajectory row."""
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT timestamp FROM trajectories ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def _get_battery_pct() -> Optional[float]:
    """Try to read battery level from castor telemetry. Returns None if unavailable."""
    try:
        # Try reading from Pi's power supply sys interface
        sysfs = Path("/sys/class/power_supply")
        for ps in sysfs.iterdir() if sysfs.exists() else []:
            cap_file = ps / "capacity"
            if cap_file.exists():
                return float(cap_file.read_text().strip())
    except Exception:
        pass

    # Try castor status JSON
    try:
        import subprocess

        result = subprocess.run(
            ["castor", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            import json

            data = json.loads(result.stdout)
            battery = data.get("battery")
            if battery is not None:
                return float(battery)
    except Exception:
        pass

    return None  # unknown — fail-open (don't block on unknown battery)


def _check_p66_active(db_path: Path) -> bool:
    """Return True if the most recent trajectory had an active control/safety scope."""
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            """
            SELECT scope, timestamp FROM trajectories
            ORDER BY timestamp DESC LIMIT 1
            """
        ).fetchone()
        conn.close()
        if row:
            scope = (row[0] or "").lower()
            ts_str = row[1] or ""
            # Only flag if the last entry was < 5 minutes ago
            try:
                last = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age_s = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds()
                if age_s < 300 and scope in ("control", "safety"):
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


# ── asynccontextmanager alias ─────────────────────────────────────────────────


# Export asynccontextmanager-wrapped version for convenience
@asynccontextmanager
async def idle_guard(poll_interval_s: float = 10.0) -> AsyncGenerator[IdleGuard, None]:
    """Async context manager alias for IdleGuard."""
    guard = IdleGuard(poll_interval_s=poll_interval_s)
    async with guard:
        yield guard
