#!/usr/bin/env python3
"""Headless shader test harness, plain ctypes: WGL on Windows (hidden window, the video card's
own driver - the one the game uses), Mesa llvmpipe via EGL (surfaceless) elsewhere.

  glrun.py ddraw  <shader.glsl> <in.png> <out.png> <outW> <outH> [--uniform [set:NAME=v ...]] [--core] [--frame N]
      Builds the program exactly like cnc-ddraw's oglu_build_program_from_file()
      and sets the same attributes/uniforms (VertexCoord, TexCoord, MVPMatrix,
      InputSize, TextureSize, OutputSize, Texture, FrameCount).
  glrun.py modes  <shader.glsl> <outdir> <outW> <outH> <in.png> [in.png ...] [--tol N] [set:NAME=v ...]
      Renders every frame three ways - #define values, --uniform, --uniform --core - one
      process each, saves <outdir>/<frame>-define|uniform|core.png and checks that uniform and
      core match define within N per channel (default 1); exit code 1 if not. Frame arguments
      may be glob patterns. set: items go to the uniform runs only (a deliberate mismatch).
  glrun.py slangcheck <shader.slang>
      Compiles both slang stages in a GL 4.5 context (push constants mapped to a
      plain uniform block) - a syntax/semantics check of the slang wrapper + core.
"""
import ctypes as C
import glob, json, os, subprocess, sys, time
import numpy as np
from PIL import Image

EGL_OPENGL_API, EGL_OPENGL_ES_API = 0x30A2, 0x30A0
CORE_BIT, COMPAT_BIT = 1, 2

if sys.platform == "win32":
    # WGL the way cnc-ddraw sets it up: pixel format as in dd.c, a plain wglCreateContext context
    # (what the game renders with: opengl_core is unset), upgraded to a forward-compatible core
    # context only for --core (ogl_create_core_context in render_ogl.c).
    FUNCTYPE = C.WINFUNCTYPE
    gl32 = C.WinDLL("opengl32")
    gdi32, user32, kernel32 = C.WinDLL("gdi32"), C.WinDLL("user32"), C.WinDLL("kernel32")
    gl32.wglCreateContext.restype = C.c_void_p
    gl32.wglCreateContext.argtypes = [C.c_void_p]
    gl32.wglMakeCurrent.argtypes = [C.c_void_p, C.c_void_p]
    gl32.wglDeleteContext.argtypes = [C.c_void_p]
    gl32.wglGetProcAddress.restype = C.c_void_p
    gl32.wglGetProcAddress.argtypes = [C.c_char_p]
    kernel32.GetModuleHandleW.restype = C.c_void_p
    kernel32.GetModuleHandleW.argtypes = [C.c_wchar_p]
    kernel32.GetProcAddress.restype = C.c_void_p
    kernel32.GetProcAddress.argtypes = [C.c_void_p, C.c_char_p]
    user32.CreateWindowExW.restype = C.c_void_p
    user32.CreateWindowExW.argtypes = [C.c_uint, C.c_wchar_p, C.c_wchar_p, C.c_uint, C.c_int, C.c_int, C.c_int, C.c_int,
                                       C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
    user32.GetDC.restype = C.c_void_p
    user32.GetDC.argtypes = [C.c_void_p]
    gdi32.ChoosePixelFormat.argtypes = [C.c_void_p, C.c_void_p]
    gdi32.SetPixelFormat.argtypes = [C.c_void_p, C.c_int, C.c_void_p]

    class WNDCLASSW(C.Structure):
        _fields_ = [("style", C.c_uint), ("lpfnWndProc", C.c_void_p), ("cbClsExtra", C.c_int), ("cbWndExtra", C.c_int),
                    ("hInstance", C.c_void_p), ("hIcon", C.c_void_p), ("hCursor", C.c_void_p), ("hbrBackground", C.c_void_p),
                    ("lpszMenuName", C.c_wchar_p), ("lpszClassName", C.c_wchar_p)]

    class PIXELFORMATDESCRIPTOR(C.Structure):
        _fields_ = [("nSize", C.c_ushort), ("nVersion", C.c_ushort), ("dwFlags", C.c_uint)] + \
                   [(f, C.c_ubyte) for f in ("iPixelType", "cColorBits", "cRedBits", "cRedShift", "cGreenBits", "cGreenShift",
                                             "cBlueBits", "cBlueShift", "cAlphaBits", "cAlphaShift", "cAccumBits", "cAccumRedBits",
                                             "cAccumGreenBits", "cAccumBlueBits", "cAccumAlphaBits", "cDepthBits", "cStencilBits",
                                             "cAuxBuffers", "iLayerType", "bReserved")] + \
                   [("dwLayerMask", C.c_uint), ("dwVisibleMask", C.c_uint), ("dwDamageMask", C.c_uint)]

    CS_OWNDC, WS_POPUP = 0x0020, 0x80000000
    PFD_DOUBLEBUFFER, PFD_DRAW_TO_WINDOW, PFD_SUPPORT_OPENGL = 0x01, 0x04, 0x20
    WGL_CONTEXT_MAJOR_VERSION_ARB, WGL_CONTEXT_MINOR_VERSION_ARB = 0x2091, 0x2092
    WGL_CONTEXT_FLAGS_ARB, WGL_CONTEXT_PROFILE_MASK_ARB = 0x2094, 0x9126
    WGL_CONTEXT_FORWARD_COMPATIBLE_BIT_ARB = 0x0002

    def get_proc_address(name):
        addr = gl32.wglGetProcAddress(name.encode())
        if addr in (None, 1, 2, 3, C.c_void_p(-1).value):   # GL 1.1 entry points live in opengl32.dll itself
            addr = kernel32.GetProcAddress(gl32._handle, name.encode())
        return addr

    def make_context(api, major, minor, profile=None):
        """Compat: the requested version is ignored, like the game (plain wglCreateContext)."""
        assert api == EGL_OPENGL_API, "WGL: desktop OpenGL only"
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW(style=CS_OWNDC, lpfnWndProc=C.cast(user32.DefWindowProcW, C.c_void_p).value,
                       hInstance=hinst, lpszClassName="glrun")
        user32.RegisterClassW(C.byref(wc))
        hwnd = user32.CreateWindowExW(0, "glrun", "glrun", WS_POPUP, 0, 0, 16, 16, None, None, hinst, None)
        assert hwnd, "CreateWindowExW failed"
        hdc = user32.GetDC(hwnd)
        pfd = PIXELFORMATDESCRIPTOR(nSize=C.sizeof(PIXELFORMATDESCRIPTOR), nVersion=1, cColorBits=32,
                                    dwFlags=PFD_DRAW_TO_WINDOW | PFD_DOUBLEBUFFER | PFD_SUPPORT_OPENGL)
        ok = gdi32.SetPixelFormat(hdc, gdi32.ChoosePixelFormat(hdc, C.byref(pfd)), C.byref(pfd))
        assert ok, "SetPixelFormat failed"
        ctx = gl32.wglCreateContext(hdc)
        ok = ctx and gl32.wglMakeCurrent(hdc, ctx)
        assert ok, "wglCreateContext failed"
        if profile != CORE_BIT:
            return
        addr = get_proc_address("wglCreateContextAttribsARB")
        assert addr, "no wglCreateContextAttribsARB"
        create = FUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_int))(addr)
        ca = [WGL_CONTEXT_MAJOR_VERSION_ARB, major, WGL_CONTEXT_MINOR_VERSION_ARB, minor,
              WGL_CONTEXT_FLAGS_ARB, WGL_CONTEXT_FORWARD_COMPATIBLE_BIT_ARB, WGL_CONTEXT_PROFILE_MASK_ARB, CORE_BIT, 0]
        core = create(hdc, None, (C.c_int * len(ca))(*ca))
        ok = core and gl32.wglMakeCurrent(hdc, core)
        assert ok, "wglCreateContextAttribsARB failed"
        gl32.wglDeleteContext(ctx)
else:
    FUNCTYPE = C.CFUNCTYPE
    egl = C.CDLL("libEGL.so.1")
    egl.eglGetProcAddress.restype = C.c_void_p
    egl.eglGetProcAddress.argtypes = [C.c_char_p]
    egl.eglGetDisplay.restype = C.c_void_p
    egl.eglInitialize.argtypes = [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int)]
    egl.eglBindAPI.argtypes = [C.c_uint]
    egl.eglChooseConfig.argtypes = [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_void_p), C.c_int, C.POINTER(C.c_int)]
    egl.eglCreateContext.restype = C.c_void_p
    egl.eglCreateContext.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_int)]
    egl.eglMakeCurrent.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
    egl.eglGetError.restype = C.c_int

    EGL_PLATFORM_SURFACELESS_MESA = 0x31DD
    EGL_RENDERABLE_TYPE, EGL_NONE = 0x3040, 0x3038
    EGL_OPENGL_BIT, EGL_OPENGL_ES3_BIT = 0x0008, 0x0040
    EGL_CONTEXT_MAJOR_VERSION, EGL_CONTEXT_MINOR_VERSION = 0x3098, 0x30FB
    EGL_CONTEXT_OPENGL_PROFILE_MASK = 0x30FD

    def get_proc_address(name):
        return egl.eglGetProcAddress(name.encode())

    def make_context(api, major, minor, profile=None):
        getdpy = C.CFUNCTYPE(C.c_void_p, C.c_uint, C.c_void_p, C.POINTER(C.c_int))(
            egl.eglGetProcAddress(b"eglGetPlatformDisplayEXT"))
        dpy = getdpy(EGL_PLATFORM_SURFACELESS_MESA, None, None)
        a, b = C.c_int(), C.c_int()
        assert egl.eglInitialize(dpy, C.byref(a), C.byref(b)), "eglInitialize failed"
        assert egl.eglBindAPI(api)
        bit = EGL_OPENGL_BIT if api == EGL_OPENGL_API else EGL_OPENGL_ES3_BIT
        attrs = (C.c_int * 5)(EGL_RENDERABLE_TYPE, bit, 0x3033, 0x0001, EGL_NONE)  # SURFACE_TYPE=PBUFFER
        cfg, n = C.c_void_p(), C.c_int()
        assert egl.eglChooseConfig(dpy, attrs, C.byref(cfg), 1, C.byref(n)) and n.value > 0, "no EGL config"
        ca = [EGL_CONTEXT_MAJOR_VERSION, major, EGL_CONTEXT_MINOR_VERSION, minor]
        if profile:
            ca += [EGL_CONTEXT_OPENGL_PROFILE_MASK, profile]
        ca += [EGL_NONE]
        ctx = egl.eglCreateContext(dpy, cfg, None, (C.c_int * len(ca))(*ca))
        assert ctx, "eglCreateContext failed 0x%x" % egl.eglGetError()
        assert egl.eglMakeCurrent(dpy, None, None, ctx), "eglMakeCurrent failed"


class GL:
    SIGS = {
        "glGetString": (C.c_char_p, [C.c_uint]),
        "glCreateShader": (C.c_uint, [C.c_uint]),
        "glShaderSource": (None, [C.c_uint, C.c_int, C.POINTER(C.c_char_p), C.c_void_p]),
        "glCompileShader": (None, [C.c_uint]),
        "glGetShaderiv": (None, [C.c_uint, C.c_uint, C.POINTER(C.c_int)]),
        "glGetShaderInfoLog": (None, [C.c_uint, C.c_int, C.c_void_p, C.c_char_p]),
        "glCreateProgram": (C.c_uint, []),
        "glAttachShader": (None, [C.c_uint, C.c_uint]),
        "glLinkProgram": (None, [C.c_uint]),
        "glGetProgramiv": (None, [C.c_uint, C.c_uint, C.POINTER(C.c_int)]),
        "glGetProgramInfoLog": (None, [C.c_uint, C.c_int, C.c_void_p, C.c_char_p]),
        "glUseProgram": (None, [C.c_uint]),
        "glGetUniformLocation": (C.c_int, [C.c_uint, C.c_char_p]),
        "glGetAttribLocation": (C.c_int, [C.c_uint, C.c_char_p]),
        "glUniform1f": (None, [C.c_int, C.c_float]),
        "glUniform1i": (None, [C.c_int, C.c_int]),
        "glUniform2f": (None, [C.c_int, C.c_float, C.c_float]),
        "glUniformMatrix4fv": (None, [C.c_int, C.c_int, C.c_ubyte, C.POINTER(C.c_float)]),
        "glGenTextures": (None, [C.c_int, C.POINTER(C.c_uint)]),
        "glBindTexture": (None, [C.c_uint, C.c_uint]),
        "glTexImage2D": (None, [C.c_uint, C.c_int, C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_void_p]),
        "glTexSubImage2D": (None, [C.c_uint, C.c_int, C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_void_p]),
        "glTexParameteri": (None, [C.c_uint, C.c_uint, C.c_int]),
        "glGenFramebuffers": (None, [C.c_int, C.POINTER(C.c_uint)]),
        "glBindFramebuffer": (None, [C.c_uint, C.c_uint]),
        "glFramebufferTexture2D": (None, [C.c_uint, C.c_uint, C.c_uint, C.c_uint, C.c_int]),
        "glCheckFramebufferStatus": (C.c_uint, [C.c_uint]),
        "glViewport": (None, [C.c_int, C.c_int, C.c_int, C.c_int]),
        "glGenBuffers": (None, [C.c_int, C.POINTER(C.c_uint)]),
        "glBindBuffer": (None, [C.c_uint, C.c_uint]),
        "glBufferData": (None, [C.c_uint, C.c_ssize_t, C.c_void_p, C.c_uint]),
        "glGenVertexArrays": (None, [C.c_int, C.POINTER(C.c_uint)]),
        "glBindVertexArray": (None, [C.c_uint]),
        "glVertexAttribPointer": (None, [C.c_uint, C.c_int, C.c_uint, C.c_ubyte, C.c_int, C.c_void_p]),
        "glEnableVertexAttribArray": (None, [C.c_uint]),
        "glDrawArrays": (None, [C.c_uint, C.c_int, C.c_int]),
        "glReadPixels": (None, [C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_void_p]),
        "glPixelStorei": (None, [C.c_uint, C.c_int]),
        "glFinish": (None, []),
        "glGetError": (C.c_uint, []),
        "glActiveTexture": (None, [C.c_uint]),
    }

    def __init__(self):
        for name, (res, args) in self.SIGS.items():
            addr = get_proc_address(name)
            assert addr, name
            setattr(self, name[2:], FUNCTYPE(res, *args)(addr))


GL_VERTEX_SHADER, GL_FRAGMENT_SHADER = 0x8B31, 0x8B30
GL_COMPILE_STATUS, GL_LINK_STATUS = 0x8B81, 0x8B82
GL_TEXTURE_2D, GL_RGBA, GL_RGBA8, GL_UNSIGNED_BYTE = 0x0DE1, 0x1908, 0x8058, 0x1401
GL_NEAREST, GL_MIN, GL_MAG = 0x2600, 0x2801, 0x2800
GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 = 0x8D40, 0x8CE0
GL_ARRAY_BUFFER, GL_STATIC_DRAW, GL_FLOAT, GL_TRIANGLE_FAN = 0x8892, 0x88E4, 0x1406, 0x0006


def compile_program(gl, vs, fs, label=""):
    def sh(kind, src):
        s = gl.CreateShader(kind)
        arr = (C.c_char_p * 1)(src.encode())
        gl.ShaderSource(s, 1, arr, None)
        gl.CompileShader(s)
        ok = C.c_int()
        gl.GetShaderiv(s, GL_COMPILE_STATUS, C.byref(ok))
        log = C.create_string_buffer(65536)
        gl.GetShaderInfoLog(s, 65536, None, log)
        if log.value.strip():
            print(f"[{label} {'VS' if kind == GL_VERTEX_SHADER else 'FS'} log]\n" + log.value.decode())
        if not ok.value:
            raise SystemExit(f"{label}: shader compile FAILED")
        return s
    p = gl.CreateProgram()
    gl.AttachShader(p, sh(GL_VERTEX_SHADER, vs))
    gl.AttachShader(p, sh(GL_FRAGMENT_SHADER, fs))
    gl.LinkProgram(p)
    ok = C.c_int()
    gl.GetProgramiv(p, GL_LINK_STATUS, C.byref(ok))
    if not ok.value:
        log = C.create_string_buffer(65536)
        gl.GetProgramInfoLog(p, 65536, None, log)
        raise SystemExit(f"{label}: link FAILED\n{log.value.decode()}")
    print(f"{label}: compiled + linked OK")
    return p


def ddraw_split(source, core_profile):
    """Mirror of cnc-ddraw oglu_build_program_from_file()."""
    i = source.find("#version")
    if i < 0:
        hdr = "#version 150\n" if core_profile else "#version 130\n"
        return hdr + "#define VERTEX\n" + source, hdr + "#define FRAGMENT\n" + source
    if core_profile and source[i:i + 12] in ("#version 130", "#version 140"):
        source = source[:i] + "#version 150" + source[i + 12:]
    j = source.find("\n", i)
    head, rest = source[:j], source[j + 1:]
    extra = "#define PARAMETER_UNIFORM\n" if UNIFORM_VALUES else ""
    return head + "\n#define VERTEX\n" + extra + rest, head + "\n#define FRAGMENT\n" + extra + rest


# --uniform: emulate the crt-emu cnc-ddraw build (parameters as uniforms, values set by the host)
UNIFORM_VALUES = {}


def parse_defines(source):
    import re
    return {m.group(1): float(m.group(2)) for m in re.finditer(r"^#define (\w+)\s+(-?\d+(?:\.\d+)?)\s*//", source, re.M)}


def upload_texture(gl, img, tw, th):
    w, h = img.size
    tex = C.c_uint()
    gl.GenTextures(1, C.byref(tex))
    gl.BindTexture(GL_TEXTURE_2D, tex.value)
    gl.TexParameteri(GL_TEXTURE_2D, GL_MIN, GL_NEAREST)
    gl.TexParameteri(GL_TEXTURE_2D, GL_MAG, GL_NEAREST)
    # garbage-red padding so edge clamping bugs would be visible
    pad = np.zeros((th, tw, 4), np.uint8); pad[..., 0] = 255; pad[..., 3] = 255
    gl.PixelStorei(0x0CF5, 1)
    gl.TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, tw, th, 0, GL_RGBA, GL_UNSIGNED_BYTE, pad.ctypes.data)
    data = np.ascontiguousarray(np.asarray(img.convert("RGBA")))
    gl.TexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, data.ctypes.data)
    return tex.value


def make_target(gl, ow, oh):
    tex, fbo = C.c_uint(), C.c_uint()
    gl.GenTextures(1, C.byref(tex)); gl.BindTexture(GL_TEXTURE_2D, tex.value)
    gl.TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, ow, oh, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
    gl.GenFramebuffers(1, C.byref(fbo)); gl.BindFramebuffer(GL_FRAMEBUFFER, fbo.value)
    gl.FramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex.value, 0)
    assert gl.CheckFramebufferStatus(GL_FRAMEBUFFER) == 0x8CD5, "FBO incomplete"
    gl.Viewport(0, 0, ow, oh)


def quad(gl, prog, attrs):
    vao = C.c_uint(); gl.GenVertexArrays(1, C.byref(vao)); gl.BindVertexArray(vao.value)
    for name, data in attrs.items():
        loc = gl.GetAttribLocation(prog, name.encode())
        if loc < 0:
            continue
        arr = (C.c_float * len(data))(*data)
        b = C.c_uint(); gl.GenBuffers(1, C.byref(b)); gl.BindBuffer(GL_ARRAY_BUFFER, b.value)
        gl.BufferData(GL_ARRAY_BUFFER, C.sizeof(arr), arr, GL_STATIC_DRAW)
        gl.VertexAttribPointer(loc, 2, GL_FLOAT, 0, 0, None)
        gl.EnableVertexAttribArray(loc)


def read_out(gl, ow, oh, path):
    buf = np.empty((oh, ow, 4), np.uint8)
    gl.PixelStorei(0x0D05, 1)
    gl.ReadPixels(0, 0, ow, oh, GL_RGBA, GL_UNSIGNED_BYTE, buf.ctypes.data)
    Image.fromarray(buf[::-1, :, :3]).save(path)
    print("saved", path, f"{ow}x{oh}")


def pow2_tex(w, h, ow, oh, two_pass):
    """cnc-ddraw ogl_create_textures(): surface/FBO texture size."""
    if two_pass:
        w, h = max(w, ow), max(h, oh)
    tw = 1024 if w <= 1024 else 2048 if w <= 2048 else 4096 if w <= 4096 else 8192 if w <= 8192 else w
    th = 512 if h <= 512 else 1024 if h <= 1024 else 2048 if h <= 2048 else 4096 if h <= 4096 else 8192 if h <= 8192 else h
    return tw, th


def set_common(gl, prog, ow, oh, tw, th, iw, ih, frame=1):
    loc = gl.GetUniformLocation
    gl.Uniform2f(loc(prog, b"OutputSize"), ow, oh)
    gl.Uniform2f(loc(prog, b"TextureSize"), tw, th)
    gl.Uniform2f(loc(prog, b"InputSize"), iw, ih)
    gl.Uniform1i(loc(prog, b"Texture"), 0)
    gl.Uniform1i(loc(prog, b"PassPrev2Texture"), 1)
    gl.Uniform1i(loc(prog, b"FrameCount"), frame)
    ident = (C.c_float * 16)(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    gl.UniformMatrix4fv(loc(prog, b"MVPMatrix"), 1, 0, ident)
    for k, v in UNIFORM_VALUES.items():
        gl.Uniform1f(loc(prog, k.encode()), v)


def run_ddraw(args):
    """ddraw <shader.glsl> <in.png> <out.png> <outW> <outH> [--core] [--frame N]
    Single pass, or the two-pass '-pass1scale' path when <shader>.pass1 exists."""
    shader, inp, out, ow, oh = args[0], args[1], args[2], int(args[3]), int(args[4])
    core = "--core" in args
    if "--uniform" in args:
        import os as _os
        src2 = shader + ".pass1" if _os.path.exists(shader + ".pass1") else shader
        UNIFORM_VALUES.update(parse_defines(open(src2, encoding="utf-8").read()))
        for a in args:
            if a.startswith("set:"):
                k, v = a[4:].split("="); UNIFORM_VALUES[k] = float(v)
        print("uniform mode:", len(UNIFORM_VALUES), "parameters")
    frame = int(args[args.index("--frame") + 1]) if "--frame" in args else 1
    import os
    two = os.path.exists(shader + ".pass1")
    upscale = two and "-pass1scale" in shader
    img = Image.open(inp).convert("RGB")
    w, h = img.size
    tw, th = pow2_tex(w, h, ow, oh, two)
    make_context(EGL_OPENGL_API, 3, 2 if core else 0, CORE_BIT if core else COMPAT_BIT)   # core 3.2, as cnc-ddraw
    gl = GL()
    print("GL:", gl.GetString(0x1F02).decode(), "|", gl.GetString(0x1F01).decode(),
          f"| tex {tw}x{th} | {'two-pass' if two else 'single pass'}")
    label = "core 150" if core else "compat 130"
    vs, fs = ddraw_split(open(shader, encoding="utf-8").read(), core)
    p1 = compile_program(gl, vs, fs, f"pass1 {os.path.basename(shader)} ({label})")
    fbo0 = upload_texture(gl, img, tw, th)          # FBO0: game frame copy, row 0 = top
    sw, sh_ = w / tw, h / th
    t = time.time()
    if two:
        vs2, fs2 = ddraw_split(open(shader + ".pass1", encoding="utf-8").read(), core)
        p2 = compile_program(gl, vs2, fs2, f"pass2 {os.path.basename(shader)}.pass1 ({label})")
        # pass 1 -> FBO1 (tex size), viewport = game size in upscale mode
        fbo1 = C.c_uint(); fb = C.c_uint()
        gl.GenTextures(1, C.byref(fbo1)); gl.BindTexture(GL_TEXTURE_2D, fbo1.value)
        gl.TexParameteri(GL_TEXTURE_2D, GL_MIN, GL_NEAREST); gl.TexParameteri(GL_TEXTURE_2D, GL_MAG, GL_NEAREST)
        gl.TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, tw, th, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        gl.GenFramebuffers(1, C.byref(fb)); gl.BindFramebuffer(GL_FRAMEBUFFER, fb.value)
        gl.FramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fbo1.value, 0)
        assert gl.CheckFramebufferStatus(GL_FRAMEBUFFER) == 0x8CD5
        if upscale:
            gl.Viewport(0, 0, w, h)
        else:
            gl.Viewport(0, 0, ow, oh)
        gl.UseProgram(p1)
        quad(gl, p1, {"VertexCoord": [-1, -1, -1, 1, 1, 1, 1, -1],
                      "TexCoord": [0, 0, 0, sh_, sw, sh_, sw, 0]})
        set_common(gl, p1, ow, oh, tw, th, w, h, frame)
        gl.ActiveTexture(0x84C0); gl.BindTexture(GL_TEXTURE_2D, fbo0)
        gl.DrawArrays(GL_TRIANGLE_FAN, 0, 4)
        # pass 2 -> output
        make_target(gl, ow, oh)
        gl.UseProgram(p2)
        s2w, s2h = (sw, sh_) if upscale else (ow / tw, oh / th)
        quad(gl, p2, {"VertexCoord": [-1, 1, 1, 1, 1, -1, -1, -1],
                      "TexCoord": [0, 0, s2w, 0, s2w, s2h, 0, s2h]})
        set_common(gl, p2, ow, oh, tw, th, w if upscale else ow, h if upscale else oh, frame)
        gl.ActiveTexture(0x84C0); gl.BindTexture(GL_TEXTURE_2D, fbo1.value)
        gl.ActiveTexture(0x84C1); gl.BindTexture(GL_TEXTURE_2D, fbo0)
        gl.ActiveTexture(0x84C0)
        gl.DrawArrays(GL_TRIANGLE_FAN, 0, 4); gl.Finish()
    else:
        make_target(gl, ow, oh)
        gl.UseProgram(p1)
        quad(gl, p1, {"VertexCoord": [-1, 1, 1, 1, 1, -1, -1, -1],
                      "TexCoord": [0, 0, sw, 0, sw, sh_, 0, sh_]})
        set_common(gl, p1, ow, oh, tw, th, w, h, frame)
        gl.ActiveTexture(0x84C0); gl.BindTexture(GL_TEXTURE_2D, fbo0)
        gl.DrawArrays(GL_TRIANGLE_FAN, 0, 4); gl.Finish()
    err = gl.GetError()
    print(f"draw {time.time() - t:.2f}s, glError=0x{err:x}")
    read_out(gl, ow, oh, out)
    if err:
        raise SystemExit(f"GL error 0x{err:x}")


def run_modes(args):
    """modes <shader.glsl> <outdir> <outW> <outH> <in.png> [in.png ...] [--tol N] [set:NAME=v ...]"""
    sys.stdout.reconfigure(errors="replace")   # frame names may not fit a piped console's code page
    tol = int(args[args.index("--tol") + 1]) if "--tol" in args else 1
    sets = [a for a in args if a.startswith("set:")]
    pos = [a for i, a in enumerate(args) if not a.startswith(("set:", "--")) and (i == 0 or args[i - 1] != "--tol")]
    shader, outdir, ow, oh = pos[:4]
    frames = [f for a in pos[4:] for f in (sorted(glob.glob(a)) or [a])]   # PowerShell does not expand globs
    os.makedirs(outdir, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    bad = 0
    for frame in frames:
        stem = os.path.splitext(os.path.basename(frame))[0]
        imgs = {}
        for mode, flags in (("define", []), ("uniform", ["--uniform"] + sets), ("core", ["--uniform", "--core"] + sets)):
            out = os.path.join(outdir, f"{stem}-{mode}.png")
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "ddraw", shader, frame, out, ow, oh] + flags,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
            log = (r.stdout + r.stderr).rstrip()
            if r.returncode:
                print(f"{stem}: {mode}: FAILED\n{log}")
                bad += 1
                break
            # exit code 0 = both passes compiled and linked, glError=0
            gl_line = next((l for l in log.splitlines() if l.startswith("GL:")), "").split(" | tex")[0]
            print(f"{stem}: {mode}: ok, {gl_line}")
            imgs[mode] = np.asarray(Image.open(out).convert("RGB"), np.int16)
        for mode in ("uniform", "core"):
            if mode in imgs:
                d = np.abs(imgs[mode] - imgs["define"]).max(axis=2)
                over = int((d > tol).sum())
                print(f"{stem}: {mode} vs define: max diff {int(d.max())}, pixels differing {int((d > 0).sum())},"
                      f" over ±{tol}: {over} of {d.size}")
                bad += over > 0
    bad += not frames
    print(f"modes: {len(frames)} frame(s),", "OK" if not bad else f"FAILED ({bad})")
    sys.exit(1 if bad else 0)


def run_slangcheck(args):
    src = open(args[0], encoding="utf-8").read()
    src = src.replace("layout(push_constant) uniform Push", "layout(std140, binding = 1) uniform Push").replace("set = 0, ", "")
    pre, rest = src.split("#pragma stage vertex", 1)
    vert, frag = rest.split("#pragma stage fragment", 1)
    pre = "\n".join(l for l in pre.splitlines() if not l.startswith("#pragma parameter"))
    make_context(EGL_OPENGL_API, 4, 5, CORE_BIT)
    gl = GL()
    print("GL:", gl.GetString(0x1F02).decode(), "|", gl.GetString(0x1F01).decode())
    compile_program(gl, pre + vert, pre + frag, "slang stages (GL 4.5 check)")


if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    {"ddraw": run_ddraw, "modes": run_modes, "slangcheck": run_slangcheck}[mode](rest)
