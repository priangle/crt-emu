#!/usr/bin/env python3
"""F12 panel outside the game, without GL: which "//@lang" block it reads and which language its
own buttons speak, for every lang= in install.ini.

    python test/osd_meta_test.py <work dir outside the repo> [shader .pass1] [old .pass1]

Builds test/osd_meta_test.c with the panel (crtemu_osd.cpp + Dear ImGui) of third_party/cnc-ddraw:
i686 llvm-mingw on Windows (on PATH or in CRTEMU_MINGW_BIN), $CC / $CXX (clang) elsewhere.
The shader defaults to out/cnc-ddraw/Shaders/crt-emu/crt-emu-pass1scale.glsl.pass1 (python build.py).
An old .pass1 (no "//@lang", e.g. a copy from a game installed before the blocks) must keep its
Russian texts, with the buttons in the language of install.ini.
"""
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


def show(exe, shader):
    """what the panel shows: {kind: [text, ...]} in panel order"""
    out = subprocess.run([exe, shader], check=True, capture_output=True).stdout.decode("utf-8")
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

    # (case, shader, install.ini text or None, language of the metadata, language of the buttons)
    cases = [
        ("lang=en", shader, "[crt-emu]\r\nversion=2.1\r\nlang=en\r\n", "en", "en"),
        ("LANG = RU", shader, "[crt-emu]\r\n  LANG = RU  \r\n", "ru", "ru"),
        ("no install.ini", shader, None, "en", "en"),
        ("lang=de", shader, "[crt-emu]\r\nlang=de\r\n", "en", "en"),
    ]
    if old:
        cases += [("old shader, lang=en", old, "[crt-emu]\r\nlang=en\r\n", "ru", "en"),
                  ("old shader, lang=ru", old, "[crt-emu]\r\nlang=ru\r\n", "ru", "ru")]
    ok = 0
    for i, (case, src, ini, meta_lang, ui_lang) in enumerate(cases):
        d = os.path.join(work, f"case{i}")
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        shutil.copyfile(src, os.path.join(d, "crt-emu-pass1scale.glsl.pass1"))
        if ini is not None:
            with open(os.path.join(d, "install.ini"), "w", encoding="utf-8", newline="") as f:
                f.write(ini)
        seen = show(exe, os.path.join(d, "crt-emu-pass1scale.glsl"))
        ok += check(case, seen, expected(meta_lang, ui_lang, params, presets), ui_lang)
    print(f"osd_meta: {ok} of {len(cases)} case(s)", "OK" if ok == len(cases) else "FAILED")
    sys.exit(0 if ok == len(cases) else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
