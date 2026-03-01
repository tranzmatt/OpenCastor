"""
castor/behaviors.py — Behavior script runner for OpenCastor.

A behavior is a YAML file that describes a named sequence of steps to execute.
Steps are dispatched through a table keyed on ``type``, so new step types can
be added without growing an if/elif chain.

Example behavior file::

    name: patrol
    steps:
      - type: think
        instruction: "Scan the room and describe what you see"
      - type: wait
        seconds: 2
      - type: speak
        text: "Patrol complete"
      - type: stop

Usage::

    from castor.behaviors import BehaviorRunner
    runner = BehaviorRunner(driver=driver, brain=brain, speaker=speaker, config=cfg)
    behavior = runner.load("patrol.behavior.yaml")
    runner.run(behavior)
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("OpenCastor.Behaviors")

REQUIRED_KEYS = {"name", "steps"}


class BehaviorRunner:
    """Execute named behavior scripts that drive the robot through a sequence of steps.

    Parameters
    ----------
    driver:
        A ``DriverBase`` instance (or None for brain-only / speaker-only runs).
    brain:
        A ``BaseProvider`` instance (or None if no LLM needed).
    speaker:
        A ``Speaker`` instance (or None if TTS disabled).
    config:
        Raw RCAN config dict (used for future extensions).
    """

    def __init__(
        self,
        driver=None,
        brain=None,
        speaker=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.driver = driver
        self.brain = brain
        self.speaker = speaker
        self.config = config or {}

        self._running: bool = False
        self._current_name: Optional[str] = None

        # Dispatch table: step type -> handler method
        self._step_handlers: Dict[str, Any] = {
            "waypoint": self._step_waypoint,
            "wait": self._step_wait,
            "think": self._step_think,
            "speak": self._step_speak,
            "stop": self._step_stop,
            "command": self._step_think,  # alias for think
            "nav_mission": self._step_nav_mission,
            "parallel": self._step_parallel,
            "loop": self._step_loop,
            "condition": self._step_condition,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True while a behavior is being executed."""
        return self._running

    @property
    def current_name(self) -> Optional[str]:
        """Name of the currently-running behavior (or None)."""
        return self._current_name

    def load(self, path: str) -> dict:
        """Load and validate a YAML behavior file.

        Parameters
        ----------
        path:
            File-system path to the ``.behavior.yaml`` file.

        Returns
        -------
        dict
            Parsed behavior dict with at minimum ``name`` and ``steps``.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If required keys (``name``, ``steps``) are missing.
        yaml.YAMLError
            If the file is not valid YAML.
        """
        try:
            import yaml
        except ImportError as exc:
            raise ImportError("pyyaml is required to load behavior files") from exc

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Behavior file not found: {path}")

        with open(p) as fh:
            data = yaml.safe_load(fh)

        if not isinstance(data, dict):
            raise ValueError(f"Behavior file must be a YAML mapping, got {type(data).__name__}")

        missing = REQUIRED_KEYS - set(data.keys())
        if missing:
            raise ValueError(f"Behavior file missing required keys: {missing}")

        if not isinstance(data["steps"], list):
            raise ValueError("'steps' must be a list")

        logger.info("Loaded behavior '%s' with %d step(s)", data["name"], len(data["steps"]))
        return data

    def run(self, behavior: dict) -> None:
        """Execute all steps in *behavior* sequentially.

        Sets ``_running = True`` before the first step and calls ``stop()``
        in a ``finally`` block so the driver always halts on completion or
        on error.

        Parameters
        ----------
        behavior:
            A behavior dict as returned by :meth:`load`.
        """
        name = behavior.get("name", "<unnamed>")
        steps = behavior.get("steps", [])

        self._running = True
        self._current_name = name
        logger.info("Starting behavior '%s' (%d steps)", name, len(steps))

        try:
            for i, step in enumerate(steps):
                if not self._running:
                    logger.info("Behavior '%s' stopped at step %d", name, i)
                    break

                step_type = step.get("type", "")
                handler = self._step_handlers.get(step_type)
                if handler is None:
                    logger.warning("Unknown step type '%s' at index %d — skipping", step_type, i)
                    continue

                logger.debug("Step %d: %s %r", i, step_type, step)
                try:
                    handler(step)
                except Exception as exc:
                    logger.error("Step %d (%s) raised: %s", i, step_type, exc)
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the current behavior and halt the driver (if available)."""
        self._running = False
        self._current_name = None
        if self.driver is not None:
            try:
                self.driver.stop()
            except Exception as exc:
                logger.warning("Driver stop error: %s", exc)

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------

    def _step_waypoint(self, step: dict) -> None:
        """Move to a named or coordinate waypoint.

        Tries to use ``castor.nav.WaypointNav`` if available.  Falls back to
        a timed ``driver.move()`` using step ``duration`` (default: 1 s) and
        step ``direction`` (default: 'forward').
        """
        try:
            from castor.nav import WaypointNav  # type: ignore

            nav = WaypointNav(self.driver, self.config)
            nav.go(step)
        except (ImportError, AttributeError):
            # Fallback: timed drive in a direction
            direction = step.get("direction", "forward")
            duration = float(step.get("duration", 1.0))
            speed = float(step.get("speed", 0.5))
            logger.debug(
                "Waypoint fallback: move %s for %.1fs at speed %.2f",
                direction,
                duration,
                speed,
            )
            if self.driver is not None:
                self.driver.move(direction=direction, speed=speed)
                time.sleep(duration)
                self.driver.stop()
            else:
                logger.warning("Waypoint step: no driver available, sleeping %.1fs", duration)
                time.sleep(duration)

    def _step_wait(self, step: dict) -> None:
        """Sleep for ``step['seconds']`` (default: 1 s)."""
        seconds = float(step.get("seconds", 1.0))
        logger.debug("Wait %.2fs", seconds)
        time.sleep(seconds)

    def _step_think(self, step: dict) -> None:
        """Send an instruction to the brain and log the result.

        Uses empty image bytes (b"") so the behavior can run without a live
        camera feed.  The step must contain an ``instruction`` key.
        """
        instruction = step.get("instruction", "")
        if self.brain is None:
            logger.warning("Think step: no brain available, skipping")
            return
        thought = self.brain.think(b"", instruction)
        logger.info("Think result: %s", thought.raw_text[:200])

    def _step_speak(self, step: dict) -> None:
        """Speak ``step['text']`` via the TTS speaker."""
        text = step.get("text", "")
        if self.speaker is None:
            logger.warning("Speak step: no speaker available, skipping")
            return
        if hasattr(self.speaker, "enabled") and not self.speaker.enabled:
            logger.debug("Speak step: speaker disabled, skipping")
            return
        self.speaker.say(text)

    def _step_stop(self, step: dict) -> None:  # noqa: ARG002
        """Immediately stop the driver."""
        if self.driver is not None:
            self.driver.stop()
        else:
            logger.debug("Stop step: no driver available")

    def _step_nav_mission(self, step: dict) -> None:
        """Execute an inline waypoint sequence using :class:`castor.mission.MissionRunner`.

        The step dict must contain a ``waypoints`` key — a list of dicts with at
        least ``distance_m``.  Optional per-waypoint keys: ``heading_deg``,
        ``speed``, ``dwell_s``, ``label``.

        An optional ``loop`` key (default ``False``) causes the waypoint list to
        repeat until this behavior is stopped.

        Example step::

            - type: nav_mission
              waypoints:
                - {distance_m: 0.5, heading_deg: 0, speed: 0.6, dwell_s: 0, label: forward}
                - {distance_m: 0.3, heading_deg: 90, speed: 0.5, dwell_s: 1.0, label: turn}
              loop: false
        """
        from castor.mission import MissionRunner  # lazy import to avoid circular deps

        waypoints = step.get("waypoints")
        if not waypoints:
            logger.warning("nav_mission step: 'waypoints' is missing or empty — skipping")
            return

        loop: bool = bool(step.get("loop", False))

        logger.info(
            "nav_mission step: starting mission with %d waypoint(s), loop=%s",
            len(waypoints),
            loop,
        )

        runner = MissionRunner(self.driver, self.config)
        runner.start(waypoints, loop=loop)

        done_event = threading.Event()

        def _wait_for_finish() -> None:
            while True:
                if not self._running or runner.status()["running"] is False:
                    done_event.set()
                    return
                time.sleep(0.1)

        watcher = threading.Thread(target=_wait_for_finish, daemon=True, name="nav-mission-watcher")
        watcher.start()

        while self._running and runner.status()["running"]:
            time.sleep(0.1)

        runner.stop()
        done_event.set()

        logger.info(
            "nav_mission step: mission finished (running=%s)",
            runner.status()["running"],
        )

    def _step_parallel(self, step: dict) -> None:
        """Run multiple inner steps concurrently in daemon threads.

        All inner steps are dispatched via ``_step_handlers`` and execute
        simultaneously.  The method blocks until every thread has finished or
        until ``timeout_s`` seconds have elapsed (default: 10.0).  Any threads
        still alive after the timeout are logged as warnings but are not
        forcibly killed (daemon flag means they die with the process).

        Each inner step's exception is caught and logged as a warning so that
        one failing step does not prevent the others from running.

        Example step::

            - type: parallel
              timeout_s: 5.0
              steps:
                - type: speak
                  text: "Going forward"
                - type: wait
                  seconds: 1.0

        Parameters
        ----------
        step:
            The step dict.  Must contain a ``steps`` key with a list of inner
            step dicts.  May contain ``timeout_s`` (float, default 10.0).
        """
        if not self._running:
            return

        inner_steps = step.get("steps")
        if not inner_steps:
            logger.warning("parallel step: 'steps' is missing or empty — skipping")
            return

        timeout_s = float(step.get("timeout_s", 10.0))
        logger.info(
            "parallel step: launching %d inner step(s) with timeout=%.1fs",
            len(inner_steps),
            timeout_s,
        )

        def _run_inner(inner_step: dict) -> None:
            step_type = inner_step.get("type", "")
            handler = self._step_handlers.get(step_type)
            if handler is None:
                logger.warning("parallel step: unknown inner step type '%s' — skipping", step_type)
                return
            try:
                handler(inner_step)
            except Exception as exc:
                logger.warning("parallel step: inner step '%s' raised: %s", step_type, exc)

        threads = [
            threading.Thread(
                target=_run_inner, args=(inner_step,), daemon=True, name=f"parallel-step-{i}"
            )
            for i, inner_step in enumerate(inner_steps)
        ]

        deadline = time.monotonic() + timeout_s
        for t in threads:
            t.start()

        for t in threads:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            t.join(timeout=remaining)

        alive = [t.name for t in threads if t.is_alive()]
        if alive:
            logger.warning(
                "parallel step: %d thread(s) still alive after timeout: %s", len(alive), alive
            )
        else:
            logger.info("parallel step: all inner steps completed")

    def _step_loop(self, step: dict) -> None:
        """Repeat a sequence of inner steps N times or indefinitely.

        Parameters
        ----------
        step:
            The step dict.  Must contain a ``steps`` key with a list of inner
            step dicts.  May contain ``count`` (int, default 1).  A ``count``
            of ``-1`` means loop indefinitely until :meth:`stop` is called.

        Example step::

            - type: loop
              count: 3
              steps:
                - type: wait
                  seconds: 0.5
                - type: speak
                  text: "Beep"

            - type: loop
              count: -1
              steps:
                - type: wait
                  seconds: 1.0
        """
        inner_steps = step.get("steps")
        if not inner_steps:
            logger.warning("loop step: 'steps' is missing or empty — skipping")
            return

        count = int(step.get("count", 1))
        logger.info(
            "loop step: starting loop count=%s with %d inner step(s)",
            "indefinite" if count == -1 else count,
            len(inner_steps),
        )

        iteration = 1
        while True:
            if not self._running:
                break
            if count != -1 and iteration > count:
                break

            for inner_step in inner_steps:
                if not self._running:
                    break
                step_type = inner_step.get("type", "")
                handler = self._step_handlers.get(step_type)
                if handler is None:
                    logger.warning("loop step: unknown inner step type '%s' — skipping", step_type)
                    continue
                try:
                    handler(inner_step)
                except Exception as exc:
                    logger.warning("loop step: inner step '%s' raised: %s", step_type, exc)

            iteration += 1

        logger.info("loop step: done after %d iteration(s)", iteration - 1)

    def _step_condition(self, step: dict) -> None:
        """Evaluate a sensor condition and branch into ``then_steps`` or ``else_steps``.

        The sensor is queried lazily at runtime; if the sensor driver is
        unavailable the field lookup falls through to ``else_steps``.

        Supported sensors (``sensor`` key):

        * ``"lidar"`` — calls ``castor.drivers.lidar_driver.get_lidar().obstacles()``
        * ``"thermal"`` — calls ``castor.drivers.thermal_driver.get_thermal().get_hotspot()``
        * ``"imu"`` — calls ``castor.drivers.imu_driver.get_imu().read()``
        * ``"none"`` (default) — empty dict; ``then_steps`` always runs when
          ``sensor`` is ``"none"`` and ``field`` is absent or ``None``.

        Supported operators (``op`` key): ``lt``, ``gt``, ``lte``, ``gte``,
        ``eq``, ``neq``.

        Example step::

            - type: condition
              sensor: lidar
              field: center_cm
              op: lt
              value: 300
              then_steps:
                - type: stop
              else_steps:
                - type: wait
                  seconds: 0.5

        Parameters
        ----------
        step:
            The step dict.  Required keys: ``field``, ``op``, ``value``.
            Optional keys: ``sensor`` (default ``"none"``),
            ``then_steps`` (default ``[]``), ``else_steps`` (default ``[]``).
        """
        sensor = step.get("sensor", "none")
        field = step.get("field")
        op = step.get("op", "")
        value = step.get("value")
        then_steps: list = step.get("then_steps") or []
        else_steps: list = step.get("else_steps") or []

        # --- Query sensor ------------------------------------------------
        sensor_data: dict = {}
        if sensor == "lidar":
            try:
                from castor.drivers.lidar_driver import get_lidar  # type: ignore

                sensor_data = get_lidar().obstacles()
            except (ImportError, Exception) as exc:
                logger.warning("condition step: lidar query failed (%s) — using {}", exc)
        elif sensor == "thermal":
            try:
                from castor.drivers.thermal_driver import get_thermal  # type: ignore

                sensor_data = get_thermal().get_hotspot()
            except (ImportError, Exception) as exc:
                logger.warning("condition step: thermal query failed (%s) — using {}", exc)
        elif sensor == "imu":
            try:
                from castor.drivers.imu_driver import get_imu  # type: ignore

                sensor_data = get_imu().read()
            except (ImportError, Exception) as exc:
                logger.warning("condition step: imu query failed (%s) — using {}", exc)
        elif sensor != "none":
            logger.warning("condition step: unknown sensor '%s' — using {}", sensor)

        # --- Extract field -----------------------------------------------
        actual = sensor_data.get(field) if field is not None else None
        if actual is None:
            if sensor != "none" or field is not None:
                logger.warning(
                    "condition step: field '%s' not found in sensor '%s' data — running else_steps",
                    field,
                    sensor,
                )
            branch = else_steps
        else:
            # --- Evaluate operator -------------------------------------------
            _OPS = {
                "lt": lambda a, b: a < b,
                "gt": lambda a, b: a > b,
                "lte": lambda a, b: a <= b,
                "gte": lambda a, b: a >= b,
                "eq": lambda a, b: a == b,
                "neq": lambda a, b: a != b,
            }
            op_fn = _OPS.get(op)
            if op_fn is None:
                logger.warning("condition step: unknown op '%s' — treating condition as False", op)
                result = False
            else:
                result = bool(op_fn(actual, value))

            logger.debug(
                "condition step: sensor=%s field=%s actual=%s op=%s value=%s → %s",
                sensor,
                field,
                actual,
                op,
                value,
                result,
            )
            branch = then_steps if result else else_steps

        # --- Execute branch ----------------------------------------------
        branch_name = "then_steps" if branch is then_steps else "else_steps"
        logger.info(
            "condition step: executing %s (%d step(s))",
            branch_name,
            len(branch),
        )
        for inner_step in branch:
            if not self._running:
                break
            step_type = inner_step.get("type", "")
            handler = self._step_handlers.get(step_type)
            if handler is None:
                logger.warning("condition step: unknown inner step type '%s' — skipping", step_type)
                continue
            try:
                handler(inner_step)
            except Exception as exc:
                logger.warning("condition step: inner step '%s' raised: %s", step_type, exc)
