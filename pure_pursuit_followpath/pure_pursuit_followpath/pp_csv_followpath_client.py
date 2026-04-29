import csv
from pathlib import Path
from typing import List, Optional, Tuple

import rclpy
from geometry_msgs.msg import PoseStamped, Quaternion
from nav2_msgs.action import FollowPath
from nav_msgs.msg import Path as NavPath
from rclpy.action import ActionClient
from rclpy.node import Node


def yaw_to_quat(yaw: float) -> Quaternion:
    # roll=pitch=0
    q = Quaternion()
    q.x = 0.0
    q.y = 0.0
    q.z = float(__import__("math").sin(yaw * 0.5))
    q.w = float(__import__("math").cos(yaw * 0.5))
    return q


def load_tum_race_trajectory_csv(csv_path: str) -> List[Tuple[float, float, Optional[float]]]:
    """
    Load TUM 'Race Trajectory' CSV.

    Expected columns include at least x_m, y_m.
    If psi_rad exists, we use it for orientation; otherwise leave None.
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
            x = float(r.get("x_m") or r.get("x") or r.get("x_ref_m") or r.get("x_meters"))
            y = float(r.get("y_m") or r.get("y") or r.get("y_ref_m") or r.get("y_meters"))
            psi_raw = r.get("psi_rad") or r.get("psi") or r.get("psi_racetraj_rad")
            psi = float(psi_raw) if psi_raw is not None and psi_raw != "" else None
            out.append((x, y, psi))
        return out


class CsvFollowPathClient(Node):
    def __init__(self):
        super().__init__("pp_csv_followpath_client")
        self.declare_parameter("csv_path", "")
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("action_name", "/follow_path")

        action_name = str(self.get_parameter("action_name").value)
        self.client = ActionClient(self, FollowPath, action_name)

    def run(self):
        csv_path = str(self.get_parameter("csv_path").value)
        if not csv_path:
            raise RuntimeError("csv_path parameter is required")

        frame_id = str(self.get_parameter("frame_id").value)

        pts = load_tum_race_trajectory_csv(csv_path)
        path_msg = NavPath()
        path_msg.header.stamp = self.get_clock().now().to_msg()
        path_msg.header.frame_id = frame_id

        for (x, y, psi) in pts:
            ps = PoseStamped()
            ps.header = path_msg.header
            ps.pose.position.x = float(x)
            ps.pose.position.y = float(y)
            ps.pose.position.z = 0.0
            if psi is not None:
                ps.pose.orientation = yaw_to_quat(float(psi))
            else:
                ps.pose.orientation.w = 1.0
            path_msg.poses.append(ps)

        self.get_logger().info(f"Waiting for FollowPath action server...")
        if not self.client.wait_for_server(timeout_sec=10.0):
            raise RuntimeError("FollowPath action server not available")

        goal = FollowPath.Goal()
        goal.path = path_msg

        self.get_logger().info(f"Sending FollowPath goal with {len(path_msg.poses)} poses from '{csv_path}'")
        send_future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()
        if not goal_handle.accepted:
            raise RuntimeError("Goal rejected")

        self.get_logger().info("Goal accepted, waiting for result...")
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        self.get_logger().info("Done.")


def main():
    rclpy.init()
    node = CsvFollowPathClient()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()

