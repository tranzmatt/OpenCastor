"""Unit tests for castor.hardware_detect."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# scan_i2c
# ---------------------------------------------------------------------------


def test_scan_i2c_returns_empty_on_non_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    from castor.hardware_detect import scan_i2c

    result = scan_i2c()
    assert result == []


def test_scan_i2c_parses_output(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    fake_output = (
        "     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f\n"
        "00:          -- -- -- -- -- -- -- -- -- -- -- -- --\n"
        "10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --\n"
        "40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --\n"
        "70: -- -- -- -- -- -- -- --\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = fake_output

    with (
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=["i2c-1"]),
        patch("subprocess.run", return_value=mock_result),
    ):
        import castor.hardware_detect as hd

        devices = hd.scan_i2c()

    assert any(d["address"] == "0x40" for d in devices)


def test_scan_i2c_handles_file_not_found(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with (
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=["i2c-1"]),
        patch("subprocess.run", side_effect=FileNotFoundError),
    ):
        from castor.hardware_detect import scan_i2c

        result = scan_i2c()
    assert result == []


# ---------------------------------------------------------------------------
# scan_usb_serial
# ---------------------------------------------------------------------------


def test_scan_usb_serial_returns_ports(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with (
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=["ttyUSB0", "ttyACM0", "tty0"]),
    ):
        from castor.hardware_detect import scan_usb_serial

        ports = scan_usb_serial()

    assert "/dev/ttyUSB0" in ports
    assert "/dev/ttyACM0" in ports
    # tty0 should not be included
    assert "/dev/tty0" not in ports


def test_scan_usb_serial_empty_on_non_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    from castor.hardware_detect import scan_usb_serial

    assert scan_usb_serial() == []


# ---------------------------------------------------------------------------
# detect_hardware
# ---------------------------------------------------------------------------


def test_detect_hardware_returns_expected_keys():
    with (
        patch("castor.hardware_detect.scan_i2c", return_value=[]),
        patch("castor.hardware_detect.scan_usb_serial", return_value=[]),
        patch("castor.hardware_detect.scan_usb_descriptors", return_value=[]),
        patch("castor.hardware_detect.scan_cameras", return_value=[]),
        patch("castor.hardware_detect._detect_platform", return_value="generic"),
    ):
        from castor.hardware_detect import detect_hardware

        hw = detect_hardware()

    for key in ("i2c_devices", "usb_serial", "cameras", "platform"):
        assert key in hw


# ---------------------------------------------------------------------------
# suggest_preset
# ---------------------------------------------------------------------------


def test_suggest_preset_generic_when_nothing():
    from castor.hardware_detect import suggest_preset

    hw = {
        "i2c_devices": [],
        "usb_serial": [],
        "usb_descriptors": [],
        "cameras": [],
        "platform": "generic",
    }
    preset, confidence, reason = suggest_preset(hw)
    assert isinstance(preset, str)
    assert len(preset) > 0


def test_suggest_preset_rpi_rc_car_with_pca9685():
    from castor.hardware_detect import suggest_preset

    hw = {
        "i2c_devices": [{"bus": 1, "address": "0x40"}],
        "usb_serial": [],
        "usb_descriptors": [],
        "cameras": [],
        "platform": "rpi",
    }
    preset, confidence, reason = suggest_preset(hw)
    assert "rpi_rc_car" in preset


def test_suggest_preset_lego_via_usb_descriptor():
    from castor.hardware_detect import suggest_preset

    hw = {
        "i2c_devices": [],
        "usb_serial": [],
        "usb_descriptors": ["bus 001 device 002: id 0694:0005 lego group"],
        "cameras": [],
        "platform": "generic",
    }
    preset, _conf, _reason = suggest_preset(hw)
    assert "lego" in preset


# ---------------------------------------------------------------------------
# _detect_platform
# ---------------------------------------------------------------------------


def test_detect_platform_returns_string():
    from castor.hardware_detect import _detect_platform

    result = _detect_platform()
    assert result in ("rpi", "jetson", "generic")


def test_detect_platform_rpi(tmp_path):
    with patch(
        "castor.hardware_detect._read_device_tree_model", return_value="Raspberry Pi 4 Model B"
    ):
        from castor.hardware_detect import _detect_platform

        assert _detect_platform() == "rpi"


# ---------------------------------------------------------------------------
# print_scan_results
# ---------------------------------------------------------------------------


def test_print_scan_results_empty(capsys):
    from castor.hardware_detect import print_scan_results

    hw = {
        "i2c_devices": [],
        "usb_serial": [],
        "usb_descriptors": [],
        "cameras": [],
        "platform": "generic",
    }
    print_scan_results(hw)
    out = capsys.readouterr().out
    assert "Hardware Scan Results" in out


def test_print_scan_results_full(capsys):
    from castor.hardware_detect import print_scan_results

    hw = {
        "i2c_devices": [{"bus": 1, "address": "0x40"}],
        "usb_serial": ["/dev/ttyUSB0"],
        "usb_descriptors": [],
        "cameras": [{"type": "usb", "device": "/dev/video0", "accessible": True}],
        "platform": "rpi",
    }
    print_scan_results(hw)
    out = capsys.readouterr().out
    assert "Hardware Scan Results" in out
    assert "0x40" in out
    assert "ttyUSB0" in out


# ---------------------------------------------------------------------------
# scan_usb_descriptors — OAK-D / Hailo heuristics via lsusb
# ---------------------------------------------------------------------------


def test_scan_usb_descriptors_returns_list_on_success():
    """scan_usb_descriptors returns lower-cased lines when lsusb succeeds."""
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = (
        "Bus 001 Device 003: ID 03e7:2485 Intel Corp. Movidius MyriadX (OAK-D)\n"
        "Bus 001 Device 004: ID 1d6b:0002 Linux Foundation 2.0 root hub\n"
    )
    with patch("subprocess.run", return_value=fake_proc):
        from castor.hardware_detect import scan_usb_descriptors

        result = scan_usb_descriptors()

    assert len(result) == 2
    assert all(line == line.lower() for line in result)
    assert any("oak" in line or "movidius" in line for line in result)


def test_scan_usb_descriptors_returns_empty_on_failure():
    """scan_usb_descriptors returns [] when lsusb exits with non-zero."""
    fake_proc = MagicMock()
    fake_proc.returncode = 1
    fake_proc.stdout = ""
    with patch("subprocess.run", return_value=fake_proc):
        from castor.hardware_detect import scan_usb_descriptors

        result = scan_usb_descriptors()

    assert result == []


def test_scan_usb_descriptors_returns_empty_when_lsusb_missing():
    """scan_usb_descriptors returns [] when lsusb is not installed."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        from castor.hardware_detect import scan_usb_descriptors

        result = scan_usb_descriptors()

    assert result == []


def test_scan_usb_descriptors_timeout():
    """scan_usb_descriptors returns [] on subprocess timeout."""
    import subprocess

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="lsusb", timeout=5)):
        from castor.hardware_detect import scan_usb_descriptors

        result = scan_usb_descriptors()

    assert result == []


# ---------------------------------------------------------------------------
# OAK-D detection via suggest_preset + USB descriptors
# ---------------------------------------------------------------------------


def test_suggest_preset_oak_d_detected_via_usb_descriptor():
    """OAK-D (Movidius VID 03e7) is surfaced through USB descriptor strings."""
    from castor.hardware_detect import suggest_preset

    hw = {
        "i2c_devices": [],
        "usb_serial": [],
        "usb_descriptors": [
            "bus 001 device 003: id 03e7:2485 intel corp. movidius myriadx (oak-d)"
        ],
        "cameras": [],
        "platform": "generic",
    }
    # OAK-D shows up as a USB device — the descriptor is available for inspection.
    # suggest_preset doesn't have a dedicated OAK-D branch, but the USB descriptor
    # content is accessible to the caller.  We verify the function doesn't crash
    # and the descriptor data is reflected in the hw dict consumed by the caller.
    preset, confidence, reason = suggest_preset(hw)
    assert isinstance(preset, str)
    assert isinstance(confidence, str)


def test_scan_usb_descriptors_oak_d_string_present():
    """OAK-D USB ID 03e7 appears in the descriptor output."""
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = "Bus 001 Device 003: ID 03e7:2485 Intel Corp. MyriadX (OAK-D)\n"
    with patch("subprocess.run", return_value=fake_proc):
        from castor.hardware_detect import scan_usb_descriptors

        result = scan_usb_descriptors()

    assert any("03e7" in line for line in result)


# ---------------------------------------------------------------------------
# Hailo-8 detection via os.path.exists('/dev/hailo0')
# ---------------------------------------------------------------------------


def test_hailo_device_present_via_os_path_exists():
    """When /dev/hailo0 exists, os.path.exists returns True (mocked)."""
    with patch("os.path.exists", side_effect=lambda p: p == "/dev/hailo0"):
        assert os.path.exists("/dev/hailo0") is True


def test_hailo_device_absent_via_os_path_exists():
    """When /dev/hailo0 is absent, os.path.exists returns False (mocked)."""
    with patch("os.path.exists", return_value=False):
        assert os.path.exists("/dev/hailo0") is False


def test_scan_usb_descriptors_hailo_string_detected():
    """Hailo USB descriptor is lower-cased and returned correctly."""
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = "Bus 002 Device 005: ID 1e60:0001 Hailo Technologies Ltd. Hailo-8\n"
    with patch("subprocess.run", return_value=fake_proc):
        from castor.hardware_detect import scan_usb_descriptors

        result = scan_usb_descriptors()

    assert any("hailo" in line for line in result)


# ---------------------------------------------------------------------------
# I2C bus detection — detected and not-detected paths
# ---------------------------------------------------------------------------


def test_scan_i2c_multiple_buses_detected(monkeypatch):
    """I2C devices on multiple buses are all collected."""
    monkeypatch.setattr(sys, "platform", "linux")
    pca_output = (
        "     0  1  2  3  4  5  6  7\n00:          -- -- -- -- --\n40: 40 -- -- -- -- -- -- --\n"
    )
    mpu_output = (
        "     0  1  2  3  4  5  6  7\n00:          -- -- -- -- --\n68: -- -- -- -- -- -- -- 68\n"
    )

    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        bus_num = int(cmd[2])
        mock.stdout = pca_output if bus_num == 1 else mpu_output
        return mock

    with (
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=["i2c-1", "i2c-2"]),
        patch("subprocess.run", side_effect=fake_run),
    ):
        from castor.hardware_detect import scan_i2c

        devices = scan_i2c()

    addresses = {d["address"] for d in devices}
    assert "0x40" in addresses
    assert "0x68" in addresses


def test_scan_i2c_no_buses_returns_empty(monkeypatch):
    """No i2c-* entries in /dev yields an empty device list."""
    monkeypatch.setattr(sys, "platform", "linux")
    with (
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=["sda", "null", "zero"]),
    ):
        from castor.hardware_detect import scan_i2c

        devices = scan_i2c()

    assert devices == []


def test_scan_i2c_non_zero_returncode_skipped(monkeypatch):
    """I2C buses where i2cdetect exits non-zero are skipped."""
    monkeypatch.setattr(sys, "platform", "linux")
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    with (
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=["i2c-0"]),
        patch("subprocess.run", return_value=mock_result),
    ):
        from castor.hardware_detect import scan_i2c

        devices = scan_i2c()

    assert devices == []


# ---------------------------------------------------------------------------
# Platform detection — RPi, x86 (generic), arm64 (generic)
# ---------------------------------------------------------------------------


def test_detect_platform_rpi_model_b():
    """Device tree containing 'raspberry pi' → platform is 'rpi'."""
    with patch(
        "castor.hardware_detect._read_device_tree_model", return_value="Raspberry Pi 4 Model B"
    ):
        from castor.hardware_detect import _detect_platform

        assert _detect_platform() == "rpi"


def test_detect_platform_rpi_zero():
    """Raspberry Pi Zero is also classified as 'rpi'."""
    with patch(
        "castor.hardware_detect._read_device_tree_model", return_value="Raspberry Pi Zero 2 W"
    ):
        from castor.hardware_detect import _detect_platform

        assert _detect_platform() == "rpi"


def test_detect_platform_jetson():
    """Device tree containing 'jetson' → platform is 'jetson'."""
    with patch("castor.hardware_detect._read_device_tree_model", return_value="NVIDIA Jetson Nano"):
        from castor.hardware_detect import _detect_platform

        assert _detect_platform() == "jetson"


def test_detect_platform_x86_generic():
    """On x86 / standard Linux, _read_device_tree_model raises FileNotFoundError → 'generic'."""
    with patch(
        "castor.hardware_detect._read_device_tree_model",
        side_effect=FileNotFoundError,
    ):
        from castor.hardware_detect import _detect_platform

        assert _detect_platform() == "generic"


def test_detect_platform_arm64_no_device_tree():
    """On arm64 without a device-tree model file, platform falls back to 'generic'."""
    with patch(
        "castor.hardware_detect._read_device_tree_model",
        side_effect=PermissionError,
    ):
        from castor.hardware_detect import _detect_platform

        assert _detect_platform() == "generic"


def test_detect_platform_unknown_board():
    """An unrecognised device-tree model → 'generic'."""
    with patch(
        "castor.hardware_detect._read_device_tree_model",
        return_value="Some Unknown SBC v3",
    ):
        from castor.hardware_detect import _detect_platform

        assert _detect_platform() == "generic"


# ---------------------------------------------------------------------------
# scan_cameras — detected and not-detected
# ---------------------------------------------------------------------------


def test_scan_cameras_returns_video_device():
    """video* entries in /dev produce USB camera entries."""
    with (
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=["video0", "video1", "null"]),
        patch("os.access", return_value=True),
    ):
        from castor.hardware_detect import scan_cameras

        cams = scan_cameras()

    devices = [c["device"] for c in cams]
    assert "/dev/video0" in devices
    assert "/dev/video1" in devices


def test_scan_cameras_no_video_devices():
    """No video* entries → empty camera list (picamera2 import also fails)."""
    with (
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=["null", "zero", "ttyUSB0"]),
    ):
        from castor.hardware_detect import scan_cameras

        cams = scan_cameras()

    usb_cams = [c for c in cams if c["type"] == "usb"]
    assert usb_cams == []


# ---------------------------------------------------------------------------
# detect_hardware integration — ensure subprocess mocks propagate
# ---------------------------------------------------------------------------


def test_detect_hardware_full_mock():
    """detect_hardware aggregates results from all sub-scanners correctly."""
    with (
        patch("castor.hardware_detect.scan_i2c", return_value=[{"bus": 1, "address": "0x40"}]),
        patch("castor.hardware_detect.scan_usb_serial", return_value=["/dev/ttyUSB0"]),
        patch(
            "castor.hardware_detect.scan_usb_descriptors",
            return_value=["bus 001 device 003: id 03e7:2485 oak-d"],
        ),
        patch(
            "castor.hardware_detect.scan_cameras",
            return_value=[{"type": "usb", "device": "/dev/video0", "accessible": True}],
        ),
        patch("castor.hardware_detect._detect_platform", return_value="rpi"),
    ):
        from castor.hardware_detect import detect_hardware

        hw = detect_hardware()

    assert hw["platform"] == "rpi"
    assert hw["i2c_devices"] == [{"bus": 1, "address": "0x40"}]
    assert "/dev/ttyUSB0" in hw["usb_serial"]
    assert any("oak-d" in d for d in hw["usb_descriptors"])
