-- RoboRacer T7: 2D Cartographer PURE LOCALIZATION on a saved map.
--
-- Use this on race day instead of mapping: load a frozen map (.pbstream saved
-- during a mapping lap) and only localize against it, so map -> odom stays
-- globally consistent without rebuilding/growing the map.
--
-- Launch with:
--   ros2 launch /race_ws/launch/cartographer_2d.launch.py \
--     configuration_basename:=roboracer_2d_localization.lua \
--     load_state_filename:=/race_ws/maps/<track>.pbstream
--
-- Inherits all frames / sensor settings from the mapping config, then switches
-- the pose graph into pure-localization mode.

include "roboracer_2d.lua"

-- Keep only a few recent submaps; do not grow the saved map.
TRAJECTORY_BUILDER.pure_localization_trimmer = {
  max_submaps_to_keep = 3,
}

-- Optimize a little more often so relocalization after a spin/U-turn snaps back.
POSE_GRAPH.optimize_every_n_nodes = 20

return options
