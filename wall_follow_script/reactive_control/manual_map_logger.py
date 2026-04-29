#!/usr/bin/env python3
"""Record base_link x,y from TF plus left/right wall ranges from /scan to CSV (manual mapping)."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener


def _scan_window_min(
    ranges: list[float],
    angle_min: float,
    angle_inc: float,
    range_min: float,
    range_max: float,
    a0: float,
    a1: float,
) -> float:
    if angle_inc <= 0.0 or not ranges:
        return float("nan")
    i0 = int(round((a0 - angle_min) / angle_inc))
    i1 = int(round((a1 - angle_min) / angle_inc))
    lo, hi = (i0, i1) if i0 <= i1 else (i1, i0)
    lo = max(0, lo)
    hi = min(len(ranges) - 1, hi)
    if hi < lo:
        return float("nan")
    vals = []
    for v in ranges[lo : hi + 1]:
        if math.isfinite(v) and range_min < v < range_max:
            vals.append(v)
    return min(vals) if vals else float("nan")


class ManualMapLogger(Node):
    def __init__(self) -> None:
        super().__init__("manual_map_logger")

        self.declare_parameter("world_frame", "map")
        self.declare_parameter("robot_frame", "base_link")
        self.declare_parameter("scan_topic", "/scan")
        self.declare_parameter("output_csv", "/race_ws/logs/manual_map.csv")
        self.declare_parameter("record_hz", 10.0)
        self.declare_parameter("left_window_rad", (1.10, 1.75))
        self.declare_parameter("right_window_rad", (-1.75, -1.10))

        self._world = str(self.get_parameter("world_frame").value)
        self._robot = str(self.get_parameter("robot_frame").value)
        self._scan_topic = str(self.get_parameter("scan_topic").value)
        out = Path(str(self.get_parameter("output_csv").value))
        out.parent.mkdir(parents=True, exist_ok=True)
        self._csv_path = out
        self._period = 1.0 / max(float(self.get_parameter("record_hz").value), 0.5)

        lw = list(self.get_parameter("left_window_rad").value)
        rw = list(self.get_parameter("right_window_rad").value)
        self._left_a0, self._left_a1 = float(lw[0]), float(lw[1])
        self._right_a0, self._right_a1 = float(rw[0]), float(rw[1])

        self._tf_buffer = Buffer(cache_time=rclpy.duration.Duration(seconds=10.0))
        self._tf_listener = TransformListener(self._tf_buffer, self)

        scan_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(LaserScan, self._scan_topic, self._scan_cb, scan_qos)
        self._last_scan: LaserScan | None = None

        self._file = open(self._csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(
            [
                "time_sec",
                "frame_id",
                "x",
                "y",
                "z",
                "yaw_rad",
                "left_wall_m",
                "right_wall_m",
                "scan_stamp_sec",
            ]
        )
        self._file.flush()

        self.create_timer(self._period, self._tick)
        self.get_logger().info(
            f"Logging TF {self._world}->{self._robot} + {self._scan_topic} to {self._csv_path} at {1.0/self._period:.1f} Hz"
        )

    def destroy_node(self) -> bool:
        try:
            self._file.close()
        except OSError:
            pass
        return super().destroy_node()

    def _scan_cb(self, msg: LaserScan) -> None:
        self._last_scan = msg

    def _tick(self) -> None:
        scan = self._last_scan
        if scan is None:
            return
        try:
            t = self._tf_buffer.lookup_transform(
                self._world,
                self._robot,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.15),
            )
        except Exception as e:
            self.get_logger().warn(f"TF lookup {self._world}->{self._robot} failed: {e}", throttle_duration_sec=2.0)
            return

        tr = t.transform.translation
        q = t.transform.rotation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        ranges = list(scan.ranges)
        left = _scan_window_min(
            ranges,
            scan.angle_min,
            scan.angle_increment,
            scan.range_min,
            scan.range_max,
            self._left_a0,
            self._left_a1,
        )
        right = _scan_window_min(
            ranges,
            scan.angle_min,
            scan.angle_increment,
            scan.range_min,
            scan.range_max,
            self._right_a0,
            self._right_a1,
        )

        stamp = self.get_clock().now().seconds_nanoseconds()
        tsec = stamp[0] + stamp[1] * 1e-9
        scan_sec = scan.header.stamp.sec + scan.header.stamp.nanosec * 1e-9
        self._writer.writerow(
            [
                f"{tsec:.6f}",
                self._world,
                f"{tr.x:.6f}",
                f"{tr.y:.6f}",
                f"{tr.z:.6f}",
                f"{yaw:.6f}",
                f"{left:.6f}" if math.isfinite(left) else "",
                f"{right:.6f}" if math.isfinite(right) else "",
                f"{scan_sec:.6f}",
            ]
        )
        self._file.flush()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ManualMapLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
