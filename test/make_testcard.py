#!/usr/bin/env python3
"""Original 1280x720 pixel-art test card in the spirit of a 90s strategy game screen
(adventure map + side panel + calibration strip). Quantised to RGB565 like HoMM3."""
import math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def load_font(names, size):
    """First font found among names in the usual Linux / Windows / macOS font folders."""
    dirs = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF", os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts"),
            "/Library/Fonts", "/System/Library/Fonts/Supplemental"]
    for n in names:
        for d in dirs:
            path = os.path.join(d, n)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    return ImageFont.load_default()

W, H = 1280, 720
MAP_W = 1024
rnd = random.Random(7)
img = Image.new("RGB", (W, H), (0, 0, 0))
d = ImageDraw.Draw(img)

# ---------- adventure map ----------
grass = [(58, 92, 34), (66, 104, 38), (74, 112, 44), (52, 84, 30)]
for y in range(0, 560):
    for x in range(0, MAP_W):
        n = (x * 7 + y * 13 + (x * y) % 11) % 17
        img.putpixel((x, y), grass[(n + rnd.randint(0, 1)) % 4])

# river
for x in range(0, MAP_W):
    cy = 380 + 40 * math.sin(x / 90.0) + 12 * math.sin(x / 23.0)
    for dy in range(-22, 23):
        y = int(cy + dy)
        if 0 <= y < 560:
            edge = abs(dy) > 18
            ripple = (x + y * 3) % 23 < 2
            c = (40, 70, 140) if not edge else (90, 120, 70)
            if ripple and not edge:
                c = (120, 160, 220)
            img.putpixel((x, y), c)

# dirt road
for t in range(0, 900):
    x = int(60 + t * 1.0)
    y = int(120 + 60 * math.sin(t / 140.0) + t * 0.12)
    for dx in range(-6, 7):
        for dy in range(-5, 6):
            if dx * dx + dy * dy < 30 and 0 <= x + dx < MAP_W and 0 <= y + dy < 560:
                img.putpixel((x + dx, y + dy), (150, 116, 72) if (x + y + dx) % 9 else (128, 98, 60))

# mountains
for (mx, my, s) in [(760, 150, 90), (850, 190, 70), (680, 200, 60), (930, 120, 80)]:
    d.polygon([(mx - s, my + s // 2), (mx, my - s // 2), (mx + s, my + s // 2)], fill=(110, 104, 96), outline=(20, 18, 16))
    d.polygon([(mx, my - s // 2), (mx + s, my + s // 2), (mx + s // 5, my + s // 2)], fill=(80, 74, 68))
    d.polygon([(mx - s // 5, my - s // 4), (mx, my - s // 2), (mx + s // 5, my - s // 4)], fill=(235, 235, 240))

# trees
for _ in range(70):
    tx, ty = rnd.randint(10, MAP_W - 10), rnd.randint(10, 300)
    if 140 < ty < 240 and 600 < tx:
        continue
    d.rectangle([tx - 2, ty + 8, tx + 2, ty + 18], fill=(80, 50, 24), outline=(20, 12, 6))
    d.ellipse([tx - 12, ty - 14, tx + 12, ty + 12], fill=(30, 70, 26), outline=(8, 20, 8))
    d.ellipse([tx - 7, ty - 10, tx + 3, ty - 2], fill=(56, 108, 40))

# castle
cx, cy = 300, 470
d.rectangle([cx - 70, cy - 60, cx + 70, cy + 30], fill=(170, 160, 140), outline=(24, 20, 16))
for k in range(-70, 71, 20):
    d.rectangle([cx + k - 6, cy - 72, cx + k + 6, cy - 60], fill=(170, 160, 140), outline=(24, 20, 16))
for tx in (cx - 85, cx + 85):
    d.rectangle([tx - 18, cy - 110, tx + 18, cy + 30], fill=(150, 140, 122), outline=(24, 20, 16))
    d.polygon([(tx - 24, cy - 110), (tx, cy - 150), (tx + 24, cy - 110)], fill=(150, 40, 40), outline=(30, 8, 8))
d.rectangle([cx - 16, cy - 10, cx + 16, cy + 30], fill=(60, 36, 20), outline=(10, 6, 2))
for wx in (cx - 40, cx + 30):
    d.rectangle([wx, cy - 40, wx + 8, cy - 28], fill=(250, 220, 120))

# hero with flag
hx, hy = 560, 300
d.line([hx, hy - 40, hx, hy + 10], fill=(30, 20, 10), width=2)
d.polygon([(hx, hy - 40), (hx + 22, hy - 33), (hx, hy - 26)], fill=(220, 30, 30), outline=(60, 0, 0))
d.ellipse([hx - 14, hy - 6, hx + 14, hy + 18], fill=(120, 90, 60), outline=(20, 12, 6))
d.ellipse([hx - 6, hy - 22, hx + 6, hy - 8], fill=(230, 190, 150), outline=(40, 24, 10))
# treasure chest + gold pile
d.rectangle([420, 250, 446, 268], fill=(150, 90, 30), outline=(30, 16, 4))
d.rectangle([420, 256, 446, 259], fill=(230, 200, 60))
for k in range(9):
    gx, gy = 470 + (k % 3) * 6, 262 - (k // 3) * 4
    d.ellipse([gx, gy, gx + 6, gy + 4], fill=(250, 210, 40), outline=(120, 80, 0))

# ---------- side panel ----------
d.rectangle([MAP_W, 0, W - 1, 559], fill=(92, 64, 36))
d.rectangle([MAP_W + 4, 4, W - 5, 555], outline=(220, 180, 80), width=3)
mini = img.crop((0, 0, MAP_W, 560)).resize((224, 122), Image.NEAREST)
img.paste(mini, (MAP_W + 16, 16))
d.rectangle([MAP_W + 15, 15, MAP_W + 240, 138], outline=(250, 220, 120))
try:
    f_big = load_font(["DejaVuSerif-Bold.ttf", "georgiab.ttf", "timesbd.ttf"], 17)
    f_sm = load_font(["DejaVuSansCondensed.ttf", "arialn.ttf", "segoeui.ttf", "arial.ttf"], 13)
except OSError:
    f_big = f_sm = ImageFont.load_default()
d.text((MAP_W + 18, 152), "Неделя 2, день 5", font=f_big, fill=(250, 230, 160))
lines = [("Золото", "12 750", (250, 210, 40)), ("Древесина", "34", (170, 120, 70)),
         ("Руда", "21", (160, 160, 170)), ("Кристаллы", "7", (230, 60, 60)),
         ("Самоцветы", "5", (90, 220, 120)), ("Сера", "9", (240, 240, 80)),
         ("Ртуть", "3", (200, 200, 230))]
for i, (name, val, col) in enumerate(lines):
    y = 190 + i * 22
    d.rectangle([MAP_W + 18, y + 3, MAP_W + 28, y + 13], fill=col, outline=(0, 0, 0))
    d.text((MAP_W + 36, y), name, font=f_sm, fill=(235, 225, 200))
    d.text((W - 70, y), val, font=f_sm, fill=(255, 255, 255))
for i, label in enumerate(["Герой", "Город", "Ход"]):
    bx, by = MAP_W + 18 + i * 76, 360
    d.rectangle([bx, by, bx + 68, by + 34], fill=(60, 40, 20), outline=(230, 190, 90))
    d.text((bx + 10, by + 9), label, font=f_sm, fill=(255, 240, 200))
d.text((MAP_W + 18, 420), "Скорость 7  Мана 24/30", font=f_sm, fill=(200, 200, 255))

# ---------- calibration strip ----------
y0 = 560
bars = [(191, 191, 191), (191, 191, 0), (0, 191, 191), (0, 191, 0), (191, 0, 191), (191, 0, 0), (0, 0, 191)]
bw = 640 // len(bars)
for i, c in enumerate(bars):
    d.rectangle([i * bw, y0, (i + 1) * bw - 1, y0 + 59], fill=c)
for i in range(16):
    v = int(i * 255 / 15)
    d.rectangle([i * 40, y0 + 60, i * 40 + 39, y0 + 99], fill=(v, v, v))
for x in range(640, 800):
    for y in range(y0, y0 + 80):
        img.putpixel((x, y), (255, 255, 255) if x % 2 == 0 else (0, 0, 0))
for x in range(800, 960):
    for y in range(y0, y0 + 80):
        img.putpixel((x, y), (255, 255, 255) if y % 2 == 0 else (0, 0, 0))
for x in range(960, 1120):
    for y in range(y0, y0 + 80):
        img.putpixel((x, y), (255, 255, 255) if (x + y) % 2 == 0 else (0, 0, 0))
d.rectangle([1120, y0, W - 1, y0 + 80], fill=(0, 0, 0))
for k in range(12):
    px, py = 1130 + (k % 6) * 24, y0 + 16 + (k // 6) * 40
    img.putpixel((px, py), (255, 255, 255))
    d.rectangle([px + 8, py, px + 9, py + 1], fill=(255, 255, 255))
d.rectangle([640, y0 + 80, W - 1, H - 1], fill=(8, 8, 12))
d.text((650, y0 + 92), "crt-emu test: 1px lines | checker | dots | Пиксели ЭЛТ", font=f_sm, fill=(255, 255, 255))
d.text((650, y0 + 114), "Мелкий текст на тёмном фоне — проверка читаемости", font=f_sm, fill=(255, 210, 90))
d.rectangle([0, y0 + 100, 639, H - 1], fill=(0, 0, 0))
for x in range(640):
    v = x / 639.0
    d.line([x, y0 + 104, x, y0 + 124], fill=(int(255 * v), 0, 0))
    d.line([x, y0 + 126, x, y0 + 144], fill=(0, int(255 * v), 0))
    d.line([x, y0 + 146, x, y0 + 159], fill=(0, 0, int(255 * v)))

# ---------- RGB565 quantisation ----------
a = np.asarray(img).astype(np.int32)
r = (a[..., 0] >> 3) << 3; g = (a[..., 1] >> 2) << 2; b = (a[..., 2] >> 3) << 3
r |= r >> 5; g |= g >> 6; b |= b >> 5
Image.fromarray(np.stack([r, g, b], -1).astype(np.uint8)).save(sys.argv[1] if len(sys.argv) > 1 else "testcard.png")
print("ok")
