"""Subscribe to nav_msgs/Path on /global_path and send Nav2 controller_server FollowPath goals."""

from __future__ import annotations

import threading

import rclpy
from action_msgs.msg import GoalStatus
from nav2_msgs.action import FollowPath
from nav_msgs.msg import Path
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy


def _path_qos() -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=2,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )


class GlobalPathFollowBridge(Node):
    def __init__(self) -> None:
        super().__init__("global_path_follow_bridge")

        self.declare_parameter("path_topic", "/global_path")
        self.declare_parameter("follow_path_action", "/follow_path")
        self.declare_parameter("controller_id", "")
        self.declare_parameter("goal_checker_id", "")

        path_topic = str(self.get_parameter("path_topic").value)
        action_name = str(self.get_parameter("follow_path_action").value)
        self._controller_id = str(self.get_parameter("controller_id").value)
        self._goal_checker_id = str(self.get_parameter("goal_checker_id").value)

        self._lock = threading.Lock()
        self._goal_handle = None

        self._client = ActionClient(self, FollowPath, action_name)
        self.create_subscription(Path, path_topic, self._on_path, _path_qos())
        self.get_logger().info(
            f"Bridging Path topic {path_topic!r} -> action {action_name!r} (wait for Nav2 controller_server)"
        )

    def _cancel_active(self) -> None:
        with self._lock:
            gh = self._goal_handle
            self._goal_handle = None
        if gh is not None:
            gh.cancel_goal_async()

    def _on_path(self, msg: Path) -> None:
        if not msg.poses:
            self.get_logger().warn("Ignoring empty Path")
            return
        if not self._client.wait_for_server(timeout_sec=2.0):
            self.get_logger().warn("FollowPath action server not available yet")
            return

        goal = FollowPath.Goal()
        goal.path = msg
        goal.controller_id = self._controller_id
        goal.goal_checker_id = self._goal_checker_id

        self._cancel_active()
        send_future = self._client.send_goal_async(goal)
        send_future.add_done_callback(self._on_goal_sent)

    def _on_goal_sent(self, future) -> None:
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn("FollowPath goal rejected")
            return
        with self._lock:
            self._goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_result)

    def _on_result(self, future) -> None:
        try:
            res = future.result().status
            if res not in (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_CANCELED):
                self.get_logger().warn(f"FollowPath finished with status {res}")
        except Exception as ex:  # noqa: BLE001
            self.get_logger().warn(f"FollowPath result error: {ex}")


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = GlobalPathFollowBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
