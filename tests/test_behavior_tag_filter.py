"""Tests for BehaviorRunner tag-based step filtering (#387)."""

from unittest.mock import MagicMock

from castor.behaviors import BehaviorRunner


def _make_runner(tags=None):
    driver = MagicMock()
    config = {"robot_tags": tags or []}
    runner = BehaviorRunner(driver=driver, config=config)
    runner._running = True
    return runner


# ── _step_tags_match ──────────────────────────────────────────────────────────


def test_step_no_tags_always_runs():
    runner = _make_runner(tags=["rpi5"])
    assert runner._step_tags_match({"type": "wait"}) is True


def test_step_empty_tags_always_runs():
    runner = _make_runner(tags=["rpi5"])
    assert runner._step_tags_match({"type": "wait", "tags": []}) is True


def test_step_matching_tag_runs():
    runner = _make_runner(tags=["rpi5", "camera"])
    assert runner._step_tags_match({"type": "wait", "tags": ["rpi5"]}) is True


def test_step_non_matching_tag_skipped():
    runner = _make_runner(tags=["rpi5"])
    assert runner._step_tags_match({"type": "wait", "tags": ["jetson"]}) is False


def test_step_partial_tag_match_runs():
    runner = _make_runner(tags=["rpi5", "camera", "lidar"])
    # Step requires any of [lidar, jetson] — lidar matches
    assert runner._step_tags_match({"type": "wait", "tags": ["lidar", "jetson"]}) is True


def test_no_robot_tags_all_steps_run():
    runner = _make_runner(tags=[])
    assert runner._step_tags_match({"type": "wait", "tags": ["rpi5"]}) is True


# ── _robot_tags initialization ────────────────────────────────────────────────


def test_robot_tags_set_from_config():
    runner = _make_runner(tags=["rpi5", "camera"])
    assert "rpi5" in runner._robot_tags
    assert "camera" in runner._robot_tags


def test_robot_tags_empty_by_default():
    runner = _make_runner()
    assert runner._robot_tags == set()


def test_robot_tags_from_tags_key():
    driver = MagicMock()
    runner = BehaviorRunner(driver=driver, config={"tags": ["jetson", "lidar"]})
    runner._running = True
    assert "jetson" in runner._robot_tags


# ── tag filtering in run() loop (via _run_step_list) ─────────────────────────


def test_tagged_step_skipped_in_step_list(caplog):
    import logging

    runner = _make_runner(tags=["rpi5"])
    executed = []

    def fake_wait(step):
        executed.append("wait")

    runner._step_handlers["wait"] = fake_wait
    steps = [
        {"type": "wait", "tags": ["jetson"]},  # should be skipped
        {"type": "wait"},  # no tags → should run
    ]
    with caplog.at_level(logging.DEBUG):
        runner._run_step_list(steps, "test")
    assert executed == ["wait"]  # only the untagged step ran


def test_matching_tagged_step_runs():
    runner = _make_runner(tags=["camera"])
    executed = []

    def fake_wait(step):
        executed.append("wait")

    runner._step_handlers["wait"] = fake_wait
    steps = [{"type": "wait", "tags": ["camera"]}]
    runner._run_step_list(steps, "test")
    assert executed == ["wait"]


def test_no_robot_tags_all_tagged_steps_run():
    runner = _make_runner(tags=[])
    executed = []

    def fake_wait(step):
        executed.append("wait")

    runner._step_handlers["wait"] = fake_wait
    steps = [
        {"type": "wait", "tags": ["jetson"]},
        {"type": "wait", "tags": ["rpi5"]},
        {"type": "wait"},
    ]
    runner._run_step_list(steps, "test")
    assert len(executed) == 3


def test_multiple_tags_some_match():
    runner = _make_runner(tags=["lidar"])
    executed = []

    def fake_wait(step):
        executed.append("wait")

    runner._step_handlers["wait"] = fake_wait
    steps = [
        {"type": "wait", "tags": ["camera"]},  # skip
        {"type": "wait", "tags": ["lidar"]},  # run
        {"type": "wait", "tags": ["camera", "lidar"]},  # run (lidar matches)
    ]
    runner._run_step_list(steps, "test")
    assert len(executed) == 2
