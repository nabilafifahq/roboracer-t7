import math

import numpy as np
import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy
from rclpy.qos import HistoryPolicy
from rclpy.qos import QoSProfile
from rclpy.qos import ReliabilityPolicy
from sensor_msgs.msg import Joy
from sensor_msgs.msg import LaserScan

# Lab constants
THETA_DEG = 60
LOOKAHEAD = 0.6  # m
DESIRED_DISTANCE_FROM_WALL = 0.5  # m
INTEGRAL_WINDOW_SIZE = 10
KP = 1.2
KD = 0.0
KI = 0.0


def angle_to_distance(theta_rad: float, lidar_array: list[float], angle_min: float, angle_increment: float):
    index = int((theta_rad - angle_min) / angle_increment)
    distance = lidar_array[index]

    return distance


def is_valid_lidar_scan(scan: float) -> bool:
    return not math.isinf(scan) and not math.isnan(scan)


class WallFollowNode(Node):
    def __init__(self):
        super().__init__("wall_follow_node")

        # Indoor-safe defaults; can be overridden from launch/CLI params.
        self.declare_parameter("target_speed_mps", 0.25)
        self.declare_parameter("min_speed_mps", 0.0)
        self.declare_parameter("max_speed_mps", 0.35)
        self.declare_parameter("max_steering_angle_rad", 0.22)
        self.declare_parameter("manual_override_latch", True)
        self.declare_parameter("front_obstacle_distance_m", 1.0)
        self.declare_parameter("side_obstacle_distance_m", 0.9)
        self.declare_parameter("centering_gain", 0.8)
        self.declare_parameter("steering_smoothing_alpha", 0.25)
        self.declare_parameter("deadman_button_index", 4)
        self.declare_parameter("lidar_drop_timeout_s", 2.0)

        self.target_speed_mps = 0.25
        self.min_speed_mps = 0.0
        self.max_speed_mps = 0.35
        self.max_steering_angle_rad = 0.22
        self.manual_override_latch = True
        self.front_obstacle_distance_m = 1.0
        self.side_obstacle_distance_m = 0.9
        self.centering_gain = 0.8
        self.steering_smoothing_alpha = 0.25
        self.deadman_button_index = 4
        self.lidar_drop_timeout_s = 2.0
        self.manual_latched = False
        self.lidar_fault_latched = False
        self.lidar_invalid_since_ns = None
        self.deadman_prev_pressed = None
        self._refresh_runtime_params()

        # Input from depthimage_to_laserscan (or real lidar later)
        scan_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(LaserScan, "/scan", self.lidar_callback, scan_qos)
        self.create_subscription(Joy, "/joy", self.joy_callback, 10)

        # Output into base stack autonomy input.
        self.nav_pub = self.create_publisher(AckermannDriveStamped, "/drive", 10)

        self.last_time = None
        self.last_steering = 0.0
        self.last_errors_window = np.array([])

    def lidar_callback(self, scan: LaserScan):
        # Allow live tuning via "ros2 param set" while node is running.
        self._refresh_runtime_params()

        if self.manual_latched or self.lidar_fault_latched:
            self.send_control_command(0.0, 0.0)
            return

        steering = 0.0  # rad
        throttle = self.target_speed_mps  # m/s

        lidar_range_array: list[float] = scan.ranges  # type: ignore
        angle_min = scan.angle_min
        angle_increment = scan.angle_increment

        front_min = self._window_min_distance(lidar_range_array, angle_min, angle_increment, -0.30, 0.30)
        right_min = self._window_min_distance(lidar_range_array, angle_min, angle_increment, -1.75, -1.10)
        left_min = self._window_min_distance(lidar_range_array, angle_min, angle_increment, 1.10, 1.75)

        # Lidar health latch: if all key windows are invalid for too long, latch stop until relaunch.
        no_valid_scan = math.isinf(front_min) and math.isinf(left_min) and math.isinf(right_min)
        now_ns = self.get_clock().now().nanoseconds
        if no_valid_scan:
            if self.lidar_invalid_since_ns is None:
                self.lidar_invalid_since_ns = now_ns
            elapsed_s = (now_ns - self.lidar_invalid_since_ns) / 1e9
            if elapsed_s >= self.lidar_drop_timeout_s:
                self.lidar_fault_latched = True
                self.get_logger().error("LiDAR invalid > timeout. Latching stop until relaunch.")
                self.send_control_command(0.0, 0.0)
                return
            self.send_control_command(0.0, 0.0)
            return
        self.lidar_invalid_since_ns = None

        # Explicit hallway safety rules (front obstacle = slow down and turn away).
        if front_min < self.front_obstacle_distance_m and right_min < self.side_obstacle_distance_m:
            self.send_control_command(0.10, self.max_steering_angle_rad)
            return
        if front_min < self.front_obstacle_distance_m and left_min < self.side_obstacle_distance_m:
            self.send_control_command(0.10, -self.max_steering_angle_rad)
            return
        if front_min < self.front_obstacle_distance_m:
            # Choose the side with more free space.
            turn_left = left_min >= right_min
            steering = self.max_steering_angle_rad if turn_left else -self.max_steering_angle_rad
            self.send_control_command(0.12, steering)
            return

        # Corridor centering: walls on both sides, no front obstacle => center smoothly.
        if left_min < self.side_obstacle_distance_m and right_min < self.side_obstacle_distance_m:
            center_error = left_min - right_min
            steering_cmd = self.centering_gain * center_error
            steering = (1.0 - self.steering_smoothing_alpha) * self.last_steering + self.steering_smoothing_alpha * steering_cmd
            self.last_steering = steering
            self.send_control_command(self.target_speed_mps, steering)
            return

        theta = np.radians(THETA_DEG)
        theta_b = -np.pi / 2.0
        theta_a = theta_b + theta
        a = angle_to_distance(theta_a, lidar_range_array, angle_min, angle_increment)
        b = angle_to_distance(theta_b, lidar_range_array, angle_min, angle_increment)

        if not is_valid_lidar_scan(a) or not is_valid_lidar_scan(b):
            # Fail safe: stop on invalid scan rather than continuing blind.
            self.get_logger().warn("Invalid lidar scan, sending stop command")
            self.send_control_command(0.0, 0.0)
            return

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
        steering = (1.0 - self.steering_smoothing_alpha) * self.last_steering + self.steering_smoothing_alpha * steering

        # Updating variables
        self.last_steering = steering
        self.last_time = self.get_clock().now().nanoseconds
        if len(self.last_errors_window) >= INTEGRAL_WINDOW_SIZE:
            self.last_errors_window[:-1] = self.last_errors_window[1:]
            self.last_errors_window[-1] = error
        else:
            self.last_errors_window = np.append(self.last_errors_window, error)

        self.send_control_command(throttle, steering)

    def send_control_command(self, throttle: float, steering: float):
        ackermann_msg = AckermannDriveStamped()
        ackermann_msg.header.frame_id = "base_link"
        ackermann_msg.header.stamp = self.get_clock().now().to_msg()

        clamped_speed = max(self.min_speed_mps, min(throttle, self.max_speed_mps))
        clamped_steering = max(-self.max_steering_angle_rad, min(steering, self.max_steering_angle_rad))

        ackermann_msg.drive.speed = clamped_speed
        ackermann_msg.drive.steering_angle = clamped_steering

        self.nav_pub.publish(ackermann_msg)

    def _refresh_runtime_params(self):
        self.target_speed_mps = float(self.get_parameter("target_speed_mps").value)
        self.min_speed_mps = float(self.get_parameter("min_speed_mps").value)
        self.max_speed_mps = float(self.get_parameter("max_speed_mps").value)
        self.max_steering_angle_rad = abs(float(self.get_parameter("max_steering_angle_rad").value))
        self.manual_override_latch = bool(self.get_parameter("manual_override_latch").value)
        self.front_obstacle_distance_m = float(self.get_parameter("front_obstacle_distance_m").value)
        self.side_obstacle_distance_m = float(self.get_parameter("side_obstacle_distance_m").value)
        self.centering_gain = float(self.get_parameter("centering_gain").value)
        self.steering_smoothing_alpha = float(self.get_parameter("steering_smoothing_alpha").value)
        self.deadman_button_index = int(self.get_parameter("deadman_button_index").value)
        self.lidar_drop_timeout_s = float(self.get_parameter("lidar_drop_timeout_s").value)

    def joy_callback(self, joy_msg: Joy):
        if not self.manual_override_latch or self.manual_latched:
            return
        if self.deadman_button_index < 0 or self.deadman_button_index >= len(joy_msg.buttons):
            return
        pressed = joy_msg.buttons[self.deadman_button_index] == 1
        if self.deadman_prev_pressed is None:
            self.deadman_prev_pressed = pressed
            return
        if pressed and not self.deadman_prev_pressed:
            self.manual_latched = True
            self.get_logger().warn("LB pressed: autonomy latched off until relaunch.")
            self.send_control_command(0.0, 0.0)
        self.deadman_prev_pressed = pressed

    def _window_min_distance(
        self,
        ranges: list[float],
        angle_min: float,
        angle_increment: float,
        start_angle: float,
        end_angle: float,
    ) -> float:
        if angle_increment <= 0.0 or not ranges:
            return float("inf")
        start_idx = max(0, int((start_angle - angle_min) / angle_increment))
        end_idx = min(len(ranges) - 1, int((end_angle - angle_min) / angle_increment))
        if end_idx < start_idx:
            start_idx, end_idx = end_idx, start_idx
        window = [v for v in ranges[start_idx : end_idx + 1] if is_valid_lidar_scan(v)]
        if not window:
            return float("inf")
        return min(window)


def main(args=None):
    rclpy.init(args=args)
    node = WallFollowNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
