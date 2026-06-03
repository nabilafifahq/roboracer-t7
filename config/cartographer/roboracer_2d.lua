-- RoboRacer T7: 2D Cartographer SLAM with external EKF odometry.
--
-- Frame ownership (REP-105):
--   EKF (robot_localization)  publishes  odom -> base_link   (use_odometry source)
--   Cartographer              publishes  map  -> odom         (global drift correction)
--
-- This is why published_frame = "odom" and provide_odom_frame = false:
-- Cartographer emits map -> published_frame. If published_frame were "base_link"
-- it would fight the EKF for the parent of base_link and break the TF tree.
-- With published_frame = "odom" the chain is  map -> odom (carto) -> base_link (EKF).
--
-- This file is SELF-CONTAINED: it includes Cartographer's INSTALLED base configs
-- (map_builder.lua / trajectory_builder.lua resolve to the cartographer share dir)
-- and then overrides individual fields. Do NOT add local map_builder.lua or
-- trajectory_builder.lua next to this file -- they would shadow the full defaults
-- (MAP_BUILDER.pose_graph, TRAJECTORY_BUILDER_2D.submaps, ceres_scan_matcher, ...)
-- and the cartographer_node would fail to start.

include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "base_link",   -- use_imu_data = false, so no IMU extrinsics needed
  published_frame = "odom",       -- EKF owns odom->base_link; Cartographer adds map->odom
  odom_frame = "odom",            -- only used if provide_odom_frame = true (it is not)
  provide_odom_frame = false,     -- EKF provides odometry, not Cartographer
  publish_frame_projected_to_2d = true,
  use_pose_extrapolator = true,
  use_odometry = true,            -- consume /odometry/filtered (EKF), remapped in launch
  use_nav_sat = false,
  use_landmarks = false,
  num_laser_scans = 1,            -- single /scan from pointcloud_to_laserscan
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,
  lookup_transform_timeout_sec = 0.3,
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,
  trajectory_publish_period_sec = 30e-3,
  rangefinder_sampling_ratio = 1.0,
  odometry_sampling_ratio = 1.0,
  fixed_frame_pose_sampling_ratio = 1.0,
  imu_sampling_ratio = 1.0,
  landmarks_sampling_ratio = 1.0,
}

-- ---- Map builder (Raspberry Pi CPU budget) -------------------------------
MAP_BUILDER.use_trajectory_builder_2d = true
MAP_BUILDER.num_background_threads = 2

-- ---- 2D local SLAM, tuned for indoor hallway + Livox /scan slice ----------
TRAJECTORY_BUILDER_2D.min_range = 0.20
TRAJECTORY_BUILDER_2D.max_range = 12.0
-- NOTE: min_z/max_z here only filter raw POINT CLOUD input. We feed a 2D LaserScan
-- (num_laser_scans=1), which is already flattened, so the real height slice that
-- keeps us on the ~0.20 m walls lives in config/pointcloud_to_laserscan_indoor.yaml.
TRAJECTORY_BUILDER_2D.min_z = -0.15
TRAJECTORY_BUILDER_2D.max_z = 0.35
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 5.0
TRAJECTORY_BUILDER_2D.num_accumulated_range_data = 1
-- The EKF already fuses the Livox IMU into odom; feeding IMU again here would
-- need correct IMU-frame extrinsics and risks double-counting. Keep it off and
-- let EKF odometry + scan matching drive local SLAM.
TRAJECTORY_BUILDER_2D.use_imu_data = false
-- Correlative matcher adds robustness when odom is noisy (your hardware case).
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true
TRAJECTORY_BUILDER_2D.motion_filter.max_time_seconds = 5.0
TRAJECTORY_BUILDER_2D.motion_filter.max_distance_meters = 0.05
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = 0.12

-- ---- Global SLAM / loop closure ------------------------------------------
POSE_GRAPH.optimize_every_n_nodes = 35
POSE_GRAPH.constraint_builder.sampling_ratio = 0.3
POSE_GRAPH.constraint_builder.min_score = 0.55
POSE_GRAPH.constraint_builder.global_localization_min_score = 0.60
POSE_GRAPH.constraint_builder.loop_closure_translation_weight = 1.1e4
POSE_GRAPH.constraint_builder.loop_closure_rotation_weight = 1.0e5
POSE_GRAPH.optimization_problem.huber_scale = 1.0e2

return options
