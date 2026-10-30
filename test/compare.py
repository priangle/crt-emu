"""Side-by-side: source (nearest) | our render | reference photo crop, all scaled to the same height."""
import sys
from PIL import Image
src, ours, ref, out = sys.argv[1:5]
box = tuple(map(int, sys.argv[5:9]))
H = 520
def fit(im, nearest=False):
    return im.resize((round(im.width * H / im.height), H), Image.NEAREST if nearest else Image.LANCZOS)
a = fit(Image.open(src).convert("RGB"), True)
b = fit(Image.open(ours).convert("RGB"))
c = fit(Image.open(ref).convert("RGB").crop(box))
W = a.width + b.width + c.width + 40
canvas = Image.new("RGB", (W, H), (0, 0, 0))
x = 0
for im in (a, b, c):
    canvas.paste(im, (x, 0)); x += im.width + 20
canvas.save(out)
