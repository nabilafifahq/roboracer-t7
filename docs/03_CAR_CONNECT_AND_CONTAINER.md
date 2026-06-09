# Car Connect and Container Startup

Connect to the car and enter the runtime container.

**Before first session:** read [PHYSICAL_SETUP.md](PHYSICAL_SETUP.md) (Wi-Fi, power-on, track).  

---

## Which machine?

| Step | Run on | Prompt looks like |
|------|--------|-------------------|
| SSH, docker pull, car_run.sh | **Pi host** (via SSH from laptop) | `ucsd-blue@UCSD-Blue:~$` |
| ROS commands, launch | **Container** (after car_run.sh) | `root@UCSD-Blue:/race_ws#` |

---

## 0) Network prerequisite (before SSH)

1. Join the same Wi-Fi network as the car — **`ucsd_robocar`** (see [PHYSICAL_SETUP.md](PHYSICAL_SETUP.md) §2).
2. Confirm you are on the **1/10 blue car** (UCSD-Blue).
3. Connect:

```bash
ssh ucsd-blue@ucsd-blue.local
```

If `.local` does not resolve, use the car's IP: `ssh ucsd-blue@<car_ip>`.

---

## 1) Power-on sequence (every time)

1. Turn **ON** the RC transmitter first.
2. Turn **ON** car power.
3. Wait 20–60 seconds for Pi boot.
4. From laptop:

```bash
ping -c 2 ucsd-blue.local
```

---

## 2) SSH into car host

```bash
ssh ucsd-blue@ucsd-blue.local
cd ~/roboracer-t7
git fetch origin && git checkout docs/clean-handoff && git pull
```

**Expected:** Prompt `ucsd-blue@UCSD-Blue:~$`

---

## 3) Pull Docker image

**Use this tag everywhere** (same as all other docs):

```bash
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
docker pull "$IMAGE"
```

**Expected:** Pull completes. Verify:

```bash
docker images | grep cartographer-ekf
```

---

## 4) Start container (Tab 1 for mapping sessions)

From repo root on **Pi host**:

```bash
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
./scripts/car_run.sh
```

**Expected:** Prompt changes to `root@UCSD-Blue:/race_ws#` — you are **inside the container**.

If `No such file or directory`: run `cd ~/roboracer-t7` first.

Other helpers (run on **Pi host**, not inside container):

```bash
./scripts/car_status.sh    # is container running?
./scripts/car_exec.sh      # open another shell inside container
./scripts/car_stop.sh      # stop container
```

---

## 5) Source ROS environment

Inside container (automatic if you used `car_run.sh` or `car_exec.sh`):

```bash
source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
printenv | grep ROS_DISTRO=
```

**Expected:** `ROS_DISTRO=humble`

Every **new** shell inside the container needs these source commands (or use `./scripts/car_exec.sh` from Pi host).

---

## 6) VESC device symlink

Inside container (once per session):

```bash
sudo mkdir -p /dev/sensors
sudo ln -sf /dev/ttyACM0 /dev/sensors/vesc
ls -l /dev/sensors/vesc
```

**Expected:** Points to `/dev/ttyACM0` (STM/VESC), **not** `ttyACM1` (Arduino RC).

Note: `car_map_setup.sh` (used in the mapping guide) also creates this symlink.

---

## 7) Open a second container shell (for mapping)

From **Pi host** (new SSH tab — prompt `ucsd-blue@...`):

```bash
cd ~/roboracer-t7
./scripts/car_exec.sh
```

**Expected:** Second container shell at `root@UCSD-Blue:/race_ws#`.

See [MAPPING_AND_RACELINE_GUIDE.md](MAPPING_AND_RACELINE_GUIDE.md) for the full 3-tab layout.

---

## 8) Power-off sequence

1. Stop ROS launch (`Ctrl+C` in container).
2. Exit container or run `./scripts/car_stop.sh` on Pi host.
3. Turn **OFF** car power.
4. Turn **OFF** RC transmitter last.
