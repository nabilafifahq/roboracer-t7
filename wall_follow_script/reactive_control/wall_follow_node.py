import math
import numpy as np
import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

# Lab constants
THETA_DEG = 60
LOOKAHEAD = 0.6  # m
DESIRED_DISTANCE_FROM_WALL = 0.5  # m
INTEGRAL_WINDOW_SIZE = 10
KP = 1.2
KD = 0.0
KI = 0.0


def angle_to_distance(theta_rad: float, lidar_array: list[float], angle_min: float, angle_increment: float):
    if angle_increment == 0.0:
        return float("nan")

    idx = (theta_rad - angle_min) / angle_increment
    index = int(round(idx))  # round is usually better than truncating toward 0

    if index < 0:
        index = 0
    elif index >= len(lidar_array):
        index = len(lidar_array) - 1

    return lidar_array[index]


def is_valid_lidar_scan(scan: float, range_min: float, range_max: float) -> bool:
    return (
        not math.isinf(scan)
        and not math.isnan(scan)
        and range_min < scan < range_max
    )


class WallFollowNode(Node):
    def __init__(self):
        super().__init__("wall_follow_node")

        # Honor the speed/steering/safety params passed by bringup.launch.py.
        # (Previously these were ignored and throttle was hardcoded at 2.2 m/s.)
        self.target_speed_mps = self.declare_parameter("target_speed_mps", 0.10).value
        self.min_speed_mps = self.declare_parameter("min_speed_mps", 0.0).value
        self.max_speed_mps = self.declare_parameter("max_speed_mps", 0.12).value
        self.max_steering_angle_rad = self.declare_parameter("max_steering_angle_rad", 0.70).value
        self.lidar_drop_timeout_s = self.declare_parameter("lidar_drop_timeout_s", 2.0).value
        # Declared for forward-compat with bringup params (not yet used by this controller;
        # RC override is handled by ackermann_mux priority, not here).
        for _name, _default in (
            ("manual_override_latch", True),
            ("front_obstacle_distance_m", 1.0),
            ("side_obstacle_distance_m", 0.9),
            ("centering_gain", 0.8),
            ("steering_smoothing_alpha", 0.25),
            ("deadman_button_index", 1),
        ):
            self.declare_parameter(_name, _default)

        # LiDAR-drop safety latch: if no valid scan for lidar_drop_timeout_s, stop and stay stopped.
        self._last_valid_scan_ns = None
        self._lidar_latched_stop = False

        scan_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(LaserScan, "/scan", self.lidar_callback, scan_qos)

        drive_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.drive_pub = self.create_publisher(AckermannDriveStamped, "/drive", drive_qos)

        self.last_time = None
        self.last_steering = 0.0
        self.last_errors_window = np.array([])

    def lidar_callback(self, scan: LaserScan):
        steering = 0.0  # rad
        throttle = self._clamp_speed(self.target_speed_mps)  # m/s (param, not hardcoded)
        now_ns = self.get_clock().now().nanoseconds

        # Once latched on LiDAR loss, stay stopped until relaunch (safety requirement).
        if self._lidar_latched_stop:
            self.send_control_command(0.0, 0.0)
            return

        lidar_range_array: list[float] = scan.ranges  # type: ignore
        angle_min = scan.angle_min
        angle_increment = scan.angle_increment

        theta = np.radians(THETA_DEG)
        theta_b = -np.pi / 2.0
        theta_a = theta_b + theta
        a = angle_to_distance(theta_a, lidar_range_array, angle_min, angle_increment)
        b = angle_to_distance(theta_b, lidar_range_array, angle_min, angle_increment)

        if not is_valid_lidar_scan(a, scan.range_min, scan.range_max) or not is_valid_lidar_scan(
            b, scan.range_min, scan.range_max
        ):
            # Tolerate brief invalid scans (repeat last steering at the safe param speed),
            # but if invalid for longer than lidar_drop_timeout_s, latch a full stop.
            if self._last_valid_scan_ns is not None and (
                (now_ns - self._last_valid_scan_ns) / 1e9 > self.lidar_drop_timeout_s
            ):
                self._lidar_latched_stop = True
                self.get_logger().error(
                    f"LiDAR invalid > {self.lidar_drop_timeout_s}s -- latching STOP (relaunch to resume)"
                )
                self.send_control_command(0.0, 0.0)
                return
            self.get_logger().warn("Invalid lidar scan, repeating last command")
            self.send_control_command(throttle, self.last_steering)
            return

        self._last_valid_scan_ns = now_ns

        alpha = math.atan((a * math.cos(theta) - b) / (a * math.sin(theta)))
        D_t = b * math.cos(alpha)
        D_tp1 = D_t + LOOKAHEAD * math.sin(alpha)

        error = DESIRED_DISTANCE_FROM_WALL - D_tp1

        # PID control
        if self.last_time is None:
            error_diff = 0.0
            error_integral = 0.0
        else:
            dt = self.get_clock().now().nanoseconds - self.last_time
            de = error - self.last_errors_window[-1]
            error_diff = de / dt
            error_integral = np.sum(self.last_errors_window) * dt

        steering = error * KP + error_integral * KI + error_diff * KD
        # Clamp steering to the configured limit.
        steering = max(-self.max_steering_angle_rad, min(self.max_steering_angle_rad, steering))

        # Updating variables
        self.last_steering = steering
        self.last_time = self.get_clock().now().nanoseconds
        if len(self.last_errors_window) >= INTEGRAL_WINDOW_SIZE:
            self.last_errors_window[:-1] = self.last_errors_window[1:]
            self.last_errors_window[-1] = error
        else:
            self.last_errors_window = np.append(self.last_errors_window, error)

        self.send_control_command(throttle, steering)

    def _clamp_speed(self, speed: float) -> float:
        return max(self.min_speed_mps, min(self.max_speed_mps, speed))

    def send_control_command(self, throttle: float, steering: float):
        ackermann_msg = AckermannDriveStamped()
        ackermann_msg.header.frame_id = "base_link"
        ackermann_msg.header.stamp = self.get_clock().now().to_msg()

        ackermann_msg.drive.speed = throttle
        ackermann_msg.drive.steering_angle = steering

        self.drive_pub.publish(ackermann_msg)


def main(args=None):
    rclpy.init(args=args)
    node = WallFollowNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
