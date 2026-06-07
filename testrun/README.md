# Test run data

Recorded bags, maps, and figures from development sessions (June 2026).

**New team:** create `testrun/my_run/` when following [../docs/MAPPING_AND_RACELINE_GUIDE.md](../docs/MAPPING_AND_RACELINE_GUIDE.md).

**Status:** Map pipeline validated in `june7_set7/`. Use `traj_race_cl.csv` from there for first pursuit tests — see [../docs/HANDOFF_STATUS.md](../docs/HANDOFF_STATUS.md).

---

## Reference results

| Folder | Notes |
|--------|--------|
| **`june7_set7/`** | **Best run** — use for comparison and first pursuit CSV |
| `june7_set6/` | Good offline pipeline example |
| `june6/` | Earlier attempts |

Key files in `june7_set7/`:

| File | Use |
|------|-----|
| `FINAL_berlin_dedrift.png` | Reference figure (compare to your `FINAL_track_map.png`) |
| `traj_race_cl.csv` | Load on car for pursuit testing |
| `lap3x/` | Source rosbag |
| `track_dedrift.pgm` | De-drifted map |

---

## Your run folder structure

```
testrun/my_run/
  lap_bag/              ← from car (Part A)
  maps/
    track_dedrift.pgm   ← Part B1
    track_dedrift.yaml
  traj_race_cl.csv      ← Part B2
  FINAL_track_map.png   ← deliverable figure
```

---

## Git note

Bag folders can be large. Consider gitignoring local `testrun/my_run/lap_bag/` and committing only CSVs/PNGs.
