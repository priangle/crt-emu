"""Recover the native pixel grid of an upscaled pixel-art crop (block size px, py may be fractional)."""
import sys
import numpy as np
from PIL import Image

def best_phase(a, p, axis):
    d = np.abs(np.diff(a.astype(float), axis=axis)).sum(axis=2).sum(axis=1 - axis)
    n = len(d)
    best = None
    for ph10 in range(int(p * 10)):
        ph = ph10 / 10.0
        idx = np.arange(ph, n - 1, p).astype(int)
        score = d[np.clip(idx, 0, n - 1)].sum() / max(len(idx), 1)
        if best is None or score > best[0]:
            best = (score, ph)
    return best[1]

def refine_period(a, axis, lo, hi):
    d = np.abs(np.diff(a.astype(float), axis=axis)).sum(axis=2).sum(axis=1 - axis)
    best = None
    for p100 in range(int(lo * 100), int(hi * 100)):
        p = p100 / 100.0
        for ph10 in range(0, int(p * 10)):
            ph = ph10 / 10.0
            idx = np.round(np.arange(ph, len(d) - 1, p)).astype(int)
            s = d[np.clip(idx, 0, len(d) - 1)].mean() - d.mean()
            if best is None or s > best[0]:
                best = (s, p, ph)
    return best[1], best[2]

src, out, x0, y0, x1, y1, pxlo, pxhi, pylo, pyhi = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7]), *map(float, sys.argv[7:11])
a = np.asarray(Image.open(src).convert("RGB").crop((x0, y0, x1, y1)))
px, phx = refine_period(a, 1, pxlo, pxhi)
py, phy = refine_period(a, 0, pylo, pyhi)
xs = np.arange(phx + px / 2, a.shape[1] - 1, px)
ys = np.arange(phy + py / 2, a.shape[0] - 1, py)
# average the central half of each block (robust to photo blur)
outa = np.zeros((len(ys), len(xs), 3))
for j, y in enumerate(ys):
    for i, x in enumerate(xs):
        blk = a[int(y - py / 4):int(y + py / 4) + 1, int(x - px / 4):int(x + px / 4) + 1]
        outa[j, i] = np.median(blk.reshape(-1, 3), axis=0)
Image.fromarray(outa.astype(np.uint8)).save(out)
print(f"period x={px} (phase {phx}), y={py} (phase {phy}) -> {len(xs)}x{len(ys)}")
