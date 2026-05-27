"""Convert geometry_msgs/Twist (Nav2 diff output) to ackermann_msgs/AckermannDriveStamped for F1Tenth mux."""

from __future__ import annotations

import math

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Twist
from rclpy.node import Node


class TwistToAckermann(Node):
    def __init__(self) -> None:
        super().__init__("twist_to_ackermann")

        self.declare_parameter("cmd_vel_topic", "/cmd_vel")
        self.declare_parameter("ackermann_topic", "/nav2_cmd_ackermann")
        self.declare_parameter("wheelbase_m", 0.325)
        self.declare_parameter("max_steering_angle_rad", 0.70)
        self.declare_parameter("min_linear_speed", 0.02)

        cmd_topic = str(self.get_parameter("cmd_vel_topic").value)
        ack_topic = str(self.get_parameter("ackermann_topic").value)
        self._L = float(self.get_parameter("wheelbase_m").value)
        self._max_steer = float(self.get_parameter("max_steering_angle_rad").value)
        self._min_v = float(self.get_parameter("min_linear_speed").value)

        self._pub = self.create_publisher(AckermannDriveStamped, ack_topic, 10)
        self.create_subscription(Twist, cmd_topic, self._cb, 10)
        self.get_logger().info(f"Remap {cmd_topic!r} -> {ack_topic!r} (bicycle model, wheelbase={self._L})")

    def _cb(self, msg: Twist) -> None:
        v = float(msg.linear.x)
        w = float(msg.angular.z)
        out = AckermannDriveStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = "base_link"

        if abs(v) < self._min_v:
            out.drive.speed = 0.0
            out.drive.steering_angle = 0.0
        else:
            delta = math.atan2(self._L * w, v)
            delta = max(-self._max_steer, min(self._max_steer, delta))
            out.drive.speed = v
            out.drive.steering_angle = delta

        self._pub.publish(out)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = TwistToAckermann()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
