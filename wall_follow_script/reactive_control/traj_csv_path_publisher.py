"""Publish nav_msgs/Path from TUM traj_race_cl.csv (Derek raceline stack)."""

from __future__ import annotations

import math
import sys
from pathlib import Path as PathlibPath

import rclpy
from geometry_msgs.msg import PoseStamped, Quaternion
from nav_msgs.msg import Path
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from reactive_control.traj_csv_io import load_traj_xy_yaw


def _yaw_to_quat(yaw: float) -> Quaternion:
    q = Quaternion()
    q.x = 0.0
    q.y = 0.0
    q.z = math.sin(yaw * 0.5)
    q.w = math.cos(yaw * 0.5)
    return q


def _make_nav_path(rows: list[tuple[float, float, float]]) -> Path:
    msg = Path()
    for x, y, psi in rows:
        ps = PoseStamped()
        ps.pose.position.x = x
        ps.pose.position.y = y
        ps.pose.position.z = 0.0
        ps.pose.orientation = _yaw_to_quat(psi)
        msg.poses.append(ps)
    return msg


class TrajCsvPathPublisher(Node):
    def __init__(self) -> None:
        super().__init__("traj_csv_path_publisher")

        self.declare_parameter("trajectory_csv", "")
        self.declare_parameter("path_topic", "/global_path")
        self.declare_parameter("frame_id", "odom")
        self.declare_parameter("publish_hz", 1.0)
        self.declare_parameter("step", 1)

        csv_path = PathlibPath(str(self.get_parameter("trajectory_csv").value).strip())
        topic = str(self.get_parameter("path_topic").value)
        self._frame_id = str(self.get_parameter("frame_id").value)
        hz = float(self.get_parameter("publish_hz").value)
        step = int(self.get_parameter("step").value)

        if not csv_path.is_file():
            self.get_logger().fatal(f"trajectory_csv is not a file: {csv_path}")
            raise SystemExit(1)
        if step < 1:
            self.get_logger().fatal("step must be >= 1")
            raise SystemExit(1)

        rows = load_traj_xy_yaw(csv_path)[::step]
        self._path_msg = _make_nav_path(rows)
        self._path_msg.header.frame_id = self._frame_id

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._pub = self.create_publisher(Path, topic, qos)

        period = max(1.0 / hz, 0.05) if hz > 0.0 else 1.0
        self.create_timer(period, self._publish_cb)

        self.get_logger().info(
            f"Loaded {len(rows)} poses from {csv_path}; publishing Path on {topic!r} "
            f"frame_id={self._frame_id!r} at {1.0/period:.2f} Hz"
        )

    def _publish_cb(self) -> None:
        now = self.get_clock().now().to_msg()
        self._path_msg.header.stamp = now
        for p in self._path_msg.poses:
            p.header.stamp = now
            p.header.frame_id = self._frame_id
        self._pub.publish(self._path_msg)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    try:
        node = TrajCsvPathPublisher()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        sys.exit(code)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
