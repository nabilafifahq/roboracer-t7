import numpy as np
import matplotlib.pyplot as plt
import yaml
import glob
from pathlib import Path

def plot_lidar_scan(yaml_file, document_index=0, label=None):
    """
    Parse YAML scan file and plot as polar coordinates
    Origin = vehicle position, rays = LiDAR measurements
    """
    
    # Load ALL YAML documents
    with open(yaml_file, 'r') as f:
        documents = list(yaml.safe_load_all(f))
    
    print(f"Found {len(documents)} scan documents in {yaml_file}")
    data = documents[document_index]
    
    # Extract scan data
    ranges = np.array(data['ranges'])
    angle_min = data['angle_min']
    angle_increment = data['angle_increment']
    range_min = data['range_min']
    range_max = data['range_max']
    
    # Create angle array for each range measurement
    num_ranges = len(ranges)
    angles = angle_min + np.arange(num_ranges) * angle_increment
    
    # Replace inf with range_max for visualization
    ranges_clean = np.array([range_max if np.isinf(r) else r for r in ranges])
    
    # Create polar plot
    fig, ax = plt.subplots(figsize=(12, 12), subplot_kw=dict(projection='polar'))
    
    # Plot the scan
    scatter = ax.scatter(angles, ranges_clean, c=ranges_clean, cmap='viridis', 
                        s=20, alpha=0.6, vmin=range_min, vmax=range_max)
    
    # Also plot as a line for continuity
    ax.plot(angles, ranges_clean, 'b-', alpha=0.3, linewidth=0.5)
    
    # Set radial limits
    ax.set_ylim(0, range_max)
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax, pad=0.1)
    cbar.set_label('Distance (meters)', rotation=270, labelpad=20)
    
    # Labels and title
    title_text = label if label else f"Scan {yaml_file}"
    ax.set_title(f'LiDAR Scan - Polar View ({title_text})\n(Vehicle at origin)', fontsize=14, pad=20)
    ax.set_xlabel('Angle (radians)', labelpad=30)
    ax.set_ylabel('Distance (meters)', labelpad=30)
    
    # Add grid
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save with predictable filename
    output_file = f'lidar_polar_{Path(yaml_file).stem}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✓ Saved: {output_file}")
    plt.close()  # Close to free memory

def plot_lidar_cartesian(yaml_file, document_index=0, label=None):    
    """
    Plot LiDAR scan in Cartesian coordinates (X-Y plane)
    """
    
    with open(yaml_file, 'r') as f:
        documents = list(yaml.safe_load_all(f))
    
    data = documents[document_index]
    
    ranges = np.array(data['ranges'])
    angle_min = data['angle_min']
    angle_increment = data['angle_increment']
    range_max = data['range_max']
    
    num_ranges = len(ranges)
    angles = angle_min + np.arange(num_ranges) * angle_increment
    
    # Convert to Cartesian coordinates
    ranges_clean = np.array([range_max if np.isinf(r) else r for r in ranges])
    x = ranges_clean * np.cos(angles)
    y = ranges_clean * np.sin(angles)
    
    # Create Cartesian plot
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # Plot scan points
    scatter = ax.scatter(x, y, c=ranges_clean, cmap='viridis', s=20, alpha=0.6)
    
    # Mark vehicle origin
    ax.plot(0, 0, 'r*', markersize=20, label='Vehicle', zorder=5)
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Distance (meters)', rotation=270, labelpad=20)
    
    # Set equal aspect ratio
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    
    # Labels
    ax.set_xlabel('X (meters)')
    ax.set_ylabel('Y (meters)')
    title_text = label if label else f"Scan {yaml_file}"
    ax.set_title(f"LiDAR Scan - Cartesian View ({title_text})\n(Vehicle at origin)", fontsize=14, pad=20)
    ax.legend()
    
    plt.tight_layout()
    
    # Save with predictable filename
    output_file = f'lidar_cartesian_{Path(yaml_file).stem}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✓ Saved: {output_file}")
    plt.close()  # Close to free memory

# ===== BATCH PROCESS ALL SCAN FILES =====
scan_files = sorted(glob.glob("scan*.yaml"))

if not scan_files:
    print("No scan*.yaml files found!")
else:
    print(f"Found {len(scan_files)} scan files:\n")
    
    for yaml_file in scan_files:
        # Extract file number from filename (e.g., "scan1.yaml" -> "1")
        file_stem = Path(yaml_file).stem  # "scan1"
        file_num = file_stem.replace("scan", "")  # "1"
        label = f"Location {file_num}"
        
        print(f"\n{'='*50}")
        print(f"Processing: {yaml_file} ({label})")
        print(f"{'='*50}")
        
        plot_lidar_scan(yaml_file, document_index=0, label=label)
        plot_lidar_cartesian(yaml_file, document_index=0, label=label)
    
    print(f"\n{'='*50}")
    print(f"✓ All {len(scan_files)} scans processed!")
    print(f"{'='*50}")