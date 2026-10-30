#!/usr/bin/env python3
"""Build ddraw.dll from the crt-emu fork of cnc-ddraw without make.

    python tools/build_ddraw.py <cnc-ddraw checkout> [out.dll] [--jobs N]

Needs an i686 MinGW toolchain on PATH (llvm-mingw recommended): i686-w64-mingw32-clang and
i686-w64-mingw32-windres. Set CRTEMU_MINGW_BIN to the toolchain's bin folder to use one that
is not on PATH. Compiles C as C99 and the Dear ImGui panel as C++ without the C++ runtime
(no exceptions, RTTI or thread-safe statics), exactly as the crt-emu releases are built.
"""
import concurrent.futures as cf
import glob
import os
import subprocess
import sys

CC = "i686-w64-mingw32-clang"
WINDRES = "i686-w64-mingw32-windres"
CFLAGS = ["-Iinc", "-O2", "-Wall", "-std=c99"]
CXXFLAGS = ["-x", "c++", "-std=c++11", "-O2", "-Wall", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
            "-DIMGUI_DISABLE_DEMO_WINDOWS", "-DIMGUI_DISABLE_WIN32_DEFAULT_IME_FUNCTIONS",
            "-DIMGUI_DISABLE_DEFAULT_SHELL_FUNCTIONS", "-Isrc/imgui", "-Iinc"]
LDFLAGS = ["-Wl,--enable-stdcall-fixup", "-s", "-static", "-shared"]
LIBS = ["-lgdi32", "-lwinmm", "-lole32", "-lmsimg32", "-lavifil32", "-luuid"]


def tool(name):
    b = os.environ.get("CRTEMU_MINGW_BIN")
    if b:
        exe = os.path.join(b, name + (".exe" if os.name == "nt" else ""))
        if os.path.exists(exe):
            return exe
    return name


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    return r.returncode, out


def git_header(src):
    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=src, capture_output=True, text=True).stdout.strip()
        except OSError:
            return ""
    commit = git("describe", "--match=NeVeRmAtCh", "--always", "--dirty") or "unknown"
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "crt-emu"
    with open(os.path.join(src, "inc", "git.h"), "w", newline="\n") as f:
        f.write(f'#define GIT_COMMIT "{commit}"\n#define GIT_BRANCH "{branch}"\n')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    src = os.path.abspath(args[0])
    out = os.path.abspath(args[1]) if len(args) > 1 else os.path.join(src, "ddraw.dll")
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else os.cpu_count() or 4
    objdir = os.path.join(src, "obj-crtemu")
    os.makedirs(objdir, exist_ok=True)
    git_header(src)

    c_files = sorted(glob.glob("src/*.c", root_dir=src) + glob.glob("src/*/*.c", root_dir=src))
    cpp_files = sorted(glob.glob("src/imgui/*.cpp", root_dir=src) + ["src/imgui/backends/imgui_impl_opengl3.cpp"] +
                       glob.glob("src/crtemu/*.cpp", root_dir=src))
    jobs_list = [([tool(CC), *CFLAGS, "-c", f, "-o", os.path.join(objdir, f.replace("/", "_").replace("\\", "_") + ".o")], f)
                 for f in c_files]
    jobs_list += [([tool(CC), *CXXFLAGS, "-c", f, "-o", os.path.join(objdir, f.replace("/", "_").replace("\\", "_") + ".o")], f)
                  for f in cpp_files]
    failed = False
    with cf.ThreadPoolExecutor(jobs) as ex:
        for (cmd, f), (rc, msg) in zip(jobs_list, ex.map(lambda j: run(j[0], src), jobs_list)):
            if rc:
                failed = True
                print(f"FAIL {f}\n{msg}")
            elif "warning" in msg and "src/imgui" not in f:
                print(f"warn {f}\n{msg}")
    if failed:
        return 1
    rc, msg = run([tool(WINDRES), "-J", "rc", "-I", ".", "res.rc", os.path.join(objdir, "res.o")], src)
    if rc:
        print("FAIL res.rc\n" + msg)
        return 1
    objs = sorted(glob.glob(os.path.join(objdir, "*.o")))
    rc, msg = run([tool(CC), *LDFLAGS, "-o", out, *objs, "exports.def", *LIBS], src)
    if rc:
        print("FAIL link\n" + msg)
        return 1
    print(f"built {out} ({os.path.getsize(out)} bytes) from {len(c_files)} C + {len(cpp_files)} C++ files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
