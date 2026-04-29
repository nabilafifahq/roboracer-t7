import math
import time
from typing import Optional

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import TransformStamped
from mav_msgs.msg import Path as MavPath
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import QoSProfile
from tf2_ros import Buffer, TransformException, TransformListener

from .path_utils import find_closest_index, find_lookahead_point
from .pp_math import Pose2D, pure_pursuit_steering_angle, quat_to_yaw


class PurePursuitMavPathFollower(Node):
    def __init__(self):
        super().__init__("pp_mav_path_follower")

        # Inputs
        self.declare_parameter("path_topic", "/optimizer/path")

        # Outputs
        self.declare_parameter("cmd_topic", "/ackermann_mux/input/nav_0")
        self.declare_parameter("control_rate_hz", 20.0)

        # Frames
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("transform_tolerance_s", 0.15)

        # Controller
        self.declare_parameter("lookahead_dist_m", 0.9)
        self.declare_parameter("constant_speed_mps", 0.5)

        # Vehicle
        self.declare_parameter("wheelbase_m", 0.33)
        self.declare_parameter("max_steering_angle_rad", 0.34)

        # Goal condition
        self.declare_parameter("goal_xy_tolerance_m", 0.25)

        qos = QoSProfile(depth=10)

        cmd_topic = str(self.get_parameter("cmd_topic").value)
        self.cmd_pub = self.create_publisher(AckermannDriveStamped, cmd_topic, qos)

        path_topic = str(self.get_parameter("path_topic").value)
        self.path_sub = self.create_subscription(MavPath, path_topic, self._on_path, qos)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self._path: Optional[MavPath] = None
        self._last_closest_index = 0

        self.get_logger().info(f"Waiting for mav_msgs/Path on '{path_topic}', publishing to '{cmd_topic}'.")

    def _on_path(self, msg: MavPath):
        if not msg.poses:
            self.get_logger().warn("Received empty mav_msgs/Path; ignoring.")
            return
        self._path = msg
        self._last_closest_index = 0
        frame = msg.header.frame_id or "map"
        self.get_logger().info(f"Received path with {len(msg.poses)} poses in frame '{frame}'.")

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

    def spin_forever(self):
        rate_hz = float(self.get_parameter("control_rate_hz").value)
        dt = 1.0 / max(rate_hz, 1e-3)

        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.0)

            if self._path is None:
                time.sleep(dt)
                continue

            path = self._path
            frame_id = path.header.frame_id or "map"
            base_frame = str(self.get_parameter("base_frame").value)

            lookahead = float(self.get_parameter("lookahead_dist_m").value)
            speed = float(self.get_parameter("constant_speed_mps").value)
            wheelbase = float(self.get_parameter("wheelbase_m").value)
            max_steer = float(self.get_parameter("max_steering_angle_rad").value)
            goal_tol = float(self.get_parameter("goal_xy_tolerance_m").value)

            tf = self._lookup_base_in_frame(frame_id, base_frame)
            if tf is None:
                self._publish_stop()
                time.sleep(dt)
                continue

            bx = float(tf.transform.translation.x)
            by = float(tf.transform.translation.y)
            q = tf.transform.rotation
            byaw = quat_to_yaw(q.x, q.y, q.z, q.w)
            pose = Pose2D(x=bx, y=by, yaw=byaw)

            gx = float(path.poses[-1].pose.position.x)
            gy = float(path.poses[-1].pose.position.y)
            if math.hypot(gx - bx, gy - by) <= goal_tol:
                self._publish_stop()
                time.sleep(dt)
                continue

            self._last_closest_index = find_closest_index(
                path.poses, bx, by, hint_index=self._last_closest_index
            )
            la = find_lookahead_point(path.poses, self._last_closest_index, lookahead)
            if la is None:
                self._publish_stop()
                time.sleep(dt)
                continue

            lax, lay, _la_index = la
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

            time.sleep(dt)


def main():
    rclpy.init()
    node = PurePursuitMavPathFollower()
    try:
        node.spin_forever()
    finally:
        node.destroy_node()
        rclpy.shutdown()

