# Manual map logging with Cartographer + EKF — full runbook

SSH → launch → record a lap → pull the CSV to your Mac. Uses the fixed image
`nabilafifahq/roboracer-t7:cartographer-ekf` (EKF + Cartographer, IMU TF, wall-band LiDAR slice).

**Three places** — know which prompt you're at:

| Prompt | Place | What runs here |
|--------|-------|----------------|
| `naqotrunnadda@…%` | **Mac** | `docker push`, `scp` (pull CSV) |
| `ucsd-blue@ucsd-blue:~$` | **Pi host** (SSH) | `docker pull`, `car_run.sh`, `docker exec`, `docker cp` |
| `root@ucsd-blue:/race_ws#` | **Container** | all `ros2` commands, the logger |

You need **two container shells**: Terminal **A** (the launch) and Terminal **B** (preflight + logger).

---

## Part 0 — ONE-TIME: pull the image onto the car

Do this **once** (or again only when a new image is pushed). After this, day-to-day you just run `car_run.sh`; it reuses the local image and does **not** re-pull.

```bash
# Mac: make sure the image is on Docker Hub (you already built it)
docker push nabilafifahq/roboracer-t7:cartographer-ekf      # only if not pushed yet

# Pi host (SSH in first):
ssh ucsd-blue@ucsd-blue.local
docker pull nabilafifahq/roboracer-t7:cartographer-ekf
```
**Gate:** pull ends with `Digest: sha256:…` and `Status: Downloaded newer image`. If it says "Image is up to date" and you expected changes, the new image wasn't pushed.

> Re-pull later only when you push a new image: `docker pull nabilafifahq/roboracer-t7:cartographer-ekf`.

---

## Part 1 — Power-up + SSH (every session)

1. **RC controller ON first**, then car power ON.
2. Put the car **on a box (wheels up)** for the first checks.
3. From the Mac:
   ```bash
   ssh ucsd-blue@ucsd-blue.local
   ```

---

## Part 2 — Terminal A: start container + launch the stack

**Pi host:**
```bash
cd ~/roboracer-t7
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
./scripts/car_run.sh
```
You're now at `root@ucsd-blue:/race_ws#` (container, **Terminal A**). Set up VESC + source:
```bash
mkdir -p /dev/sensors
ln -sf /dev/ttyACM0 /dev/sensors/vesc      # if VESC doesn't connect, try /dev/ttyACM1
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
printenv RMW_IMPLEMENTATION                 # GATE: rmw_cyclonedds_cpp
```
Launch (EKF + Cartographer):
```bash
ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true
```
**Expect:** nodes start, you see **`cartographer_node`** in the log (NOT dying/respawning). VESC says "Connected … firmware 6.6", joy "Opened joystick".
**Leave this running the whole session.** `wall_follow` "Invalid lidar scan" / `/drive` QoS warnings are harmless for mapping.

---

## Part 3 — Terminal B: open a second shell + preflight gates

**New Pi-host SSH tab**, then exec into the *same* container:
```bash
ssh ucsd-blue@ucsd-blue.local
docker exec -it roboracer_t7 bash
# now inside container:
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
```

Run the gates **in order** — don't proceed past a failed gate:

```bash
ros2 node list | grep cartographer_node          # GATE: cartographer_node present
ros2 topic list | grep -E '^/map$'               # GATE: prints /map
ros2 topic hz /scan --window 20                  # GATE: non-zero rate (Ctrl+C to stop)
ros2 run tf2_ros tf2_echo base_link livox_frame  # GATE: resolves (IMU TF fix)
ros2 run tf2_ros tf2_echo odom base_link         # GATE: EKF, updates
ros2 run tf2_ros tf2_echo map base_link          # see sequence below
```

**`map → base_link` gate sequence:**
1. Briefly may print **"map does not exist"** — wait **10–30 s** after launch.
2. **Pass:** steady `At time … Translation: […]` lines, no permanent "map does not exist".
3. **Drive ~1 m slowly** with the joystick (Terminal A still running).
4. **Pass:** Translation **X/Y change while moving**. If they don't move while you ARE driving → **stop, do not log** (fix SLAM/scan/motion first; see triage).

`Ctrl+C` `tf2_echo` when satisfied.

---

## Part 4 — Terminal B: start the logger + drive the lap

```bash
mkdir -p /race_ws/logs
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map \
  -p robot_frame:=base_link \
  -p record_hz:=20.0 \
  -p output_csv:=/race_ws/logs/map_cart_$(date +%Y%m%d_%H%M%S).csv
```
Note the printed filename. Then **drive ONE smooth, continuous lap** at walking pace, close the loop, minimal stops. (If the car pulls right, that's the servo trim — counter-steer gently; it adds noise but won't block logging.)

**Watch it grow** — third shell (`docker exec -it roboracer_t7 bash`) or check periodically:
```bash
watch -n 1 'wc -l /race_ws/logs/map_cart_*.csv'     # or: wc -l /race_ws/logs/map_cart_*.csv
```
**Gate:** line count grows well past 2 into the **hundreds**. Endless TF errors every 2 s for the whole run = bad → stop and fix TF.

---

## Part 5 — Stop in the RIGHT order + verify CSV

**Order matters** (stopping bringup first breaks TF and ruins the file tail):

1. **Terminal B:** `Ctrl+C` the **logger** (only the logger).
2. **Terminal B:** verify the CSV on the car:
   ```bash
   wc -l /race_ws/logs/map_cart_*.csv          # GATE: large
   head -15 /race_ws/logs/map_cart_*.csv       # GATE: x,y non-zero and CHANGING
   ```
   Columns: `time_sec, frame_id, x, y, z, yaw_rad, left_wall_m, right_wall_m, scan_stamp_sec`.
3. **Copy out of the container to the Pi home:**
   ```bash
   # find the exact name first:
   ls -t /race_ws/logs/map_cart_*.csv | head -1
   ```
   then, on the **Pi host** (new tab or exit container):
   ```bash
   docker cp roboracer_t7:/race_ws/logs/map_cart_YYYYMMDD_HHMMSS.csv ~/
   ```
4. **Terminal A:** `Ctrl+C` the `ros2 launch` (fully done).

---

## Part 6 — Pull the CSV to your Mac

Run **from the Mac** (it pulls from the Pi). Destination is your analysis folder:

```bash
scp ucsd-blue@ucsd-blue.local:~/map_cart_YYYYMMDD_HHMMSS.csv \
    /Users/naqotrunnadda/Documents/roboracer-t7/test_manual_map_new/
```

Or grab everything at once:
```bash
scp 'ucsd-blue@ucsd-blue.local:~/map_cart_*.csv' \
    /Users/naqotrunnadda/Documents/roboracer-t7/test_manual_map_new/
```

**Verify on the Mac:**
```bash
cd /Users/naqotrunnadda/Documents/roboracer-t7/test_manual_map_new
wc -l map_cart_YYYYMMDD_HHMMSS.csv
head -15 map_cart_YYYYMMDD_HHMMSS.csv     # x,y vary, not all zeros
```
Then process with your existing scripts in that folder (`visualize_closed_loop_track.py`, `visualize_straight_track.py`, `process_multi_run_map.py`).

---

## Triage — if a gate fails

| Symptom | Likely cause / fix |
|---------|---------------------|
| `wc -l` stays 1 (header only) | TF never succeeded — bringup stopped, `map` missing, or wasn't moving. |
| `tf2_echo base_link livox_frame` fails | Not the new image — confirm `IMAGE=…:cartographer-ekf`. |
| `tf2_echo map base_link` never sees `map` | `use_cartographer` not set, or `cartographer_node` died — check Terminal A log. |
| Translation never moves while driving | SLAM not localizing — `/scan` rate? walls in slice? drive smoother. |
| `cartographer_node` dies on start | Old image / hand-edited lua — this image is fixed; re-pull `:cartographer-ekf`. |
| `/scan` rate zero / gaps | Livox QoS/network, or height slice too tight — widen `max_height` ~2 cm, rebuild. |
| VESC not connected | Wrong ACM — `ln -sf /dev/ttyACM1 /dev/sensors/vesc` and relaunch. |
| Pull says "up to date" but you changed code | Image not pushed, or wrong tag. |

---

## One-screen quick reference

```bash
# ONE-TIME (Pi host): pull image
docker pull nabilafifahq/roboracer-t7:cartographer-ekf

# Terminal A (Pi host -> container): launch
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
./scripts/car_run.sh
#   in container:
ln -sf /dev/ttyACM0 /dev/sensors/vesc
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true

# Terminal B (Pi host -> same container): preflight + log
docker exec -it roboracer_t7 bash
source /opt/ros/humble/setup.bash && source /race_ws/install/setup.bash
ros2 run tf2_ros tf2_echo map base_link            # wait until it moves when you drive
ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map -p robot_frame:=base_link -p record_hz:=20.0 \
  -p output_csv:=/race_ws/logs/map_cart_$(date +%Y%m%d_%H%M%S).csv
# drive one smooth lap -> Ctrl+C logger -> Ctrl+C launch

# Pi host: copy out of container
docker cp roboracer_t7:/race_ws/logs/map_cart_YYYYMMDD_HHMMSS.csv ~/

# Mac: pull to analysis folder
scp ucsd-blue@ucsd-blue.local:~/map_cart_YYYYMMDD_HHMMSS.csv \
    /Users/naqotrunnadda/Documents/roboracer-t7/test_manual_map_new/
```
