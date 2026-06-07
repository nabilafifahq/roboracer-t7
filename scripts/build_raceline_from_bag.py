#!/usr/bin/env python3
"""
build_raceline_from_bag.py  —  ONE deterministic pipeline:
    rosbag (/scan,/tf,/odom) + Cartographer map (.pgm/.yaml)  ->  measured track + TUM raceline + figures

This replaces the ad-hoc steps used on june7_set6 so every run uses the SAME algorithm.
Two products, both in the `map` frame so they overlay exactly:
  (A) measured map      : occupancy grid statistics + extracted walls  (from .pgm)
  (B) raceline          : driven path -> clean centerline -> MEASURED widths -> TUM mincurv

Width is MEASURED (ray-cast to the occupied cells of the map), not modelled. Drive slower
and closer to the inner box so the box is well-observed; then the left/right widths are real.

Pipeline (each stage is a single, documented algorithm):
  1. read path     : compose map->odom (Cartographer) o odom->base_link (VESC) per /tf sample  [exact SE(2)]
  2. laps          : angle unwrap around centroid -> revolutions
  3. centerline    : per-angle-bin radial envelope (percentiles) -> mid loop -> Fourier(N) low-pass
  4. widths        : ray-cast centerline normals into the occupancy grid -> dL,dR (MEASURED)
                     re-center line to mid-corridor, symmetric half = (dL+dR)/2, circular-median smooth,
                     clamp to [W_MIN, WIDTH_RADIUS_FRAC*local_radius]  (keeps TUM boundaries non-crossing)
  5. TUM input     : resample at STEP_M, write '# x_m,y_m,w_tr_right_m,w_tr_left_m'
  6. TUM mincurv   : run roboracer-t7-raceline container with the small-track fixes (optional --run-tum)
  7. figures       : raw map, envelope, final Berlin-style overlay

Usage:
    python3 scripts/build_raceline_from_bag.py \
        --bag   testrun/june7_set6/lap3x \
        --pgm   testrun/june7_set6/maps_4x/track.pgm \
        --yaml  testrun/june7_set6/maps_4x/track.yaml \
        --outdir testrun/june7_set6 \
        --run-tum                      # needs docker + roboracer-t7-raceline:latest (amd64)

Deps: numpy, scipy, matplotlib, pillow, rosbags.
"""
from __future__ import annotations
import argparse, os, subprocess, sys
from dataclasses import dataclass
import numpy as np

# ----------------------------------------------------------------------------- CONFIG (single source of truth)
@dataclass
class Cfg:
    n_bins: int = 72            # angular bins for the radial envelope
    p_inner: float = 8.0        # percentile -> inner envelope (outlier-robust vs min)
    p_outer: float = 92.0       # percentile -> outer envelope (outlier-robust vs max)
    smooth_k: int = 5           # circular moving-average window over bins
    fourier_n: int = 3          # Fourier harmonics kept for the centerline (low-pass). 3-5 typical
    fourier_m: int = 400        # samples of the reconstructed Fourier curve
    cast_max: float = 2.60      # [m] max ray length when measuring width in the grid
    cast_step: float = 0.025    # [m] ray marching step
    width_min: float = 0.22     # [m] floor on half-width
    width_radius_frac: float = 0.65   # half-width <= frac * local radius (no boundary self-cross)
    width_median_k: int = 7     # circular median filter window for the width profile
    step_m: float = 0.15        # [m] resample spacing for the TUM track
    recenter_passes: int = 0    # 0 = measure on the clean mid-envelope line (robust default).
                                # >0 nudges toward true mid-corridor but can distort on noisy maps.
CFG = Cfg()

# ----------------------------------------------------------------------------- stage 1: path from bag
def quat_yaw(x, y, z, w):
    return np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))

def read_path(bag: str):
    from rosbags.rosbag2 import Reader
    from rosbags.typesys import Stores, get_typestore
    ts = get_typestore(Stores.ROS2_HUMBLE)
    mo, ob, scans = [], [], []
    with Reader(bag) as r:
        for con, t, raw in r.messages():
            if con.topic == '/tf':
                m = ts.deserialize_cdr(raw, con.msgtype)
                for tr in m.transforms:
                    p, c = tr.header.frame_id, tr.child_frame_id
                    tt, q = tr.transform.translation, tr.transform.rotation
                    if p == 'map' and c == 'odom':
                        mo.append((t, tt.x, tt.y, quat_yaw(q.x, q.y, q.z, q.w)))
                    elif p == 'odom' and c == 'base_link':
                        ob.append((t, tt.x, tt.y, quat_yaw(q.x, q.y, q.z, q.w)))
            elif con.topic == '/scan':
                m = ts.deserialize_cdr(raw, con.msgtype)
                scans.append((t, m.angle_min, m.angle_increment,
                              np.asarray(m.ranges, np.float32), m.range_max))
    mo, ob = np.array(mo), np.array(ob)
    def interp(a, t):
        i = np.searchsorted(a[:, 0], t); i = min(max(i, 1), len(a) - 1)
        return a[i, 1], a[i, 2], a[i, 3]
    path = []
    for t, bx, by, byaw in ob:                       # exact SE(2) composition  map->odom o odom->base
        mx, my, myaw = interp(mo, t)
        c, s = np.cos(myaw), np.sin(myaw)
        path.append((t, mx + c * bx - s * by, my + s * bx + c * by, myaw + byaw))
    return np.array(path), mo, ob, scans

# ----------------------------------------------------------------------------- stage 2: laps
def revolutions(X, Y, cx, cy):
    th = np.unwrap(np.arctan2(Y - cy, X - cx))
    return (th[-1] - th[0]) / (2 * np.pi)

# ----------------------------------------------------------------------------- stage 3: centerline
def fill_periodic(ang, a):
    g = np.isfinite(a)
    return np.interp(ang, ang[g], a[g], period=2 * np.pi)

def circ_smooth(a, k):
    from scipy.ndimage import uniform_filter1d
    return uniform_filter1d(a, k, mode='wrap')

def radial_envelope(X, Y, cx, cy, cfg=CFG):
    phi = np.mod(np.arctan2(Y - cy, X - cx), 2 * np.pi)
    r = np.hypot(X - cx, Y - cy)
    edges = np.linspace(0, 2 * np.pi, cfg.n_bins + 1)
    ang = (edges[:-1] + edges[1:]) / 2
    idx = np.clip(np.digitize(phi, edges) - 1, 0, cfg.n_bins - 1)
    rin = np.full(cfg.n_bins, np.nan); rout = np.full(cfg.n_bins, np.nan); rmid = np.full(cfg.n_bins, np.nan)
    for b in range(cfg.n_bins):
        rr = r[idx == b]
        if rr.size > 2:
            rin[b] = np.percentile(rr, cfg.p_inner)
            rout[b] = np.percentile(rr, cfg.p_outer)
            rmid[b] = np.median(rr)
    rin, rout, rmid = (circ_smooth(fill_periodic(ang, a), cfg.smooth_k) for a in (rin, rout, rmid))
    return ang, rin, rout, rmid

def fourier_loop(px, py, th, n, m):
    tt = np.linspace(0, 2 * np.pi, m, endpoint=False)
    def rec(vals):
        out = np.full(m, vals.mean())
        for k in range(1, n + 1):
            out += 2 * np.mean(vals * np.cos(k * th)) * np.cos(k * tt) \
                 + 2 * np.mean(vals * np.sin(k * th)) * np.sin(k * tt)
        return out
    return rec(px), rec(py)

# ----------------------------------------------------------------------------- stage 4: MEASURED widths from map
class Grid:
    def __init__(self, pgm, yaml):
        from PIL import Image
        self.img = np.array(Image.open(pgm))
        meta = {}
        for ln in open(yaml):
            if ':' in ln:
                k, v = ln.split(':', 1); meta[k.strip()] = v.strip()
        self.res = float(meta['resolution'])
        ox, oy = meta['origin'].strip('[] ').split(',')[:2]
        self.ox, self.oy = float(ox), float(oy)
        self.H, self.W = self.img.shape
        self.occ = (self.img == 0)
    def occupied(self, x, y):
        c = int(round((x - self.ox) / self.res)); r = int(round(self.H - 1 - (y - self.oy) / self.res))
        if r < 0 or r >= self.H or c < 0 or c >= self.W:
            return None
        return bool(self.occ[r, c])
    def cast(self, x, y, dx, dy, cfg=CFG):
        d = 0.0
        while d < cfg.cast_max:
            d += cfg.cast_step
            o = self.occupied(x + dx * d, y + dy * d)
            if o is None:
                return np.nan          # ran off the map -> no wall measured here
            if o:
                return d
        return np.nan

def normals(sx, sy):
    dx = np.gradient(np.r_[sx, sx[0]])[:-1]; dy = np.gradient(np.r_[sy, sy[0]])[:-1]
    n = np.hypot(dx, dy)
    return -dy / n, dx / n               # left normal (+90 deg)

def local_radius(sx, sy):
    dx = np.gradient(np.r_[sx, sx[0]])[:-1]; dy = np.gradient(np.r_[sy, sy[0]])[:-1]
    ddx = np.gradient(np.r_[dx, dx[0]])[:-1]; ddy = np.gradient(np.r_[dy, dy[0]])[:-1]
    curv = np.abs(dx * ddy - dy * ddx) / np.power(dx * dx + dy * dy, 1.5)
    return 1.0 / np.maximum(curv, 1e-6)

def _cast_both(grid, px, py, cx, cy):
    """Left normal made to point toward the centroid (box); return dL(box), dR(hose)."""
    nx, ny = normals(px, py)
    flip = (nx * (cx - px) + ny * (cy - py)) < 0
    nx = np.where(flip, -nx, nx); ny = np.where(flip, -ny, ny)
    dL = np.array([grid.cast(px[i], py[i],  nx[i],  ny[i]) for i in range(len(px))])  # box side
    dR = np.array([grid.cast(px[i], py[i], -nx[i], -ny[i]) for i in range(len(px))])  # hose side
    return nx, ny, dL, dR

def measure_widths(grid, sx, sy, cx, cy, cfg=CFG):
    """Ray-cast both normals into the occupied grid -> MEASURED dL (box), dR (hose).
    Gently re-center toward mid-corridor (clamped + re-Fourier each pass so the loop stays smooth),
    then take a CONSERVATIVE symmetric half = min(dL,dR): a boundary never extends past the nearer
    measured wall, so it can't cross into the box or the hose even if the line isn't perfectly centered."""
    from scipy.ndimage import median_filter
    px, py = sx.copy(), sy.copy()
    for _ in range(cfg.recenter_passes):
        nx, ny, dL, dR = _cast_both(grid, px, py, cx, cy)
        both = np.isfinite(dL) & np.isfinite(dR)
        shift = np.zeros(len(px))
        shift[both] = np.clip((dL[both] - dR[both]) / 2.0, -0.40, 0.40)   # clamp: missing rays -> no move
        px = px + nx * shift; py = py + ny * shift
        ang = np.mod(np.arctan2(py - cy, px - cx), 2 * np.pi)
        px, py = fourier_loop(px, py, ang, cfg.fourier_n, cfg.fourier_m)  # re-smooth -> no distortion
    nx, ny, dL, dR = _cast_both(grid, px, py, cx, cy)                     # final measured widths
    ang = np.mod(np.arctan2(py - cy, px - cx), 2 * np.pi); order = np.argsort(ang)
    dLf = _fill_loop(dL, ang, order); dRf = _fill_loop(dR, ang, order)
    half = np.minimum(dLf, dRf)                                           # conservative -> never crosses a wall
    half = median_filter(half, size=cfg.width_median_k, mode='wrap')
    half = np.minimum(half, cfg.width_radius_frac * local_radius(px, py)) # keep TUM boundaries non-crossing
    half = np.clip(half, cfg.width_min, None)
    return px, py, half, dL, dR

def _fill_loop(vals, ang, order):
    v = vals.copy(); g = np.isfinite(v)
    if g.sum() < 3:
        v[~g] = np.nanmedian(v) if g.any() else CFG.width_min
        return v
    a = ang[order]; w = v[order]; gg = np.isfinite(w)
    w = np.interp(a, a[gg], w[gg], period=2 * np.pi)
    out = np.empty_like(v); out[order] = w
    return out

# ----------------------------------------------------------------------------- stage 5: write TUM input
def write_tum_csv(path, sx, sy, half, cfg=CFG):
    seg = np.hypot(np.diff(np.r_[sx, sx[0]]), np.diff(np.r_[sy, sy[0]]))
    s = np.r_[0, np.cumsum(seg)]; L = s[-1]
    ss = np.arange(0, L, cfg.step_m)
    rx = np.interp(ss, s, np.r_[sx, sx[0]]); ry = np.interp(ss, s, np.r_[sy, sy[0]])
    rh = np.interp(ss, s, np.r_[half, half[0]])
    with open(path, 'w') as f:
        f.write("# x_m,y_m,w_tr_right_m,w_tr_left_m\n")
        for x, y, h in zip(rx, ry, rh):
            f.write(f"{x:.6f},{y:.6f},{h:.6f},{h:.6f}\n")
    return L, len(rx)

# ----------------------------------------------------------------------------- stage 6: run TUM (docker)
# Patch applied inside the container to the baked main_globaltraj.py (avoids sed-quoting pitfalls):
#   - skip the strict pkg_resources version gate (installed wheels work)
#   - force track_name=hallway and opt_type=mincurv (image bakes berlin_2018 / mintime)
TUM_PATCH = (
    "import re\n"
    "p='main_globaltraj.py'; s=open(p).read()\n"
    "s=re.sub(r'pkg_resources\\.require\\(dependencies\\)','pass',s)\n"
    "s=re.sub(r'file_paths\\[\"track_name\"\\]\\s*=.*','file_paths[\"track_name\"] = \"hallway\"',s)\n"
    "s=re.sub(r'^opt_type\\s*=.*',\"opt_type = 'mincurv'\",s,flags=re.M)\n"
    "open(p,'w').write(s)\n"
)
def run_tum(repo_root, track_csv, ini_src, out_csv, image="roboracer-t7-raceline:latest"):
    data = os.path.join(repo_root, "raceline_data")
    os.makedirs(os.path.join(data, "inputs", "tracks"), exist_ok=True)
    os.makedirs(os.path.join(data, "params"), exist_ok=True)
    os.makedirs(os.path.join(data, "outputs"), exist_ok=True)
    import shutil
    shutil.copy(track_csv, os.path.join(data, "inputs", "tracks", "hallway.csv"))
    shutil.copy(ini_src,   os.path.join(data, "params", "racecar.ini"))
    with open(os.path.join(data, "patch_main.py"), "w") as f:
        f.write(TUM_PATCH)
    inner = (
        "cd /work/global_racetrajectory_optimization && "
        "cp /data/inputs/tracks/hallway.csv inputs/tracks/hallway.csv && "
        "cp /data/params/racecar.ini params/racecar.ini && "
        "python3 /data/patch_main.py && "
        "python main_globaltraj.py > /tmp/log.txt 2>&1; "
        "grep -E 'boundaries|deviation|Traceback|Error|crossed|EXIT' /tmp/log.txt | tail -5; "
        "cp -f outputs/traj_race_cl.csv /data/outputs/traj_race_cl.csv && echo TUM_OK || echo TUM_FAIL"
    )
    cmd = ["docker", "run", "--rm", "--platform", "linux/amd64", "-e", "MPLBACKEND=Agg",
           "-v", f"{data}:/data", image, "bash", "-lc", inner]
    print("[tum] running mincurv optimizer ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip());
    if "TUM_OK" not in r.stdout:
        print(r.stderr[-1500:]); raise RuntimeError("TUM failed; see output above")
    import shutil as sh; sh.copy(os.path.join(data, "outputs", "traj_race_cl.csv"), out_csv)
    return out_csv

def load_traj(p):
    rows = [l for l in open(p) if not l.startswith('#') and l.strip()]
    d = np.array([[float(v) for v in l.replace(';', ',').split(',')] for l in rows])
    return d  # s,x,y,psi,kappa,vx,ax

# ----------------------------------------------------------------------------- stage 7: figures
def figures(grid, path, env, sx, sy, half, traj, outdir):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    ext = [grid.ox, grid.ox + grid.W * grid.res, grid.oy, grid.oy + grid.H * grid.res]
    disp = np.full_like(grid.img, 255); disp[grid.img == 0] = 0; disp[grid.img == 205] = 235
    nx, ny = normals(sx, sy)
    lbx, lby = sx + nx * half, sy + ny * half
    rbx, rby = sx - nx * half, sy - ny * half
    rx, ry, vx = traj[:, 1], traj[:, 2], traj[:, 5]
    fig, axs = plt.subplots(1, 2, figsize=(18, 8))
    ax = axs[0]
    ax.imshow(np.flipud(disp), cmap='gray', origin='lower', extent=ext, vmin=0, vmax=255)
    ax.plot(path[:, 1], path[:, 2], color='0.6', lw=0.4, alpha=0.6, label='driven path')
    for bx, by in [(lbx, lby), (rbx, rby)]:
        ax.plot(np.r_[bx, bx[0]], np.r_[by, by[0]], color='tab:blue', lw=1.2)
    ax.plot(np.r_[rx, rx[0]], np.r_[ry, ry[0]], 'r-', lw=2.3, label='TUM raceline')
    ax.plot([], [], color='tab:blue', label='measured track bounds')
    ax.set_aspect('equal'); ax.legend(fontsize=8); ax.set_title('measured map + measured bounds + raceline')
    ax = axs[1]
    for bx, by in [(lbx, lby), (rbx, rby)]:
        ax.plot(np.r_[bx, bx[0]], np.r_[by, by[0]], 'k-', lw=2)
    pts = np.column_stack([np.r_[rx, rx[0]], np.r_[ry, ry[0]]])
    seg = np.concatenate([pts[:-1, None], pts[1:, None]], axis=1)
    lc = LineCollection(seg, cmap='viridis', lw=4); v = np.r_[vx, vx[0]]
    lc.set_array((v[:-1] + v[1:]) / 2); ax.add_collection(lc)
    fig.colorbar(lc, ax=ax, fraction=0.046, pad=0.04).set_label('raceline speed (m/s)')
    ax.set_aspect('equal'); ax.set_title('Berlin-style: measured boundaries + optimal raceline')
    plt.tight_layout(); out = os.path.join(outdir, 'FINAL_berlin.png'); plt.savefig(out, dpi=140)
    print(f"[fig] {out}")

# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bag', required=True)
    ap.add_argument('--pgm', required=True)
    ap.add_argument('--yaml', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--run-tum', action='store_true')
    ap.add_argument('--ini', default=None, help='F1TENTH racecar.ini (default: docker/tum_overrides/racecar.ini)')
    ap.add_argument('--fourier-n', type=int, default=CFG.fourier_n)
    a = ap.parse_args()
    CFG.fourier_n = a.fourier_n
    os.makedirs(a.outdir, exist_ok=True)
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini = a.ini or os.path.join(repo, 'docker', 'tum_overrides', 'racecar.ini')

    print('[1] reading bag ...')
    path, mo, ob, scans = read_path(a.bag)
    X, Y = path[:, 1], path[:, 2]
    cx, cy = np.median(X), np.median(Y)
    print(f'    {len(path)} poses, centroid ({cx:.2f},{cy:.2f}), {revolutions(X,Y,cx,cy):.2f} revolutions')

    print('[2/3] envelope + Fourier centerline ...')
    ang, rin, rout, rmid = radial_envelope(X, Y, cx, cy)
    mx = cx + rmid * np.cos(ang); my = cy + rmid * np.sin(ang)
    sx, sy = fourier_loop(mx, my, ang, CFG.fourier_n, CFG.fourier_m)
    print(f'    centerline min radius {local_radius(sx,sy).min():.2f} m')

    print('[4] measuring widths from map ...')
    grid = Grid(a.pgm, a.yaml)
    occ = grid.occ.sum()
    print(f'    map {grid.W}x{grid.H}px res {grid.res}  occupied {occ} ({100*occ/grid.img.size:.1f}%)')
    sx, sy, half, dL, dR = measure_widths(grid, sx, sy, cx, cy)
    miss = np.isnan(dL).sum() + np.isnan(dR).sum()
    print(f'    half-width median {np.median(half):.2f} ({half.min():.2f}-{half.max():.2f})  '
          f'unmeasured rays {miss} (interpolated)')

    print('[5] writing TUM track ...')
    track = os.path.join(a.outdir, 'tum_track_input.csv')
    L, n = write_tum_csv(track, sx, sy, half); print(f'    {n} pts, {L:.2f} m -> {track}')

    env = dict(ang=ang, rin=rin, rout=rout, cx=cx, cy=cy)
    traj_path = os.path.join(a.outdir, 'traj_race_cl.csv')
    if a.run_tum:
        print('[6] TUM mincurv ...')
        run_tum(repo, track, ini, traj_path)
        traj = load_traj(traj_path)
        print(f'    raceline {len(traj)} pts, |kappa|max {np.abs(traj[:,4]).max():.2f} rad/m')
        print('[7] figures ...'); figures(grid, path, env, sx, sy, half, traj, a.outdir)
    else:
        print('[6] skipped TUM (--run-tum to enable). Track input written for manual run.')
    print('DONE.')

if __name__ == '__main__':
    sys.exit(main())
