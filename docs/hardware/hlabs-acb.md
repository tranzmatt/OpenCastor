# HLabs ACB v2.0 Hardware Guide

The **HLaboratories Actuator Control Board v2.0** (ACB v2.0) is an open-source STM32G474-based
motor controller for 3-phase BLDC motors. OpenCastor ships first-class support starting in
v2026.3.10.1.

---

## Overview

| Spec | Value |
|------|-------|
| MCU | STM32G474 (Cortex-M4, 170MHz) |
| Motor type | 3-phase BLDC |
| Supply voltage | 12V – 30V |
| Peak current | 40A |
| Communication | USB-C (full-speed serial) + CAN Bus (1Mbit/s) |
| Encoder | Magnetic (AS5047) or hall sensors |
| Firmware | Open-source (HLabs GitHub) |
| Form factor | 50mm × 50mm |

**Why ACB v2.0?** It's one of the few open-source BLDC controllers that speaks CAN Bus
natively at reasonable cost. The STM32G474 has a dedicated FDCAN peripheral, so you get
true hardware CAN without an external transceiver IC. This matters for multi-joint robots
(arms, bipeds) where you daisy-chain multiple ACBs on a single CAN bus.

---

## Wiring

### Power

```
Battery (12V–30V) ──► XT60 connector on ACB
GND ──────────────►  XT60 GND
```

> **Warning:** Never connect USB-C while the motor is drawing more than ~5A. The USB data
> lines are isolated from the power stage, but a transient spike can reset the STM32.

### USB-C

Standard USB-C cable to host. The ACB enumerates as a CDC virtual serial port (CP2102N
or native STM32 USB-CDC depending on firmware version).

```
Host USB-C ──► ACB USB-C port (left side of board)
```

OpenCastor auto-detects via VID/PID:

| VID | PID | Description |
|-----|-----|-------------|
| `0x0483` | `0x5740` | STM32 native USB-CDC |
| `0x10C4` | `0xEA60` | CP2102N UART bridge |

### CAN Bus

```
Host CAN adapter ──► ACB CAN-H / CAN-L (JST GH 4-pin)
                     Pin 1: CAN-H
                     Pin 2: CAN-L
                     Pin 3: GND
                     Pin 4: (not connected)
```

Terminate the bus with 120Ω between CAN-H and CAN-L at each end. Most USB-CAN adapters
(e.g., PEAK PCAN-USB, CANable) include a built-in terminator switch.

### Motor Phases

Three-phase BLDC motor connects to the three screw terminals on the ACB (U/V/W). Phase
order determines rotation direction — swap any two phases to reverse.

---

## RCAN Configuration

### USB-C (simplest setup)

```yaml
drivers:
- id: left_wheel
  protocol: acb
  port: auto          # auto-detects first ACB by USB VID/PID
  baud: 115200
  node_id: 1
  pole_pairs: 7
```

`port: auto` scans `/dev/tty*` for known HLabs VID/PID combinations. Override with an
explicit path if you have multiple ACBs:

```yaml
port: /dev/ttyUSB0
```

### CAN Bus (multi-joint)

```yaml
drivers:
- id: joint_0
  protocol: acb
  transport: can
  can_interface: can0       # Linux SocketCAN interface
  can_bitrate: 1000000      # 1Mbit/s
  node_id: 1
  pole_pairs: 14

- id: joint_1
  protocol: acb
  transport: can
  can_interface: can0
  node_id: 2
  pole_pairs: 14
```

Bring up the CAN interface:

```bash
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
```

### CAN ARB ID format

OpenCastor uses an 11-bit standard CAN frame:

```
ARB ID = (node_id << 5) | cmd_id
```

| cmd_id | Command |
|--------|---------|
| `0x00` | SET_VELOCITY |
| `0x01` | SET_POSITION |
| `0x02` | GET_TELEMETRY |
| `0x03` | CALIBRATE |
| `0x04` | ESTOP |

---

## RCAN Profiles

Three ready-made profiles ship with OpenCastor:

```bash
castor hub install hlabs/acb-single      # single-axis (wheel / winch)
castor hub install hlabs/acb-arm-3dof    # 3-DOF robot arm
castor hub install hlabs/acb-biped-6dof  # 6-DOF biped (3 per leg)
```

Or reference them in RCAN:

```yaml
profiles:
  - hlabs/acb-single
```

The biped profile sets up CAN Bus with 6 nodes (IDs 1–6), appropriate pole pairs for the
HLabs recommended motor, and calibration defaults.

---

## Calibration

Calibration determines:
1. **Pole pairs** — number of electrical cycles per mechanical revolution
2. **Zero electrical angle** — offset between encoder zero and motor zero
3. **PID gains** — proportional/integral/derivative for the velocity controller

Run interactively:

```bash
castor wizard          # includes ACB onboarding flow
```

Or via API:

```bash
curl -X POST http://localhost:8000/api/drivers/left_wheel/calibrate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pole_pairs": 7}'
```

A `CalibrationResult` is returned:

```json
{
  "ok": true,
  "pole_pairs": 7,
  "zero_angle_deg": 12.4,
  "pid_kp": 0.8,
  "pid_ki": 0.1,
  "pid_kd": 0.02,
  "duration_s": 4.2
}
```

---

## Telemetry

The ACB streams encoder telemetry at 50Hz. Access via:

```bash
curl http://localhost:8000/api/drivers/left_wheel/telemetry
```

```json
{
  "position_deg": 142.3,
  "velocity_rpm": 320.5,
  "current_a": 2.1,
  "voltage_v": 24.0,
  "errors": 0,
  "mode": "hardware"
}
```

Prometheus metrics are also emitted (requires monitoring profile):

```
opencastor_acb_position_deg{driver="left_wheel"} 142.3
opencastor_acb_velocity_rpm{driver="left_wheel"} 320.5
opencastor_acb_current_a{driver="left_wheel"} 2.1
```

---

## Firmware Flash

To update ACB firmware via DFU mode:

```bash
# Put ACB into DFU mode: hold BOOT button, press RESET, release both
castor flash --id left_wheel --firmware https://github.com/hlaboratories/acb/releases/latest/download/acb_v2.bin
```

Requires `dfu-util`:

```bash
sudo apt install dfu-util   # Debian/Ubuntu/Raspberry Pi OS
brew install dfu-util       # macOS
```

> **Note:** Only GitHub releases URLs from `github.com/hlaboratories/` are accepted
> (SSRF-safe validation). Custom firmware URLs are not supported via the CLI.

---

## Hardware Scan

```bash
curl http://localhost:8000/api/hardware/scan
```

Returns all detected HLabs devices:

```json
{
  "detected": [
    {"type": "acb_v2", "port": "/dev/ttyUSB0", "vid": "0x0483", "pid": "0x5740", "serial": "ACB2_001"},
    {"type": "acb_v2", "port": "/dev/ttyUSB1", "vid": "0x0483", "pid": "0x5740", "serial": "ACB2_002"}
  ]
}
```

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `port: auto` not finding ACB | udev rules missing | `sudo udevadm control --reload-rules && sudo udevadm trigger` |
| CAN interface not found | kernel module not loaded | `sudo modprobe can && sudo modprobe can_raw` |
| Calibration fails immediately | Motor not powered | Check XT60 power connection |
| Telemetry all zeros | Wrong node_id | Check ACB DIP switches match `node_id` in RCAN |
| Flash fails: DFU device not found | Not in DFU mode | Hold BOOT before pressing RESET |
| `TypeError` on `move()` | Old AcbDriver cached | `pip install --upgrade opencastor` |

---

## Links

- [HLaboratories GitHub](https://github.com/hlaboratories) — ACB firmware + schematics
- [OpenCastor Discord](https://discord.gg/jMjA8B26Bq) — `#hardware-hlabs` channel
- [Hardware Guide](../hardware-guide.md) — general hardware setup

---

*Part of the [OpenCastor](https://github.com/craigm26/OpenCastor) project — Apache 2.0*
