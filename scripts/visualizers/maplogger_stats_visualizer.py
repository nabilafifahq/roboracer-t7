#!/usr/bin/env python3
"""
Manual Map Logger STATS visualizer — odometry drift analysis.

Reads a manual_map_logger CSV (x, y, yaw_rad, time_sec) and reports how much the
odometry drifted over one lap, plus 4 diagnostic plots:
  1. position error growth vs time
  2. X and Y drift vs time
  3. cumulative (unwrapped) yaw  -> how many turns the car actually made
  4. trajectory colored by time (start green, end red)

Key number: "Position error" = distance between start and end of a loop. On a closed
track that SHOULD be ~0; a large value = odom drift. This is the chart on the
"What we have Done" slide (scattered spiral = drifted, clean loop = fixed).

Deps: pandas, numpy, matplotlib.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_csv("lap10_june7.csv")
x = df["x"].values
y = df["y"].values
yaw = df["yaw_rad"].values
time = df["time_sec"].values
time_norm = time - time[0]


def unwrap_yaw(yaw_rad):
    out = np.zeros_like(yaw_rad)
    out[0] = yaw_rad[0]
    for i in range(1, len(yaw_rad)):
        d = yaw_rad[i] - yaw_rad[i - 1]
        if d > np.pi:
            d -= 2 * np.pi
        elif d < -np.pi:
            d += 2 * np.pi
        out[i] = out[i - 1] + d
    return out


yaw_unwrapped = unwrap_yaw(yaw)
total_rotation = yaw_unwrapped[-1] - yaw_unwrapped[0]
total_rotations = total_rotation / (2 * np.pi)

start_x, start_y = x[0], y[0]
end_x, end_y = x[-1], y[-1]
position_error = np.hypot(end_x - start_x, end_y - start_y)
distances = np.hypot(np.diff(x), np.diff(y))
total_distance = np.sum(distances)

print("=" * 60)
print("ODOMETRY DRIFT ANALYSIS")
print("=" * 60)
print(f"Total distance traveled: {total_distance:.2f} m")
print(f"Total rotation: {total_rotation:.2f} rad ({total_rotations:.2f} turns)")
print(f"Start position: ({start_x:.3f}, {start_y:.3f})")
print(f"End position: ({end_x:.3f}, {end_y:.3f})")
print(f"Position error (start->end): {position_error:.3f} m")
print(f"Drift per meter: {(position_error/total_distance)*100:.1f}%")
print("=" * 60)

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

cumulative_error = np.hypot(x - start_x, y - start_y)
axes[0, 0].plot(time_norm, cumulative_error)
axes[0, 0].set(ylabel='Distance from start (m)', xlabel='Time (s)', title='Position Error Growth')
axes[0, 0].grid(True, alpha=0.3)

axes[0, 1].plot(time_norm, x - start_x, label='X drift')
axes[0, 1].plot(time_norm, y - start_y, label='Y drift')
axes[0, 1].set(ylabel='Drift from start (m)', xlabel='Time (s)', title='X and Y Drift Over Time')
axes[0, 1].legend(); axes[0, 1].grid(True, alpha=0.3)

axes[1, 0].plot(time_norm, yaw_unwrapped)
axes[1, 0].set(ylabel='Unwrapped Yaw (rad)', xlabel='Time (s)', title='Cumulative Rotation')
axes[1, 0].grid(True, alpha=0.3)

scatter = axes[1, 1].scatter(x, y, c=time_norm, cmap='viridis', s=10, alpha=0.7)
axes[1, 1].scatter(start_x, start_y, c='green', marker='*', s=200, label='Start')
axes[1, 1].scatter(end_x, end_y, c='red', marker='*', s=200, label='End')
axes[1, 1].set(xlabel='X (m)', ylabel='Y (m)', title='Trajectory (color = time)')
axes[1, 1].axis('equal'); axes[1, 1].grid(True, alpha=0.3); axes[1, 1].legend()
plt.colorbar(scatter, ax=axes[1, 1], label='Time (s)')

plt.tight_layout()
plt.show()
