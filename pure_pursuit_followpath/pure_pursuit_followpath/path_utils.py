import math
from typing import List, Optional, Tuple

from geometry_msgs.msg import PoseStamped


def _dist2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def find_closest_index(points: List[PoseStamped], x: float, y: float, hint_index: int = 0) -> int:
    """
    Return index of closest point. Uses hint_index as a starting point
    and searches the full list (safe but O(N)).
    """
    if not points:
        return 0
    best_i = 0
    best_d2 = float("inf")

    # Search full list; for typical F1TENTH paths this is fine.
    # If you later push to very large paths, we can window this.
    for i, p in enumerate(points):
        px = float(p.pose.position.x)
        py = float(p.pose.position.y)
        d2 = _dist2((px, py), (x, y))
        if d2 < best_d2:
            best_d2 = d2
            best_i = i
    return best_i


def find_lookahead_point(
    points: List[PoseStamped],
    start_index: int,
    lookahead_dist: float,
) -> Optional[Tuple[float, float, int]]:
    """
    Walk forward along points from start_index until cumulative arc length
    reaches lookahead_dist. Returns (x, y, index).
    """
    if not points:
        return None

    i = max(0, min(start_index, len(points) - 1))
    acc = 0.0
    prev_x = float(points[i].pose.position.x)
    prev_y = float(points[i].pose.position.y)

    if lookahead_dist <= 0.0:
        return (prev_x, prev_y, i)

    for j in range(i + 1, len(points)):
        x = float(points[j].pose.position.x)
        y = float(points[j].pose.position.y)
        seg = math.hypot(x - prev_x, y - prev_y)
        acc += seg
        prev_x, prev_y = x, y
        if acc >= lookahead_dist:
            return (x, y, j)
    # If we run out, return last point
    last = points[-1].pose.position
    return (float(last.x), float(last.y), len(points) - 1)

