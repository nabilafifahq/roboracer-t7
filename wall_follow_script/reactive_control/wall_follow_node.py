import math
import numpy as np
import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan

# Lab constants
THETA_DEG = 60
LOOKAHEAD = 0.6  # m
DESIRED_DISTANCE_FROM_WALL = 0.5  # m
INTEGRAL_WINDOW_SIZE = 10
KP = 1.2
KD = 0.0
KI = 0.0

def windowed_median_distance_with_index(theta, ranges, angle_min, angle_inc, window_n, range_min=None, range_max=None):
    n = len(ranges)
    i_center = int(round((theta - angle_min) / angle_inc))
    i_center = max(0, min(n - 1, i_center))

    lo = max(0, i_center - window_n)
    hi = min(n, i_center + window_n + 1)

    window = ranges[lo:hi]

    finite_vals = []
    for v in window:
        if math.isinf(v) or math.isnan(v):
            continue
        if range_min is not None and v <= range_min:
            continue
        if range_max is not None and v >= range_max:
            continue
        finite_vals.append(v)

    if not finite_vals:
        return i_center, float("inf")

    # robust central tendency vs outliers
    return i_center, float(np.median(np.array(finite_vals, dtype=float)))

def angle_to_index(theta, angle_min, angle_inc, n):
    i = int(round((theta - angle_min) / angle_inc))
    return max(0, min(n - 1, i))

def angle_to_distance_with_index(theta, ranges, angle_min, angle_inc):
    n = len(ranges)
    i = angle_to_index(theta, angle_min, angle_inc, n)
    return i, ranges[i]

def is_valid_lidar_scan(value: float, range_min: float, range_max: float) -> bool:
    return (
        not math.isinf(value)
        and not math.isnan(value)
        and range_min < value < range_max
    )


class WallFollowNode(Node):
    def __init__(self):
        super().__init__("wall_follow_node")

        qos_scan = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.create_subscription(LaserScan, "/scan", self.lidar_callback, qos_scan)

        qos_drive = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.drive_pub = self.create_publisher(AckermannDriveStamped, "drive", qos_drive)

        self.last_time_ns: int | None = None
        self.last_steering = 0.0
        self.last_errors_window = np.array([])

    def lidar_callback(self, scan: LaserScan):
        throttle = 0.3  # m/s

        lidar_range_array: list[float] = scan.ranges  # type: ignore
        angle_min = scan.angle_min
        angle_increment = scan.angle_increment

        theta = np.radians(THETA_DEG)
        theta_b = np.radians(-70)
        theta_a = theta_b + np.radians(THETA_DEG)

        i_a, a = windowed_median_distance_with_index(theta_a, scan.ranges, scan.angle_min, scan.angle_increment, 4,range_min=scan.range_min, range_max=scan.range_max)
        i_b, b = windowed_median_distance_with_index(theta_b, scan.ranges, scan.angle_min, scan.angle_increment,4,range_min=scan.range_min, range_max=scan.range_max)
        self.get_logger().info(f"i_a={i_a} theta_a={theta_a:+.3f} rad ({np.degrees(theta_a):+.1f} deg) a={a} | "f"i_b={i_b} theta_b={theta_b:+.3f} rad({np.degrees(theta_b):+.1f} deg) b={b}")

        if not is_valid_lidar_scan(a, scan.range_min, scan.range_max) or not is_valid_lidar_scan(b, scan.range_min, scan.range_max):
            self.get_logger().warn(f"Invalid lidar: a={a:.3f}, b={b:.3f}, range=[{scan.range_min:.3f},{scan.range_max:.3f}], "f"angle_min={scan.angle_min:.3f}, angle_inc={scan.angle_increment:.6f}, n={len(scan.ranges)}")
            # Fallback: slow down and straighten a bit instead of repeating a saturated steering
            self.send_control_command(0.3, 0.0)
            self.last_steering = 0.0
            self.last_time_ns = self.get_clock().now().nanoseconds
            return

        alpha = math.atan((a * math.cos(theta) - b) / (a * math.sin(theta)))
        d_t = b * math.cos(alpha)
        d_tp1 = d_t + LOOKAHEAD * math.sin(alpha)

        error = DESIRED_DISTANCE_FROM_WALL - d_tp1
		
        self.get_logger().info(f"alpha={alpha:+.3f} d_tp1={d_tp1:.3f} error={error:+.3f} steer_raw={KP*error:+.3f}")

        # PID control
        now_ns = self.get_clock().now().nanoseconds
        if self.last_time_ns is None or len(self.last_errors_window) == 0:
            error_diff = 0.0
            error_integral = 0.0
        else:
            dt_ns = now_ns - self.last_time_ns
            dt = dt_ns * 1e-9  # seconds
            if dt <= 0.0:
                error_diff = 0.0
                error_integral = 0.0
            else:
                de = error - float(self.last_errors_window[-1])
                error_diff = de / dt
                error_integral = float(np.sum(self.last_errors_window)) * dt

        steering = error * KP + error_integral * KI + error_diff * KD
        MAX_STEER = 0.15  # rad (~20 deg)
        steering = max(min(steering, MAX_STEER), -MAX_STEER)
        # steering = -steering

        # Update state
        self.last_steering = steering
        self.last_time_ns = now_ns

        if len(self.last_errors_window) >= INTEGRAL_WINDOW_SIZE:
            self.last_errors_window[:-1] = self.last_errors_window[1:]
            self.last_errors_window[-1] = error
        else:
            self.last_errors_window = np.append(self.last_errors_window, error)

        self.send_control_command(throttle, steering)

    def send_control_command(self, throttle: float, steering: float):
        msg = AckermannDriveStamped()
        msg.header.frame_id = "base_link"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.drive.speed = throttle
        msg.drive.steering_angle = steering
        self.drive_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = WallFollowNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()