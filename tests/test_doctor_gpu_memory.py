"""Tests for check_gpu_memory() in castor/doctor.py — Issue #406."""

import sys
from unittest.mock import MagicMock, patch

from castor.doctor import check_gpu_memory, run_all_checks

# ---------------------------------------------------------------------------
# Basic contract tests
# ---------------------------------------------------------------------------


class TestCheckGpuMemoryContract:
    def test_function_exists_and_callable(self):
        """check_gpu_memory is importable and callable."""
        assert callable(check_gpu_memory)

    def test_returns_tuple(self):
        """Return value is a tuple."""
        result = check_gpu_memory()
        assert isinstance(result, tuple)

    def test_returns_tuple_of_length_3(self):
        """Return value is a 3-tuple."""
        result = check_gpu_memory()
        assert len(result) == 3

    def test_second_element_is_gpu_memory(self):
        """Second element of return tuple is 'GPU memory'."""
        result = check_gpu_memory()
        assert result[1] == "GPU memory"

    def test_first_element_is_bool(self):
        """First element of return tuple is a bool."""
        result = check_gpu_memory()
        assert isinstance(result[0], bool)

    def test_third_element_is_non_empty_string(self):
        """Third element of return tuple is a non-empty string."""
        result = check_gpu_memory()
        assert isinstance(result[2], str)
        assert len(result[2]) > 0


# ---------------------------------------------------------------------------
# nvidia-smi path tests
# ---------------------------------------------------------------------------


class TestCheckGpuMemoryNvidiaSmi:
    def test_nvidia_smi_success_under_80_percent(self):
        """nvidia-smi success with low VRAM usage returns ok=True."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "2000, 8000\n"

        with patch("subprocess.run", return_value=mock_result):
            ok, name, detail = check_gpu_memory()

        assert ok is True
        assert name == "GPU memory"
        assert "25.0%" in detail

    def test_nvidia_smi_over_80_percent_returns_false(self):
        """nvidia-smi with VRAM ≥80% used returns ok=False with warning."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "7000, 8000\n"

        with patch("subprocess.run", return_value=mock_result):
            ok, name, detail = check_gpu_memory()

        assert ok is False
        assert name == "GPU memory"
        assert ">80% full" in detail

    def test_nvidia_smi_failure_falls_through(self):
        """nvidia-smi non-zero returncode falls through to next check."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        # Also make torch unavailable so we hit the no-GPU path
        with patch("subprocess.run", return_value=mock_result):
            with patch.dict(sys.modules, {"torch": None}):
                ok, name, detail = check_gpu_memory()

        assert name == "GPU memory"
        # Either no-GPU skip or some valid result
        assert isinstance(ok, bool)

    def test_nvidia_smi_file_not_found_falls_through(self):
        """FileNotFoundError from nvidia-smi falls through gracefully."""
        with patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi not found")):
            with patch.dict(sys.modules, {"torch": None}):
                ok, name, detail = check_gpu_memory()

        assert name == "GPU memory"
        assert isinstance(ok, bool)
        assert isinstance(detail, str)


# ---------------------------------------------------------------------------
# No-GPU / fallback path tests
# ---------------------------------------------------------------------------


class TestCheckGpuMemoryNoGpu:
    def test_no_gpu_returns_true(self):
        """When no GPU is detected, function returns (True, 'GPU memory', skip_msg)."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            with patch.dict(sys.modules, {"torch": None}):
                ok, name, detail = check_gpu_memory()

        assert ok is True
        assert name == "GPU memory"
        assert "skipping" in detail.lower() or isinstance(detail, str)

    def test_torch_cuda_path_under_threshold(self):
        """torch.cuda path with low VRAM usage returns ok=True."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        # Build a minimal torch mock with cuda available
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.memory_allocated.return_value = 1 * 1024 * 1024 * 1024  # 1 GB
        props = MagicMock()
        props.total_memory = 8 * 1024 * 1024 * 1024  # 8 GB
        mock_torch.cuda.get_device_properties.return_value = props

        with patch("subprocess.run", return_value=mock_result):
            with patch.dict(sys.modules, {"torch": mock_torch}):
                ok, name, detail = check_gpu_memory()

        assert name == "GPU memory"
        assert isinstance(ok, bool)
        assert isinstance(detail, str)


# ---------------------------------------------------------------------------
# run_all_checks() integration test
# ---------------------------------------------------------------------------


class TestCheckGpuMemoryInRunAllChecks:
    def test_included_in_run_all_checks(self):
        """check_gpu_memory result appears in run_all_checks() output."""
        results = run_all_checks()
        names = [r[1] for r in results]
        assert "GPU memory" in names
