-- 2D trajectory builder tuned for indoor hallway + pointcloud_to_laserscan slice
TRAJECTORY_BUILDER_2D = {
  min_range = 0.20,
  max_range = 12.0,
  min_z = -0.15,
  max_z = 0.35,
  missing_data_ray_length = 5.0,
  num_accumulated_range_data = 1,
  -- Livox IMU frame vs base_link can be finicky; odometry from EKF is primary.
  use_imu_data = false,
  use_online_correlative_scan_matching = true,
  motion_filter = {
    max_time_seconds = 5.0,
    max_distance_meters = 0.05,
    max_angle_radians = 0.12,
  },
}

POSE_GRAPH = {
  optimize_every_n_nodes = 35,
  constraint_builder = {
    sampling_ratio = 0.3,
    min_score = 0.55,
    global_localization_min_score = 0.60,
    loop_closure_translation_weight = 1.1e4,
    loop_closure_rotation_weight = 1.0e5,
  },
  optimization_problem = {
    huber_scale = 1.0e2,
  },
}

TRAJECTORY_BUILDER = TRAJECTORY_BUILDER_2D
