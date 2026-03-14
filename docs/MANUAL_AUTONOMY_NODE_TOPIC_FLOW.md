# Manual + Autonomy Node/Topic Map

This is the current communication map for the unified launch:

- `ros2 launch /race_ws/bringup.launch.py`

It combines:

- manual RC control (`f1tenth_stack` + `joy_rc_steer_fix.yaml`)
- autonomy wall-follow (`reactive_control`)
- LiDAR bridge (`pointcloud_to_laserscan`)

---

## Node -> Topic Chart

| Node | Subscribes | Publishes | Role |
|---|---|---|---|
| `joy_node` | joystick device (`/dev/input/js0`) | `/joy` | Reads RC input from controller |
| `joy_teleop` | `/joy` | `/teleop` (`AckermannDriveStamped`) | Converts RC axes/buttons to manual drive commands |
| `ackermann_mux` | `/teleop`, `/drive` | `ackermann_cmd` | Chooses command source (manual has higher priority) |
| `ackermann_to_vesc_node` | `ackermann_cmd` | `/commands/motor/speed`, `/commands/servo/position` | Converts Ackermann command to VESC motor/servo commands |
| `vesc_driver_node` | `/commands/motor/speed`, `/commands/servo/position` | `/sensors/core` and VESC telemetry topics | Sends commands to hardware and reports state |
| `vesc_to_odom_node` | VESC state topics | `/odom` | Produces wheel odometry |
| `livox_ros_driver2_node` | (device/network data) | `/livox/lidar`, `/livox/imu` | Publishes 3D LiDAR/IMU stream |
| `pointcloud_to_laserscan_node` | `/livox/lidar` | `/scan` | Converts PointCloud2 into LaserScan |
| `wall_follow_node` (`reactive_control`) | `/scan`, `/joy` | `/drive` | Autonomy controller (slow hallway behavior + safety latches) |
| `static_transform_publisher` | - | `/tf_static` | Publishes fixed frame transform(s) |

---

## Priority / Override Rules

- `joy_teleop` manual command topic: `/teleop`
- autonomy command topic: `/drive`
- `ackermann_mux` priorities (from runtime logs):
  - `joystick` (`/teleop`) priority `100`
  - `navigation` (`/drive`) priority `10`
- Result: manual override wins when active.

---

## End-to-End Flowchart

```mermaid
flowchart LR
  RC[RC Controller<br/>/dev/input/js0] --> JN[joy_node]
  JN -->|/joy| JT[joy_teleop]
  JT -->|/teleop| MUX[ackermann_mux]

  LIVOX[livox_ros_driver2_node] -->|/livox/lidar| P2L[pointcloud_to_laserscan]
  P2L -->|/scan| WF[wall_follow_node]
  JN -->|/joy (latch input)| WF
  WF -->|/drive| MUX

  MUX -->|ackermann_cmd| A2V[ackermann_to_vesc_node]
  A2V -->|/commands/motor/speed| VESC[vesc_driver_node]
  A2V -->|/commands/servo/position| VESC
  VESC -->|hardware IO| CAR[Motor + Steering]
  VESC -->|state topics| ODOM[vesc_to_odom_node]
  ODOM -->|/odom| NAV[Localization/monitoring consumers]
```

---

## Behavior Notes (Current)

- Autonomy default speed target: `0.25 m/s` (clamped min `0.0`, max `0.35`).
- Wall-follow node uses LiDAR safety rules and can latch stop on:
  - manual override button event
  - prolonged invalid LiDAR input.
- Unified launch passes working RC config:
  - `config/joy_rc_steer_fix.yaml`
  - deadman/switch index: `[1]`.
