#!/usr/bin/env python3
"""
Multi-scan (YAML based) Cartesian + Polar LiDAR visualizer.

Reads files named like:  scan_loc3_0to0-5cm_0-3to1-2cm.yaml
(location 3, height 0-0.5 cm slice, range 0.3-1.2 cm) where each YAML holds one or
more sensor_msgs/LaserScan documents (dump with: ros2 topic echo /scan > scan.yaml).

For each file it saves a polar plot and a Cartesian (X-Y) plot of the scan, so you can
SEE what the LiDAR slice is actually returning (walls vs floor, gaps, range cut-off).

Usage: drop scan_loc*.yaml in the cwd, then `python3 scan_yaml_visualizer.py`.
Deps: numpy, matplotlib, pyyaml.
"""
import numpy as np
import matplotlib.pyplot as plt
import yaml
import glob
from pathlib import Path
import re


def parse_scan_filename(yaml_file):
    """Parse 'scan_loc3_0to0-5cm_0-3to1-2cm.yaml' -> (loc, hmin, hmax, rmin, rmax). Dashes = decimals."""
    stem = Path(yaml_file).stem
    loc_match = re.search(r'loc(\d+)', stem)
    location = loc_match.group(1) if loc_match else "unknown"

    height_match = re.search(r'(\d+(?:-\d+)?)to(\d+(?:-\d+)?)cm', stem)
    if height_match:
        min_height = height_match.group(1).replace('-', '.')
        max_height = height_match.group(2).replace('-', '.')
    else:
        min_height = max_height = "unknown"

    range_match = re.search(r'_(\d+(?:-\d+)?)to(\d+(?:-\d+)?)cm$', stem)
    if range_match:
        min_range = range_match.group(1).replace('-', '.')
        max_range = range_match.group(2).replace('-', '.')
    else:
        min_range = max_range = "unknown"

    return location, min_height, max_height, min_range, max_range


def plot_lidar_scan(yaml_file, document_index=0):
    """Polar view: origin = vehicle, rays = LiDAR returns."""
    location, min_height, max_height, min_range, max_range = parse_scan_filename(yaml_file)
    label = f"height {min_height}-{max_height} cm, range {min_range}-{max_range} cm at location {location}"

    with open(yaml_file, 'r') as f:
        documents = list(yaml.safe_load_all(f))
    print(f"Found {len(documents)} scan documents in {yaml_file}")
    data = documents[document_index]

    ranges = np.array(data['ranges'])
    angle_min = data['angle_min']
    angle_increment = data['angle_increment']
    range_min = data['range_min']
    range_max = data['range_max']

    angles = angle_min + np.arange(len(ranges)) * angle_increment
    ranges_clean = np.array([range_max if np.isinf(r) else r for r in ranges])

    fig, ax = plt.subplots(figsize=(12, 12), subplot_kw=dict(projection='polar'))
    scatter = ax.scatter(angles, ranges_clean, c=ranges_clean, cmap='viridis',
                         s=20, alpha=0.6, vmin=range_min, vmax=range_max)
    ax.plot(angles, ranges_clean, 'b-', alpha=0.3, linewidth=0.5)
    ax.set_ylim(0, range_max)
    cbar = plt.colorbar(scatter, ax=ax, pad=0.1)
    cbar.set_label('Distance (meters)', rotation=270, labelpad=20)
    ax.set_title(f'LiDAR Scan - Polar View\n({label})', fontsize=14, pad=20)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    output_file = f'h{min_height}-{max_height}_r{min_range}-{max_range}_loc{location}_lidar_distance.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()


def plot_lidar_cartesian(yaml_file, document_index=0):
    """Cartesian X-Y view of the scan."""
    location, min_height, max_height, min_range, max_range = parse_scan_filename(yaml_file)
    label = f"height {min_height}-{max_height} cm, range {min_range}-{max_range} cm at location {location}"

    with open(yaml_file, 'r') as f:
        documents = list(yaml.safe_load_all(f))
    data = documents[document_index]

    ranges = np.array(data['ranges'])
    angle_min = data['angle_min']
    angle_increment = data['angle_increment']
    range_max = data['range_max']

    angles = angle_min + np.arange(len(ranges)) * angle_increment
    ranges_clean = np.array([range_max if np.isinf(r) else r for r in ranges])
    x = ranges_clean * np.cos(angles)
    y = ranges_clean * np.sin(angles)

    fig, ax = plt.subplots(figsize=(12, 12))
    scatter = ax.scatter(x, y, c=ranges_clean, cmap='viridis', s=20, alpha=0.6)
    ax.plot(0, 0, 'r*', markersize=20, label='Vehicle', zorder=5)
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Distance (meters)', rotation=270, labelpad=20)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('X (meters)')
    ax.set_ylabel('Y (meters)')
    ax.set_title(f"LiDAR Scan - Cartesian View\n({label})", fontsize=14, pad=20)
    ax.legend()
    plt.tight_layout()

    output_file = f'h{min_height}-{max_height}_r{min_range}-{max_range}_loc{location}_lidar_cartesian.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()


if __name__ == '__main__':
    scan_files = sorted(glob.glob("scan_loc*.yaml"))
    if not scan_files:
        print("No scan_loc*.yaml files found!")
    else:
        print(f"Found {len(scan_files)} scan files:\n")
        for yaml_file in scan_files:
            loc, hmin, hmax, rmin, rmax = parse_scan_filename(yaml_file)
            print(f"\n{'='*70}\nProcessing: {yaml_file}\n  Location {loc}, height {hmin}-{hmax} cm, range {rmin}-{rmax} cm\n{'='*70}")
            plot_lidar_scan(yaml_file, 0)
            plot_lidar_cartesian(yaml_file, 0)
        print(f"\nAll {len(scan_files)} scans processed!")
