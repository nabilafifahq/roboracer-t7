#!/usr/bin/env python3
"""Classic geometric pure pursuit on a TUM `traj_race_cl.csv` polyline."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, HistoryPolicy, ReliabilityPolicy
from tf2_ros import TransformException, TransformListener
from tf2_ros.buffer import Buffer


def _quat_to_yaw(q) -> float:
    x, y, z, w = q.x, q.y, q.z, q.w
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _load_tum_traj(csv_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Return (pts Nx2, cumlen N, vx N or None) from traj_race_cl or header-compatible CSV."""
    text = csv_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if not text:
        raise ValueError(f"Empty trajectory CSV: {csv_path}")

    first = text[0].lower()
    if "x_m" in first and "y_m" in first:
        rd = csv.DictReader(text)
        vx_key = None
        if rd.fieldnames:
            for cand in ("vx_mps", "vx"):
                if cand in rd.fieldnames:
                    vx_key = cand
                    break
        xs, ys, vxs = [], [], []
        for r in rd:
            try:
                xs.append(float(r["x_m"]))
                ys.append(float(r["y_m"]))
                if vx_key:
                    vxs.append(float(r[vx_key]))
            except (KeyError, ValueError):
                continue
        pts = np.column_stack([xs, ys]) if xs else np.zeros((0, 2))
        vx = np.array(vxs) if vx_key and len(vxs) == len(xs) else None
    else:
        # TUM numeric-only: s_m,x_m,y_m,psi_rad,kappa,vx_mps,ax_mps
        vx = []
        pts_list = []
        for line in text:
            parts = line.split(",")
            if len(parts) < 7:
                continue
            try:
                xs = float(parts[1].strip())
                ys = float(parts[2].strip())
                vv = float(parts[5].strip())
            except ValueError:
                continue
            pts_list.append([xs, ys])
            vx.append(vv)
        pts = np.array(pts_list, dtype=np.float64)
        vx = np.array(vx) if pts.shape[0] == len(vx) else None

    if pts.shape[0] < 3:
        raise ValueError(f"Need ≥3 trajectory points after parsing {csv_path}")

    dif = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(dif)])
    return pts, cum, vx


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


class RacelinePurePursuit(Node):
    def __init__(self) -> None:
        super().__init__("raceline_pure_pursuit")

        self.declare_parameter("trajectory_csv", "/race_ws/racelines/traj_race_cl.csv")
        self.declare_parameter("world_frame", "odom")
        self.declare_parameter("robot_frame", "base_link")
        self.declare_parameter("lookahead_m", 0.55)
        self.declare_parameter("wheelbase_m", 0.33)
        self.declare_parameter("target_speed_mps", 0.12)
        self.declare_parameter("use_traj_velocity", False)
        self.declare_parameter("traj_velocity_scale", 0.35)
        self.declare_parameter("max_steering_rad", 0.28)
        self.declare_parameter("min_speed_mps", 0.05)
        self.declare_parameter("control_hz", 20.0)
        self.declare_parameter("stop_within_m", 0.35)

        path = Path(str(self.get_parameter("trajectory_csv").value)).expanduser()
        self._world = str(self.get_parameter("world_frame").value)
        self._robot = str(self.get_parameter("robot_frame").value)
        self._ld = float(self.get_parameter("lookahead_m").value)
        self._L = float(self.get_parameter("wheelbase_m").value)
        self._v_nom = float(self.get_parameter("target_speed_mps").value)
        self._use_tv = bool(self.get_parameter("use_traj_velocity").value)
        self._tv_scale = float(self.get_parameter("traj_velocity_scale").value)
        self._delta_max = float(self.get_parameter("max_steering_rad").value)
        self._vmin = float(self.get_parameter("min_speed_mps").value)
        self._stop_rad = float(self.get_parameter("stop_within_m").value)
        hz = max(float(self.get_parameter("control_hz").value), 1.0)

        self._pts, self._cum, self._vx = _load_tum_traj(path)
        self._path_len = float(self._cum[-1])

        self.get_logger().info(
            f"Loaded trajectory {path} ({self._pts.shape[0]} points, length {self._path_len:.2f} m)"
        )

        # RELIABLE matches ackermann_mux on /drive (BEST_EFFORT is ignored with QoS warnings).
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self._pub = self.create_publisher(AckermannDriveStamped, "/drive", qos)

        self._tf_buf = Buffer(cache_time=rclpy.duration.Duration(seconds=30.0))
        self._tf_listener = TransformListener(self._tf_buf, self)

        self.create_timer(1.0 / hz, self._tick)

    def _projection_s(self, lx: float, ly: float) -> tuple[float, int]:
        """Closest point-on-polyline by segment projection; return (arclength s, segment start index used for vx lookup)."""
        p = np.array([lx, ly])
        pts = self._pts
        cum = self._cum
        best_d2 = float("inf")
        best_s = 0.0
        seg_i = 0
        for i in range(len(pts) - 1):
            p0 = pts[i]
            p1 = pts[i + 1]
            seg = p1 - p0
            L2 = float(np.dot(seg, seg))
            if L2 < 1e-12:
                continue
            tt = float(np.dot(p - p0, seg) / L2)
            tt = _clamp(tt, 0.0, 1.0)
            proj = p0 + tt * seg
            d2 = float(np.sum((p - proj) ** 2))
            if d2 < best_d2:
                best_d2 = d2
                best_s = cum[i] + tt * math.sqrt(L2)
                seg_i = i
        return best_s, seg_i

    def _point_at_s(self, s_target: float) -> tuple[float, float]:
        s_target = _clamp(s_target, 0.0, self._path_len)
        pts = self._pts
        cum = self._cum
        for i in range(len(pts) - 1):
            seg_len = cum[i + 1] - cum[i]
            if seg_len <= 1e-9:
                continue
            if cum[i + 1] >= s_target:
                rr = _clamp((s_target - cum[i]) / seg_len, 0.0, 1.0)
                q = pts[i] * (1.0 - rr) + pts[i + 1] * rr
                return float(q[0]), float(q[1])
        q = pts[-1]
        return float(q[0]), float(q[1])

    def _tick(self) -> None:
        try:
            t = self._tf_buf.lookup_transform(
                self._world,
                self._robot,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.15),
            )
        except TransformException as e:
            self.get_logger().warn(f"TF {self._world}->{self._robot}: {e}", throttle_duration_sec=2.0)
            return

        lx = float(t.transform.translation.x)
        ly = float(t.transform.translation.y)
        yaw = _quat_to_yaw(t.transform.rotation)

        s_here, idx_hint = self._projection_s(lx, ly)
        s_goal = min(s_here + self._ld, self._path_len)
        px, py = self._point_at_s(s_goal)

        dx = px - lx
        dy = py - ly

        lx_b = math.cos(-yaw) * dx - math.sin(-yaw) * dy
        ly_b = math.sin(-yaw) * dx + math.cos(-yaw) * dy

        dist = math.hypot(lx_b, ly_b)
        denom = max(dist, self._ld * 0.15)
        alpha = math.atan2(ly_b, lx_b)

        steer = math.atan2(2.0 * self._L * math.sin(alpha), denom)
        steer = float(np.clip(steer, -self._delta_max, self._delta_max))

        remain = max(0.0, self._path_len - s_here)
        v = self._v_nom
        if self._use_tv and self._vx is not None and idx_hint < len(self._vx):
            tv = abs(float(self._vx[idx_hint]))
            v = max(self._vmin, min(self._v_nom, self._tv_scale * tv))

        if remain < self._stop_rad:
            v = 0.0
            steer = 0.0

        msg = AckermannDriveStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._robot
        msg.drive.speed = v
        msg.drive.steering_angle = steer
        self._pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RacelinePurePursuit()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
