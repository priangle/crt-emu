#!/usr/bin/env python3
"""F12 panel outside the game, without GL: which "//@lang" block it reads and which language its
own buttons speak, for lang= in install.ini, the game's language (HD mod profile) and the EN/RU
buttons of the panel.

    python test/osd_meta_test.py <work dir outside the repo> [shader .pass1] [old .pass1]

Builds test/osd_meta_test.c with the panel (crtemu_osd.cpp + Dear ImGui) of third_party/cnc-ddraw:
i686 llvm-mingw on Windows (on PATH or in CRTEMU_MINGW_BIN), $CC / $CXX (clang) elsewhere.
The shader defaults to out/cnc-ddraw/Shaders/crt-emu/crt-emu-pass1scale.glsl.pass1 (python build.py).
An old .pass1 (no "//@lang", e.g. a copy from a game installed before the blocks) must keep its
Russian texts, with the buttons in the panel's language.
Each case is a little game folder: Shaders/crt-emu/ with the shader and install.ini, and
_HD3_Data/Settings/hota.ini with the game's language. With neither, the panel takes the Windows
display language (English elsewhere); the expected results follow this machine's.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FORK = os.path.join(ROOT, "third_party", "cnc-ddraw")
sys.path.insert(0, ROOT)
import build  # noqa: E402  (panel texts per language: build.LANGS)

SOURCES = ["src/imgui/imgui.cpp", "src/imgui/imgui_draw.cpp", "src/imgui/imgui_tables.cpp",
           "src/imgui/imgui_widgets.cpp", "src/imgui/backends/imgui_impl_opengl3.cpp", "src/crtemu/crtemu_osd.cpp"]
CXXFLAGS = ["-std=c++11", "-O1", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
            "-DIMGUI_DISABLE_DEMO_WINDOWS", "-DCRTEMU_OSD_TEST",
            "-I", os.path.join(FORK, "src", "imgui"), "-I", os.path.join(FORK, "inc")]
UI_SAVE = {"en": "Save", "ru": "Сохранить"}   # the panel's own strings: one sample per language
UI_TITLE = {"en": "CRT tube", "ru": "кинескоп"}


def toolchain():
    if os.name == "nt":
        b = os.environ.get("CRTEMU_MINGW_BIN", "")
        tool = lambda n: os.path.join(b, n) if b else n
        return tool("i686-w64-mingw32-clang"), tool("i686-w64-mingw32-clang++"), ["-static", "-lgdi32", "-luser32"]
    return os.environ.get("CC", "clang"), os.environ.get("CXX", "clang++"), ["-ldl"]


def build_driver(work):
    cc, cxx, libs = toolchain()
    obj = os.path.join(work, "osd_meta_test.o")
    exe = os.path.join(work, "osd_meta_test.exe" if os.name == "nt" else "osd_meta_test")
    subprocess.run([cc, "-O1", "-Wall", "-c", os.path.join(HERE, "osd_meta_test.c"), "-o", obj], check=True)
    subprocess.run([cxx, *CXXFLAGS, *[os.path.join(FORK, s) for s in SOURCES], obj, *libs, "-o", exe], check=True)
    return exe


def system_lang():
    """what the panel falls back to: the Windows display language, English elsewhere"""
    if os.name != "nt":
        return "en"
    import ctypes
    return "ru" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x19 else "en"


def show(exe, shader, extra=()):
    """what the panel shows: {kind: [text, ...]} in panel order"""
    out = subprocess.run([exe, shader, *extra], check=True, capture_output=True).stdout.decode("utf-8")
    seen = {}
    for line in out.splitlines():
        kind, _, text = line.split("\t", 2)
        seen.setdefault(kind, []).append(text)
    return seen


def expected(meta_lang, ui_lang, params, presets):
    groups, label, hint, options, name = build.LANGS[meta_lang]
    return {
        "lang": [ui_lang],
        "name": [p["name"] for p in params],
        "label": [p[label] for p in params],
        "hint": [p[hint] for p in params],
        "option": [o for p in params for o in p.get(options, [])],
        "group": list(groups.values()),
        "preset": [pr[name] for pr in presets],
    }


def check(case, seen, want, ui_lang):
    bad = [k for k, v in want.items() if seen.get(k, []) != v]
    ui = seen.get("ui", [])
    if UI_SAVE[ui_lang] not in ui or not any(UI_TITLE[ui_lang] in t for t in ui):
        bad.append("ui")
    counts = f"{len(seen.get('label', []))} params, {len(seen.get('group', []))} groups, {len(seen.get('preset', []))} presets"
    print(f"{case}: panel {seen.get('lang')}, {counts}:", "ok" if not bad else "FAIL " + ", ".join(bad))
    for k in bad:
        if k != "ui":
            print("   want", k, want[k][:3], "\n   got ", k, seen.get(k, [])[:3])
    return not bad


def main(args):
    work = os.path.abspath(args[0])
    shader = args[1] if len(args) > 1 else os.path.join(ROOT, "out", "cnc-ddraw", "Shaders", "crt-emu",
                                                        "crt-emu-pass1scale.glsl.pass1")
    old = args[2] if len(args) > 2 else None
    sys.stdout.reconfigure(errors="replace")   # texts may not fit a piped console's code page
    params = json.load(open(os.path.join(ROOT, "src", "params.json"), encoding="utf-8"))
    presets = json.load(open(os.path.join(ROOT, "src", "presets.json"), encoding="utf-8"))
    os.makedirs(work, exist_ok=True)
    exe = build_driver(work)

    sys_l = system_lang()
    other = "ru" if sys_l == "en" else "en"
    ru_game, en_game, ua_game = '<Language> = "#ru.ini"\r\n', '<Language> = "#en.ini"\r\n', '<Language> = "#ua.ini"\r\n'
    # (case, shader, install.ini or None, hota.ini or None, panel arguments,
    #  language of the metadata, language of the buttons, install.ini afterwards or None = unchanged)
    cases = [
        ("lang=en", shader, "[crt-emu]\r\nversion=2.1\r\nlang=en\r\n", None, [], "en", "en", None),
        ("LANG = RU", shader, "[crt-emu]\r\n  LANG = RU  \r\n", None, [], "ru", "ru", None),
        ("no install.ini, no game language", shader, None, None, [], sys_l, sys_l, None),
        ("lang=de", shader, "[crt-emu]\r\nlang=de\r\n", None, [], sys_l, sys_l, None),
        ("game ru", shader, "[crt-emu]\r\nversion=2.2\r\n", ru_game, [], "ru", "ru", None),
        ("game en", shader, None, en_game, [], "en", "en", None),
        ("game ua -> Windows", shader, None, ua_game, [], sys_l, sys_l, None),
        ("lang=en over game ru", shader, "[crt-emu]\r\nlang=en\r\n", ru_game, [], "en", "en", None),
        ("EN -> RU keeps live values", shader, "[crt-emu]\r\nversion=2.1\r\nlang=en\r\nx=1", None,
         ["set:PIXEL_GAP=0.33", "switch:ru"], "ru", "ru", "[crt-emu]\r\nversion=2.1\r\nlang=ru\r\nx=1"),
        ("RU -> EN", shader, "[crt-emu]\r\n  LANG = RU  \r\n", ru_game, ["switch:en"], "en", "en", "[crt-emu]\r\nlang=en\r\n"),
        ("switch adds lang=", shader, "[crt-emu]\r\nversion=2.2", None, [f"switch:{other}"], other, other,
         f"[crt-emu]\r\nversion=2.2\r\nlang={other}\r\n"),
        ("switch creates install.ini", shader, None, None, [f"switch:{other}"], other, other, f"[crt-emu]\r\nlang={other}\r\n"),
        ("lit button pins the game's language", shader, None, ru_game, ["switch:ru"], "ru", "ru", "[crt-emu]\r\nlang=ru\r\n"),
    ]
    if old:
        cases += [("old shader, lang=en", old, "[crt-emu]\r\nlang=en\r\n", None, [], "ru", "en", None),
                  ("old shader, lang=ru", old, "[crt-emu]\r\nlang=ru\r\n", None, [], "ru", "ru", None)]
    ok = 0
    for i, (case, src, ini, game, extra, meta_lang, ui_lang, ini_after) in enumerate(cases):
        d = os.path.join(work, f"case{i}")
        shutil.rmtree(d, ignore_errors=True)
        sd = os.path.join(d, "Shaders", "crt-emu")
        os.makedirs(sd)
        pass1 = os.path.join(sd, "crt-emu-pass1scale.glsl.pass1")
        shutil.copyfile(src, pass1)
        ini_file = os.path.join(sd, "install.ini")
        if ini is not None:
            with open(ini_file, "w", encoding="utf-8", newline="") as f:
                f.write(ini)
        if game is not None:
            os.makedirs(os.path.join(d, "_HD3_Data", "Settings"))
            with open(os.path.join(d, "_HD3_Data", "Settings", "hota.ini"), "w", encoding="utf-8", newline="") as f:
                f.write('<Version> = 5008319\r\n' + game)
        before = hashlib.sha256(open(pass1, "rb").read()).hexdigest()
        seen = show(exe, os.path.join(sd, "crt-emu-pass1scale.glsl"), extra)
        good = check(case, seen, expected(meta_lang, ui_lang, params, presets), ui_lang)
        # the switch keeps live values, never touches the shader file, writes only lang= to install.ini
        for arg in extra:
            if arg.startswith("set:"):
                name, val = arg[4:].split("=")
                if f"{name}={float(val):.3f}" not in seen.get("value", []):
                    print("   value lost:", name, [v for v in seen.get("value", []) if v.startswith(name + "=")]); good = False
        if hashlib.sha256(open(pass1, "rb").read()).hexdigest() != before:
            print("   the .pass1 file changed"); good = False
        now = open(ini_file, encoding="utf-8", newline="").read() if os.path.exists(ini_file) else None
        if now != (ini if ini_after is None else ini_after):
            print("   install.ini:", repr(now), "want", repr(ini if ini_after is None else ini_after)); good = False
        if seen.get("status", [""])[0]:
            print("   status:", seen["status"][0]); good = False
        ok += good
    print(f"osd_meta: {ok} of {len(cases)} case(s)", "OK" if ok == len(cases) else "FAILED")
    sys.exit(0 if ok == len(cases) else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
