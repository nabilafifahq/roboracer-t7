import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float


def normalize_angle_rad(a: float) -> float:
    # Normalize to (-pi, pi]
    while a <= -math.pi:
        a += 2.0 * math.pi
    while a > math.pi:
        a -= 2.0 * math.pi
    return a


def quat_to_yaw(x: float, y: float, z: float, w: float) -> float:
    # yaw (z-axis rotation) from quaternion
    # https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def pure_pursuit_steering_angle(
    *,
    pose: Pose2D,
    lookahead_point_x: float,
    lookahead_point_y: float,
    lookahead_dist: float,
    wheelbase_m: float,
) -> float:
    """
    Returns steering angle (rad) for Ackermann/bicycle model.

    Using curvature kappa = 2*sin(alpha)/L_d and delta = atan(L*kappa).
    """
    dx = lookahead_point_x - pose.x
    dy = lookahead_point_y - pose.y

    # Angle from vehicle to point in world/path frame
    target_bearing = math.atan2(dy, dx)
    alpha = normalize_angle_rad(target_bearing - pose.yaw)

    # Avoid divide-by-zero; if lookahead is tiny treat as straight.
    ld = max(lookahead_dist, 1e-6)
    kappa = 2.0 * math.sin(alpha) / ld
    return math.atan(wheelbase_m * kappa)

