import math
import time
from typing import Optional

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import TransformStamped
from nav2_msgs.action import FollowPath
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import QoSProfile
from tf2_ros import Buffer, TransformException, TransformListener

from .path_utils import find_closest_index, find_lookahead_point
from .pp_math import Pose2D, pure_pursuit_steering_angle, quat_to_yaw


class PurePursuitFollowPathServer(Node):
    def __init__(self):
        super().__init__("pp_followpath_server")

        # Outputs
        self.declare_parameter("cmd_topic", "/ackermann_mux/input/nav_0")
        self.declare_parameter("control_rate_hz", 20.0)

        # Frames
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("transform_tolerance_s", 0.15)

        # Controller
        self.declare_parameter("lookahead_dist_m", 0.9)
        self.declare_parameter("constant_speed_mps", 0.5)

        # Vehicle (defaults are typical F1TENTH-ish; tune later)
        self.declare_parameter("wheelbase_m", 0.33)
        self.declare_parameter("max_steering_angle_rad", 0.34)

        # Goal condition
        self.declare_parameter("goal_xy_tolerance_m", 0.25)

        cmd_topic = str(self.get_parameter("cmd_topic").value)
        qos = QoSProfile(depth=10)
        self.cmd_pub = self.create_publisher(AckermannDriveStamped, cmd_topic, qos)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self._active_goal = None
        self._last_closest_index = 0

        self.action_server = ActionServer(
            self,
            FollowPath,
            "follow_path",
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
        )

        self.get_logger().info(
            f"PurePursuit FollowPath server ready on action '/follow_path', publishing to '{cmd_topic}'."
        )

    def goal_callback(self, goal_request: FollowPath.Goal) -> GoalResponse:
        if not goal_request.path.poses:
            self.get_logger().warn("Rejecting FollowPath goal: empty path.")
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle) -> CancelResponse:
        self.get_logger().info("FollowPath cancel requested.")
        return CancelResponse.ACCEPT

    def _lookup_base_in_frame(self, target_frame: str, base_frame: str) -> Optional[TransformStamped]:
        tol = float(self.get_parameter("transform_tolerance_s").value)
        try:
            return self.tf_buffer.lookup_transform(
                target_frame,
                base_frame,
                rclpy.time.Time(),
                timeout=Duration(seconds=tol),
            )
        except TransformException as ex:
            self.get_logger().warn(f"TF lookup failed {target_frame} <- {base_frame}: {ex}")
            return None

    def _publish_stop(self):
        msg = AckermannDriveStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.drive.speed = 0.0
        msg.drive.steering_angle = 0.0
        self.cmd_pub.publish(msg)

    def execute_callback(self, goal_handle):
        goal: FollowPath.Goal = goal_handle.request
        path = goal.path
        frame_id = path.header.frame_id or "map"
        base_frame = str(self.get_parameter("base_frame").value)

        lookahead = float(self.get_parameter("lookahead_dist_m").value)
        speed = float(self.get_parameter("constant_speed_mps").value)
        wheelbase = float(self.get_parameter("wheelbase_m").value)
        max_steer = float(self.get_parameter("max_steering_angle_rad").value)
        goal_tol = float(self.get_parameter("goal_xy_tolerance_m").value)
        rate_hz = float(self.get_parameter("control_rate_hz").value)
        dt = 1.0 / max(rate_hz, 1e-3)

        self.get_logger().info(
            f"Accepted FollowPath goal with {len(path.poses)} poses in frame '{frame_id}'."
        )

        self._last_closest_index = 0
        result = FollowPath.Result()

        while rclpy.ok():
            if goal_handle.is_cancel_requested:
                self._publish_stop()
                goal_handle.canceled()
                return result

            tf = self._lookup_base_in_frame(frame_id, base_frame)
            if tf is None:
                # Fail safe: stop but keep trying a bit.
                self._publish_stop()
                time.sleep(dt)
                continue

            bx = float(tf.transform.translation.x)
            by = float(tf.transform.translation.y)
            q = tf.transform.rotation
            byaw = quat_to_yaw(q.x, q.y, q.z, q.w)
            pose = Pose2D(x=bx, y=by, yaw=byaw)

            # Check goal reached (XY only)
            gx = float(path.poses[-1].pose.position.x)
            gy = float(path.poses[-1].pose.position.y)
            if math.hypot(gx - bx, gy - by) <= goal_tol:
                self._publish_stop()
                goal_handle.succeed()
                return result

            self._last_closest_index = find_closest_index(
                path.poses, bx, by, hint_index=self._last_closest_index
            )
            la = find_lookahead_point(path.poses, self._last_closest_index, lookahead)
            if la is None:
                self._publish_stop()
                time.sleep(dt)
                continue

            lax, lay, la_index = la
            steering = pure_pursuit_steering_angle(
                pose=pose,
                lookahead_point_x=lax,
                lookahead_point_y=lay,
                lookahead_dist=lookahead,
                wheelbase_m=wheelbase,
            )
            steering = max(-max_steer, min(max_steer, steering))

            cmd = AckermannDriveStamped()
            cmd.header.stamp = self.get_clock().now().to_msg()
            cmd.drive.speed = float(speed)
            cmd.drive.steering_angle = float(steering)
            self.cmd_pub.publish(cmd)

            feedback = FollowPath.Feedback()
            feedback.distance_to_goal = float(math.hypot(gx - bx, gy - by))
            feedback.speed = float(speed)
            # Some FollowPath defs include these fields; keep minimal + safe.
            goal_handle.publish_feedback(feedback)

            time.sleep(dt)

        # Shutdown path
        self._publish_stop()
        return result


def main():
    rclpy.init()
    node = PurePursuitFollowPathServer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

