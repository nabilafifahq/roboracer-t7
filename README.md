# RoboRacer T7

UCSD Winter 2026 Team 7 — F1TENTH indoor RoboRacer (1/10 scale).

**Handoff repo** for the next team.

---

## Start here (new team)

| # | Doc | Purpose |
|---|-----|---------|
| 1 | [docs/00_START_HERE.md](docs/00_START_HERE.md) | Router |
| 2 | **[docs/HANDOFF_STATUS.md](docs/HANDOFF_STATUS.md)** | **What works / where you pick up** |
| 3 | [docs/PHYSICAL_SETUP.md](docs/PHYSICAL_SETUP.md) | Car, track, Wi-Fi, layout |
| 4 | [docs/MAPPING_AND_RACELINE_GUIDE.md](docs/MAPPING_AND_RACELINE_GUIDE.md) | Map pipeline + pursuit steps |

**Current States**: See [Progress Update](https://docs.google.com/presentation/d/1Z3oOzJPs9dkZyqz4G1NnzSDlAGju_gPKxS-lMDGGmN4/edit?usp=sharing)

**Pick-up task:** Run raceline with Pure Pursuit algorithm in map frame (implemented but not tested).

---

## Quick reference

```bash
export IMAGE=nabilafifahq/roboracer-t7:cartographer-ekf
docker pull "$IMAGE"
```

**Mapping:** 3 terminal tabs on laptop → see mapping guide Part A.  
**Laptop pipeline:** `cartographer_offline_dedrift.sh` → `build_raceline_from_bag.py`  
**Reference output:** `testrun/june7_set7/`

---

## Repo layout

[docs/PROJECT_LAYOUT.md](docs/PROJECT_LAYOUT.md)

---

## Docs index

[docs/README.md](docs/README.md)
