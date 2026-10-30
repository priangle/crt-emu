#!/usr/bin/env python3
"""Host test of the in-game panel (cnc-ddraw crt-emu build): draw it with the real ImGui/OpenGL
code over a shaded frame in a headless EGL context, with synthetic mouse input.

osd_test.py <libosd.so> <shader.glsl> <background.png> <out.png> [W H] [script...]
script items: move:x,y  down  up  wheel:n  frames:n  shot:path  save  set:NAME=v  show:0|1
"""
import ctypes as C
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glrun as G  # noqa: E402

WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEWHEEL = 0x200, 0x201, 0x202, 0x20A


def main(a):
    lib, shader, bg, out = a[0], a[1], a[2], a[3]
    W, H = (int(a[4]), int(a[5])) if len(a) > 5 and a[4].isdigit() else (2560, 1440)
    script = a[6:] if len(a) > 5 and a[4].isdigit() else a[4:]
    G.make_context(G.EGL_OPENGL_API, 3, 0, G.COMPAT_BIT)
    gl = G.GL()
    G.make_target(gl, W, H)
    img = Image.open(bg).convert("RGBA").resize((W, H))
    data = np.ascontiguousarray(np.asarray(img)[::-1])
    tex = C.c_int()
    gl.GetIntegerv = getattr(gl, "GetIntegerv", None)
    # fill the colour attachment with the background (texture bound by make_target)
    gl.TexSubImage2D(G.GL_TEXTURE_2D, 0, 0, 0, W, H, G.GL_RGBA, G.GL_UNSIGNED_BYTE, data.ctypes.data)

    osd = C.CDLL(lib)
    osd.crtemu_osd_load.argtypes = [C.c_char_p]
    osd.crtemu_osd_render.argtypes = [C.c_void_p, C.c_int, C.c_int]
    osd.crtemu_osd_test_input.argtypes = [C.c_uint, C.c_ulonglong, C.c_longlong]
    osd.crtemu_osd_test_set.argtypes = [C.c_char_p, C.c_float]
    osd.crtemu_osd_test_status.restype = C.c_char_p
    osd.crtemu_osd_param_count.restype = C.c_int
    osd.crtemu_osd_param_name.restype = C.c_char_p
    osd.crtemu_osd_param_value.restype = C.c_float
    osd.crtemu_osd_load(shader.encode())
    n = osd.crtemu_osd_param_count()
    print("params:", n, {osd.crtemu_osd_param_name(i).decode(): round(osd.crtemu_osd_param_value(i), 3) for i in range(n)})
    osd.crtemu_osd_test_show(1)

    def frame(k=1):
        for _ in range(k):
            gl.TexSubImage2D(G.GL_TEXTURE_2D, 0, 0, 0, W, H, G.GL_RGBA, G.GL_UNSIGNED_BYTE, data.ctypes.data)
            osd.crtemu_osd_render(None, W, H)
        err = gl.GetError()
        if err:
            print("GL error 0x%x" % err)

    def lp(x, y):
        return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

    x = y = 0
    frame(3)
    for item in script:
        if item.startswith("move:"):
            x, y = map(int, item[5:].split(",")); osd.crtemu_osd_test_input(WM_MOUSEMOVE, 0, lp(x, y)); frame(2)
        elif item == "down":
            osd.crtemu_osd_test_input(WM_LBUTTONDOWN, 1, lp(x, y)); frame(2)
        elif item == "up":
            osd.crtemu_osd_test_input(WM_LBUTTONUP, 0, lp(x, y)); frame(2)
        elif item.startswith("wheel:"):
            osd.crtemu_osd_test_input(WM_MOUSEWHEEL, (int(item[6:]) * 120 & 0xFFFF) << 16, lp(x, y)); frame(2)
        elif item.startswith("frames:"):
            frame(int(item[7:]))
        elif item.startswith("set:"):
            k, v = item[4:].split("="); osd.crtemu_osd_test_set(k.encode(), float(v)); frame(1)
        elif item == "save":
            print("save ->", osd.crtemu_osd_test_save(), osd.crtemu_osd_test_status().decode())
        elif item.startswith("show:"):
            osd.crtemu_osd_test_show(int(item[5:])); frame(1)
        elif item.startswith("shot:"):
            G.read_out(gl, W, H, item[5:])
    G.read_out(gl, W, H, out)
    print({osd.crtemu_osd_param_name(i).decode(): round(osd.crtemu_osd_param_value(i), 3) for i in range(n)})


if __name__ == "__main__":
    main(sys.argv[1:])
