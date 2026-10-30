import sys
from PIL import Image
src, out, x, y, w, h, z = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:8])
im = Image.open(src).crop((x, y, x + w, y + h))
im.resize((w * z, h * z), Image.NEAREST).save(out)
