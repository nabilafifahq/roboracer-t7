import csv
import math
from pathlib import Path
from typing import List, Optional, Tuple

import rclpy
from geometry_msgs.msg import PoseStamped, Quaternion
from mav_msgs.msg import Path as MavPath
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


def yaw_to_quat(yaw: float) -> Quaternion:
    q = Quaternion()
    q.x = 0.0
    q.y = 0.0
    q.z = float(math.sin(yaw * 0.5))
    q.w = float(math.cos(yaw * 0.5))
    return q


def load_optimizer_output_csv(csv_path: str) -> List[Tuple[float, float, Optional[float]]]:
    """
    Load optimizer output CSV.

    Required columns: x_m, y_m
    Optional: psi_rad

    Other columns (s_m, kappa_radpm, vx_mps, ax_mps2) are ignored by this
    pose-only Path container.
    """
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(csv_path)

    with p.open("r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not rows:
            raise ValueError("CSV has no rows")

        out: List[Tuple[float, float, Optional[float]]] = []
        for r in rows:
            x = float(r["x_m"])
            y = float(r["y_m"])
            psi_raw = r.get("psi_rad")
            psi = float(psi_raw) if psi_raw is not None and psi_raw != "" else None
            out.append((x, y, psi))
        return out


class CsvToMavPathPublisher(Node):
    def __init__(self):
        super().__init__("csv_to_mav_path_publisher")

        self.declare_parameter("csv_path", "")
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("path_topic", "/optimizer/path")
        self.declare_parameter("publish_period_s", 1.0)

        path_topic = str(self.get_parameter("path_topic").value)

        # "Latch"-like behavior in ROS 2: transient_local durability.
        qos = QoSProfile(depth=1)
        qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        qos.reliability = ReliabilityPolicy.RELIABLE
        self.pub = self.create_publisher(MavPath, path_topic, qos)

        period = float(self.get_parameter("publish_period_s").value)
        self.timer = self.create_timer(max(period, 0.05), self._on_timer)

        self._last_csv_path: Optional[str] = None
        self._cached_msg: Optional[MavPath] = None

    def _build_path_msg(self, csv_path: str, frame_id: str) -> MavPath:
        pts = load_optimizer_output_csv(csv_path)

        msg = MavPath()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = frame_id

        for (x, y, psi) in pts:
            ps = PoseStamped()
            ps.header = msg.header
            ps.pose.position.x = float(x)
            ps.pose.position.y = float(y)
            ps.pose.position.z = 0.0
            if psi is not None:
                ps.pose.orientation = yaw_to_quat(float(psi))
            else:
                ps.pose.orientation.w = 1.0
            msg.poses.append(ps)

        return msg

    def _on_timer(self):
        csv_path = str(self.get_parameter("csv_path").value)
        frame_id = str(self.get_parameter("frame_id").value)

        if not csv_path:
            # Don't spam; just idle until configured.
            return

        if self._cached_msg is None or self._last_csv_path != csv_path:
            self._cached_msg = self._build_path_msg(csv_path, frame_id)
            self._last_csv_path = csv_path
            self.get_logger().info(f"Loaded optimizer CSV '{csv_path}' with {len(self._cached_msg.poses)} poses.")
        else:
            # Refresh header stamp so downstream can see it as "current".
            self._cached_msg.header.stamp = self.get_clock().now().to_msg()
            for ps in self._cached_msg.poses:
                ps.header.stamp = self._cached_msg.header.stamp

        self.pub.publish(self._cached_msg)


def main():
    rclpy.init()
    node = CsvToMavPathPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

