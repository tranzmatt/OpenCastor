"""Hardware component registry for RCAN v2.2.

Provides auto-detection, schema validation, and Firestore registration
of individual hardware components (NPU, cameras, actuators, sensors, etc.)
attached to a robot.

Component IDs are deterministic: sha256(rrn + type + model)[:8].
This ensures re-registration produces the same IDs (idempotent).
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path
from typing import Any

# ── Component types (RCAN v2.2 §7.3) ─────────────────────────────────────────

COMPONENT_TYPES = {
    "npu",  # Neural Processing Unit
    "gpu",  # Graphics Processing Unit
    "cpu",  # Central Processing Unit (main compute)
    "camera",  # RGB or RGB-D camera
    "lidar",  # LiDAR sensor
    "imu",  # Inertial Measurement Unit
    "microphone",  # Audio input
    "speaker",  # Audio output
    "motor",  # Motor controller or servo
    "battery",  # Power management / battery
    "estop",  # Hardware emergency stop device
    "gps",  # GPS / GNSS receiver
    "display",  # LCD / display panel
    "radio",  # Wireless radio (WiFi, BLE, LoRa)
    "other",  # Anything not fitting the above
}


def make_component_id(rrn: str, component_type: str, model: str) -> str:
    """Deterministic component ID: sha256(rrn:type:model)[:8]."""
    raw = f"{rrn}:{component_type}:{model}".encode()
    return hashlib.sha256(raw).hexdigest()[:8]


def _run(cmd: list[str]) -> str:
    """Run a subprocess and return stdout, empty string on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout
    except Exception:
        return ""


# ── Auto-detection ────────────────────────────────────────────────────────────


def detect_hailo_npu() -> list[dict[str, Any]]:
    """Detect Hailo-8/8L NPU via /dev/hailo* or hailo CLI."""
    components: list[dict[str, Any]] = []
    hailo_devices = list(Path("/dev").glob("hailo*"))
    if hailo_devices:
        # Try to get firmware version via hailortcli
        fw_version = "unknown"
        out = _run(["hailortcli", "fw-control", "identify"])
        for line in out.splitlines():
            if "Firmware version" in line or "firmware_version" in line.lower():
                fw_version = line.split(":")[-1].strip()
                break
        for dev in hailo_devices:
            components.append(
                {
                    "type": "npu",
                    "model": "Hailo-8",
                    "manufacturer": "Hailo Technologies",
                    "device_path": str(dev),
                    "firmware_version": fw_version,
                    "status": "detected",
                }
            )
    return components


def detect_oak_d_cameras() -> list[dict[str, Any]]:
    """Detect OAK-D / DepthAI cameras via lsusb (Luxonis vendor ID 03e7)."""
    components: list[dict[str, Any]] = []
    lsusb_out = _run(["lsusb"])
    oak_models = {
        "f63b": "OAK-D",
        "2485": "OAK-1",
        "2488": "OAK-D-Lite",
        "2489": "OAK-D-Pro",
    }
    for line in lsusb_out.splitlines():
        if "03e7:" in line:
            pid = ""
            if "03e7:" in line:
                try:
                    pid = line.split("03e7:")[1].split()[0].rstrip(",").lower()
                except IndexError:
                    pid = ""
            model = oak_models.get(pid, "OAK-D (unknown model)")
            components.append(
                {
                    "type": "camera",
                    "model": model,
                    "manufacturer": "Luxonis",
                    "device_path": "USB",
                    "firmware_version": "unknown",
                    "status": "detected",
                    "capabilities": ["rgb", "stereo_depth", "imu"],
                }
            )
    return components


_V4L2_SKIP_PATTERNS = (
    # Raspberry Pi ISP internal pipeline stages — not real cameras
    "pispbe",
    "rpi-hevc",
    "rpi-h264",
    "rpi-isp",
    "rpivid",
    # Codec devices
    "decoder",
    "encoder",
    "m2m",
    # OAK — already handled via lsusb
    "myriad",
    "luxonis",
)


def detect_usb_cameras() -> list[dict[str, Any]]:
    """Detect V4L2 cameras (non-OAK, non-ISP) via /dev/video*.

    Skips Raspberry Pi ISP pipeline stages and codec devices which
    appear as /dev/video* but are not real camera inputs.
    """
    components: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for dev in sorted(Path("/dev").glob("video*")):
        try:
            name_path = Path(f"/sys/class/video4linux/{dev.name}/name")
            name = name_path.read_text().strip() if name_path.exists() else dev.name

            lower_name = name.lower()
            if any(pat in lower_name for pat in _V4L2_SKIP_PATTERNS):
                continue
            if name in seen_names:
                continue
            seen_names.add(name)

            components.append(
                {
                    "type": "camera",
                    "model": name,
                    "manufacturer": "unknown",
                    "device_path": str(dev),
                    "firmware_version": "unknown",
                    "status": "detected",
                    "capabilities": ["rgb"],
                }
            )
        except Exception:
            continue
    return components


def detect_main_cpu() -> list[dict[str, Any]]:
    """Detect main CPU from /proc/cpuinfo or platform."""
    cpu_model = platform.processor() or "unknown"
    # Raspberry Pi: parse /proc/cpuinfo for Model
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("Model") or line.startswith("Hardware"):
                    cpu_model = line.split(":")[-1].strip()
                    if "Pi" in cpu_model or "BCM" in cpu_model:
                        break
    except Exception:
        pass
    cpu_count = ""
    try:
        import os

        cpu_count = str(os.cpu_count() or "")
    except Exception:
        pass
    return [
        {
            "type": "cpu",
            "model": cpu_model,
            "manufacturer": "unknown",
            "firmware_version": platform.release(),
            "status": "active",
            "cpu_count": cpu_count,
        }
    ]


def detect_components(rrn: str = "RRN-UNKNOWN") -> list[dict[str, Any]]:
    """Auto-detect all hardware components and assign deterministic IDs.

    Returns a list of component dicts ready for Firestore / RCAN config.
    """
    raw: list[dict[str, Any]] = []
    raw.extend(detect_main_cpu())
    raw.extend(detect_hailo_npu())
    raw.extend(detect_oak_d_cameras())
    raw.extend(detect_usb_cameras())

    # Assign deterministic IDs and rrn reference
    components = []
    for c in raw:
        comp_id = make_component_id(rrn, c["type"], c["model"])
        components.append(
            {
                "id": comp_id,
                "rrn": rrn,
                **c,
            }
        )
    return components


# ── Config helpers ────────────────────────────────────────────────────────────


def components_from_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the components: section from a RCAN config dict."""
    return config.get("components", [])


def merge_components(
    detected: list[dict[str, Any]],
    configured: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge auto-detected and config-declared components.

    Config-declared entries take precedence (override detected fields).
    Detected entries with no matching config entry are appended.
    """
    merged: dict[str, dict[str, Any]] = {}
    for comp in detected:
        merged[comp["id"]] = comp
    for comp in configured:
        cid = comp.get("id", "")
        if cid in merged:
            merged[cid] = {**merged[cid], **comp}
        else:
            merged[cid] = comp
    return list(merged.values())


# ── Firestore registration ────────────────────────────────────────────────────


def register_components_to_firestore(
    rrn: str,
    components: list[dict[str, Any]],
) -> tuple[int, list[str]]:
    """Write components to Firestore robots/{rrn}/components/{id}.

    Returns (success_count, error_messages).
    """
    try:
        from google.cloud import firestore  # type: ignore[import-untyped]
        from google.oauth2 import service_account  # type: ignore[import-untyped]

        sa_path = Path.home() / ".config" / "opencastor" / "firebase-sa-key.json"
        creds = service_account.Credentials.from_service_account_file(
            str(sa_path),
            scopes=["https://www.googleapis.com/auth/datastore"],
        )
        db = firestore.Client(project="opencastor", credentials=creds)
        robot_ref = db.collection("robots").document(rrn)
        comps_ref = robot_ref.collection("components")

        ok = 0
        errors: list[str] = []
        for comp in components:
            comp_id = comp.get("id", "unknown")
            try:
                comps_ref.document(comp_id).set(comp, merge=True)
                ok += 1
            except Exception as e:
                errors.append(f"{comp_id}: {e}")

        # Also store component summary on the robot doc itself (for Fleet screen)
        try:
            summary = [
                {"id": c.get("id"), "type": c.get("type"), "model": c.get("model")}
                for c in components
            ]
            robot_ref.update({"component_count": len(components), "components_summary": summary})
        except Exception:
            pass

        return ok, errors

    except ImportError:
        return 0, ["firebase-admin not installed"]
    except Exception as e:
        return 0, [str(e)]
