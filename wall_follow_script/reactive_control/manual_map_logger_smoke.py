#!/usr/bin/env python3
"""Publish fake /scan + odom->base_link TF for offline testing of manual_map_logger."""

from __future__ import annotations

import math

import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from tf2_ros import TransformBroadcaster


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = rclpy.create_node("manual_map_logger_smoke")
    tf_br = TransformBroadcaster(node)
    scan_qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    )
    scan_pub = node.create_publisher(LaserScan, "/scan", scan_qos)

    t0 = node.get_clock().now().nanoseconds * 1e-9

    def tick() -> None:
        t = node.get_clock().now().nanoseconds * 1e-9 - t0
        ts = TransformStamped()
        ts.header.stamp = node.get_clock().now().to_msg()
        ts.header.frame_id = "odom"
        ts.child_frame_id = "base_link"
        ts.transform.translation.x = 0.05 * t
        ts.transform.translation.y = 0.3 * math.sin(0.5 * t)
        ts.transform.translation.z = 0.0
        yaw = 0.2 * t
        ts.transform.rotation.x = 0.0
        ts.transform.rotation.y = 0.0
        ts.transform.rotation.z = math.sin(yaw * 0.5)
        ts.transform.rotation.w = math.cos(yaw * 0.5)
        tf_br.sendTransform(ts)

        angle_min = -math.pi
        angle_max = math.pi
        n = 360
        inc = (angle_max - angle_min) / max(n - 1, 1)
        scan = LaserScan()
        scan.header.stamp = node.get_clock().now().to_msg()
        scan.header.frame_id = "base_link"
        scan.angle_min = angle_min
        scan.angle_max = angle_max
        scan.angle_increment = inc
        scan.time_increment = 0.0
        scan.scan_time = 0.05
        scan.range_min = 0.05
        scan.range_max = 30.0
        ranges: list[float] = []
        for i in range(n):
            ang = angle_min + i * inc
            if 1.10 <= ang <= 1.75:
                ranges.append(1.2 + 0.1 * math.sin(t))
            elif -1.75 <= ang <= -1.10:
                ranges.append(2.1 + 0.1 * math.cos(t))
            else:
                ranges.append(8.0)
        scan.ranges = ranges
        scan_pub.publish(scan)

    node.create_timer(0.05, tick)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
