"""
RCAN §20 Telemetry Field Registry — standard field names.

Use these constants when emitting telemetry to ensure cross-runtime
compatibility. Implementations SHOULD use these names for standard fields.

Spec: https://rcan.dev/spec/section-20/
"""

from __future__ import annotations

# --- Joint fields (per-joint, indexed or named) ---
JOINT_POSITION = "joint_position"  # float | list[float] — radians
JOINT_VELOCITY = "joint_velocity"  # float | list[float] — rad/s
JOINT_EFFORT = "joint_effort"  # float | list[float] — Nm
JOINT_TEMPERATURE = "joint_temperature"  # float | list[float] — Celsius
JOINT_NAMES = "joint_names"  # list[str] — ordered joint name list

# --- Mobile robot state ---
LINEAR_VELOCITY = "linear_velocity"  # float — m/s (forward)
ANGULAR_VELOCITY = "angular_velocity"  # float — rad/s (yaw rate)
LINEAR_VELOCITY_X = "linear_velocity_x"  # float — m/s
LINEAR_VELOCITY_Y = "linear_velocity_y"  # float — m/s
LINEAR_VELOCITY_Z = "linear_velocity_z"  # float — m/s
ANGULAR_VELOCITY_X = "angular_velocity_x"  # float — rad/s
ANGULAR_VELOCITY_Y = "angular_velocity_y"  # float — rad/s
ANGULAR_VELOCITY_Z = "angular_velocity_z"  # float — rad/s

# --- Position / pose ---
POSITION_X = "position_x"  # float — meters
POSITION_Y = "position_y"  # float — meters
POSITION_Z = "position_z"  # float — meters
ORIENTATION_W = "orientation_w"  # float — quaternion w
ORIENTATION_X = "orientation_x"  # float — quaternion x
ORIENTATION_Y = "orientation_y"  # float — quaternion y
ORIENTATION_Z = "orientation_z"  # float — quaternion z

# --- Power ---
BATTERY_VOLTAGE = "battery_voltage"  # float — Volts
BATTERY_CURRENT = "battery_current"  # float — Amps
BATTERY_PERCENT = "battery_percent"  # float — 0.0-100.0
BATTERY_CHARGING = "battery_charging"  # bool

# --- Compute ---
CPU_PERCENT = "cpu_percent"  # float — 0.0-100.0
MEMORY_PERCENT = "memory_percent"  # float — 0.0-100.0
GPU_PERCENT = "gpu_percent"  # float — 0.0-100.0
NPU_PERCENT = "npu_percent"  # float — 0.0-100.0
TEMPERATURE_CPU = "temperature_cpu"  # float — Celsius
TEMPERATURE_GPU = "temperature_gpu"  # float — Celsius

# --- Sensors ---
LIDAR_SCAN_COUNT = "lidar_scan_count"  # int — points in last scan
CAMERA_FPS = "camera_fps"  # float — frames/sec
DEPTH_MIN_M = "depth_min_m"  # float — meters
DEPTH_MAX_M = "depth_max_m"  # float — meters

# --- Safety ---
ESTOP_ACTIVE = "estop_active"  # bool
SAFETY_ZONE_BREACH = "safety_zone_breach"  # bool
CONFIDENCE_SCORE = "confidence_score"  # float — 0.0-1.0

# --- Runtime ---
UPTIME_SECONDS = "uptime_seconds"  # float
RCAN_MESSAGES_SENT = "rcan_messages_sent"  # int
RCAN_MESSAGES_RECV = "rcan_messages_recv"  # int
ACTIVE_SKILL = "active_skill"  # str | None — currently executing skill
