# A minimal Path message compatible with pose-based followers.
#
# Note: This intentionally mirrors nav_msgs/Path so we can use mav_msgs/Path
# as the "optimizer output" container while keeping integration simple.

std_msgs/Header header
geometry_msgs/PoseStamped[] poses

