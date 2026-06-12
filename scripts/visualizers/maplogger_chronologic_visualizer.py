#!/usr/bin/env python3
"""
Manual Map Logger CHRONOLOGIC visualizer (Jupyter / ipywidgets).

Steps through a manual_map_logger CSV (lapNN.csv with columns
x, y, yaw_rad, left_wall_m, right_wall_m, time_sec) chunk by chunk so you can WATCH
the track being built over time and spot where the walls/centerline go wrong.

Reconstructs the left/right wall points from the pose + perpendicular wall distances:
    left  = (x,y) + left_normal  * left_wall_m
    right = (x,y) - left_normal  * right_wall_m   (left_normal = (-sin yaw, cos yaw))

Run in a Jupyter notebook (uses %matplotlib inline + ipywidgets sliders/play).
Deps: pandas, numpy, matplotlib, ipywidgets, IPython.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from ipywidgets import HBox, VBox, Output, Layout
from IPython.display import display
import ipywidgets as widgets

# %matplotlib inline   # uncomment in Jupyter

df = pd.read_csv("lap10_june7.csv")
df["left_wall_m"] = pd.to_numeric(df["left_wall_m"], errors="coerce")
df["right_wall_m"] = pd.to_numeric(df["right_wall_m"], errors="coerce")
df = df.dropna(subset=["x", "y", "yaw_rad"])

x = df["x"].values
y = df["y"].values
yaw = df["yaw_rad"].values
time_sec = df["time_sec"].values
time_normalized = time_sec - time_sec[0]
wL = df["left_wall_m"].values
wR = df["right_wall_m"].values

# left-facing normal
nx = -np.sin(yaw)
ny = np.cos(yaw)
left_x = np.where(np.isfinite(wL), x + nx * wL, np.nan)
left_y = np.where(np.isfinite(wL), y + ny * wL, np.nan)
right_x = np.where(np.isfinite(wR), x - nx * wR, np.nan)
right_y = np.where(np.isfinite(wR), y - ny * wR, np.nan)

valid = np.isfinite(left_x) & np.isfinite(left_y) & np.isfinite(right_x) & np.isfinite(right_y)
x_clean, y_clean = x[valid], y[valid]
time_clean = time_normalized[valid]
left_x_clean, left_y_clean = left_x[valid], left_y[valid]
right_x_clean, right_y_clean = right_x[valid], right_y[valid]
start_x, start_y = x_clean[0], y_clean[0]

out = Output()


def plot_chunk(chunk_num, chunk_size, show_full):
    out.clear_output(wait=True)
    with out:
        fig, ax = plt.subplots(figsize=(12, 10))
        start_idx = (chunk_num - 1) * chunk_size
        end_idx = min(start_idx + chunk_size, len(x_clean))

        if len(time_clean) > 0 and start_idx < len(time_clean):
            st = time_clean[start_idx]
            et = time_clean[end_idx - 1] if end_idx > start_idx else st
            time_range_str = f"Time: {st:.3f}s -> {et:.3f}s (Duration: {et-st:.3f}s)"
        else:
            time_range_str = "Time: N/A"

        if show_full:
            ax.scatter(x_clean, y_clean, s=5, c="black", alpha=0.1, label="Centerline (Full)")
            ax.scatter(left_x_clean, left_y_clean, s=5, c="blue", alpha=0.05, label="Left Wall (Full)")
            ax.scatter(right_x_clean, right_y_clean, s=5, c="red", alpha=0.05, label="Right Wall (Full)")
            ax.scatter(x_clean[start_idx:end_idx], y_clean[start_idx:end_idx], s=25, c="black", alpha=0.9)
            ax.scatter(left_x_clean[start_idx:end_idx], left_y_clean[start_idx:end_idx], s=25, c="blue", alpha=0.9)
            ax.scatter(right_x_clean[start_idx:end_idx], right_y_clean[start_idx:end_idx], s=25, c="red", alpha=0.9)
        else:
            if end_idx > 0:
                ax.scatter(x_clean[:end_idx], y_clean[:end_idx], s=8, c="gray", alpha=0.3, label="Elapsed Path")
                ax.scatter(left_x_clean[:end_idx], left_y_clean[:end_idx], s=8, c="lightblue", alpha=0.3)
                ax.scatter(right_x_clean[:end_idx], right_y_clean[:end_idx], s=8, c="lightcoral", alpha=0.3)
            if end_idx > start_idx:
                ax.scatter(x_clean[start_idx:end_idx], y_clean[start_idx:end_idx], s=25, c="black", alpha=1.0, label="Current Centerline")
                ax.scatter(left_x_clean[start_idx:end_idx], left_y_clean[start_idx:end_idx], s=25, c="blue", alpha=1.0, label="Current Left Wall")
                ax.scatter(right_x_clean[start_idx:end_idx], right_y_clean[start_idx:end_idx], s=25, c="red", alpha=1.0, label="Current Right Wall")

        ax.scatter(start_x, start_y, s=200, c="green", marker="*", edgecolors="darkgreen", linewidths=2, zorder=10, label="Start")
        ax.axis("equal")
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=8)
        total_chunks = (len(x_clean) + chunk_size - 1) // chunk_size
        ax.set_title(f"Track Wall View - Chunk {chunk_num}/{total_chunks}\nRows {start_idx}-{end_idx-1} of {len(x_clean)} | {time_range_str}", fontsize=10)
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)")
        plt.tight_layout(); plt.show()


chunk_size = 10
total_chunks = (len(x_clean) + chunk_size - 1) // chunk_size
chunk_slider = widgets.IntSlider(value=1, min=1, max=total_chunks, step=1, description='Chunk:', layout=Layout(width='400px'))
toggle_button = widgets.ToggleButton(value=False, description='Show Full Track', button_style='info', layout=Layout(width='150px'))
chunk_size_dropdown = widgets.Dropdown(options=[5, 10, 20, 50, 100], value=10, description='Chunk Size:', layout=Layout(width='180px'))
play_button = widgets.Play(interval=500, value=1, min=1, max=total_chunks, step=1, layout=Layout(width='150px'))
widgets.jslink((play_button, 'value'), (chunk_slider, 'value'))

current_show_full = False
current_chunk_size = 10


def update_plot(change=None):
    plot_chunk(chunk_slider.value, current_chunk_size, current_show_full)


def on_toggle_change(change):
    global current_show_full
    current_show_full = change['new']; update_plot()


def on_chunk_size_change(change):
    global current_chunk_size
    current_chunk_size = change['new']
    n = (len(x_clean) + current_chunk_size - 1) // current_chunk_size
    chunk_slider.max = n; play_button.max = n
    if chunk_slider.value > n:
        chunk_slider.value = n
    update_plot()


chunk_slider.observe(lambda c: update_plot(), names='value')
toggle_button.observe(on_toggle_change, names='value')
chunk_size_dropdown.observe(on_chunk_size_change, names='value')

controls = VBox([
    HBox([chunk_slider, play_button], layout=Layout(justify_content='center')),
    HBox([toggle_button, chunk_size_dropdown], layout=Layout(justify_content='center', margin='10px 0px')),
])

print("Loading track data...")
print(f"Total rows: {len(x_clean)} | Initial chunks: {total_chunks} | Duration: {time_normalized[-1]:.3f}s | Start: ({start_x:.3f}, {start_y:.3f})")
display(controls)
display(out)
plot_chunk(1, chunk_size, False)
