-- RoboRacer T7: load official ROS Humble map_builder (includes pose_graph.lua with
-- fast_correlative_scan_matcher_3d schema required by cartographer 2.0.x).
-- Do not define FAST_CORRELATIVE_SCAN_MATCHER_3D here (old keys crash the node).
dofile('/opt/ros/humble/share/cartographer/configuration_files/map_builder.lua')

MAP_BUILDER.use_trajectory_builder_2d = true
MAP_BUILDER.use_trajectory_builder_3d = false
MAP_BUILDER.num_background_threads = 2
