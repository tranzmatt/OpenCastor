"""tests/test_system_info.py — Tests for castor/system_info.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestGetSystemInfo:
    def test_returns_dict_with_required_keys(self):
        from castor.system_info import get_system_info

        info = get_system_info()
        required = {
            "platform",
            "ram_total_gb",
            "ram_available_gb",
            "cpu_temp_c",
            "npu_detected",
            "disk_total_gb",
            "disk_free_gb",
        }
        for k in required:
            assert k in info, f"Missing key: {k}"

    def test_ram_values_are_positive(self):
        from castor.system_info import get_system_info

        info = get_system_info()
        if info["ram_total_gb"] is not None:
            assert info["ram_total_gb"] > 0
        if info["ram_available_gb"] is not None:
            assert info["ram_available_gb"] > 0

    def test_platform_is_string(self):
        from castor.system_info import get_system_info

        info = get_system_info()
        assert isinstance(info["platform"], str)
        assert len(info["platform"]) > 0

    def test_no_exceptions_on_any_field(self):
        """All fields must be JSON-safe (no exceptions, no non-serializable types)."""
        import json

        from castor.system_info import get_system_info

        info = get_system_info()
        dumped = json.dumps(info)
        assert len(dumped) > 10

    def test_hailo_npu_detected(self):
        """When /dev/hailo0 exists, npu_detected should return hailo-8."""
        from pathlib import Path
        from unittest.mock import patch

        with patch.object(Path, "exists", return_value=True):
            from castor import system_info

            npu, tops = system_info._detect_npu()
            assert npu == "hailo-8"
            assert tops == 26.0

    def test_no_npu_returns_none(self):
        from pathlib import Path

        with patch.object(Path, "exists", return_value=False):
            from castor import system_info

            npu, tops = system_info._detect_npu()
            assert npu is None

    def test_cpu_temp_returns_float_or_none(self):
        from castor.system_info import _cpu_temp_c

        t = _cpu_temp_c()
        assert t is None or isinstance(t, float)
        if t is not None:
            assert 0 < t < 150, f"Unrealistic temp: {t}"


class TestGetModelRuntimeInfo:
    def test_returns_required_keys(self):
        from castor.system_info import get_model_runtime_info

        state = MagicMock()
        state.config = {
            "agent": {"provider": "ollama", "model": "gemma3:4b"},
            "local_inference": {},
        }
        info = get_model_runtime_info(state)
        for k in ("active_model", "provider", "kv_compression", "context_window"):
            assert k in info

    def test_default_kv_compression_is_none(self):
        from castor.system_info import get_model_runtime_info

        state = MagicMock()
        state.config = {"agent": {"provider": "ollama", "model": "gemma3:4b"}}
        info = get_model_runtime_info(state)
        assert info["kv_compression"] == "none"

    def test_turboquant_kv_preserved(self):
        from castor.system_info import get_model_runtime_info

        state = MagicMock()
        state.config = {
            "agent": {"provider": "ollama", "model": "gemma3:4b"},
            "local_inference": {"kv_compression": "turboquant", "kv_bits": 2},
        }
        info = get_model_runtime_info(state)
        assert info["kv_compression"] == "turboquant"
        assert info["kv_bits"] == 2

    def test_llmfit_runs_without_crash(self):
        from castor.system_info import get_model_runtime_info

        state = MagicMock()
        state.config = {"agent": {"provider": "ollama", "model": "gemma3:4b"}}
        info = get_model_runtime_info(state)
        # llmfit may or may not run depending on device RAM — just check no crash
        assert isinstance(info, dict)

    def test_none_state_safe(self):
        """get_model_runtime_info(None) should not raise."""
        from castor.system_info import get_model_runtime_info

        info = get_model_runtime_info(
            None,
            config={
                "agent": {"provider": "ollama", "model": "gemma3:4b"},
            },
        )
        assert isinstance(info, dict)
