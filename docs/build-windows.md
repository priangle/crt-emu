# Building on Windows

## Install once
```
winget install --id Git.Git -e                      # Git for Windows: clone with the submodule
winget install --id Python.Python.3.12 -e --scope user
winget install --id GitHub.cli -e                   # gh: repository, PRs, releases
winget install --id MartinStorsjo.LLVM-MinGW.UCRT -e
python -m pip install pillow numpy
```
- llvm-mingw with an x86_64 host builds for i686 too. Check in a new terminal: `i686-w64-mingw32-clang --version`.
- If the command is not found, point to the toolchain's `bin` folder: `setx CRTEMU_MINGW_BIN "C:\…\llvm-mingw-…\bin"`. Both build scripts read this variable (before the project was renamed to crt-emu it was `PCCRT_MINGW_BIN`).
- If `windres` cannot find `<windows.h>`, set `CRTEMU_MINGW_INCLUDE` (the toolchain's `include` folder, for i686).

### Tested setup (2026-10-29)
- Python 3.12.10 (`--scope user`, without administrator rights), pillow 13.0, numpy 2.5.4. Before the install, `python` led to the Microsoft Store stub
  (`%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe`); after the install the real Python comes before it in PATH. Check: `python --version`.
- llvm-mingw 20261020 (clang 23.1.4). winget itself puts the commands into `%LOCALAPPDATA%\Microsoft\WinGet\Links`, so
  `CRTEMU_MINGW_BIN` and `CRTEMU_MINGW_INCLUDE` were not needed. The commands include common names (`gcc`, `cc`, `ar`, `strip`, `strings`,
  `nm`, `windres`): they may shadow programs of the same name from other packages.
- PATH changes only in a new terminal. In a PowerShell window that is already open:
  `$env:Path = [Environment]::GetEnvironmentVariable('Path','User') + ';' + [Environment]::GetEnvironmentVariable('Path','Machine')`.
- Time: `build.py` — instant, DLL — 5 s, setup — a few seconds.
- One warning while building the DLL: `-Wdeprecated-non-prototype` in `src/directinput.c`. It is an upstream file, not ours.

## Commands
| What | Command | Result |
|---|---|---|
| shaders | `python build.py` | `out/cnc-ddraw/…`, `out/shaderglass/…` |
| ddraw.dll | `python tools/build_ddraw.py third_party/cnc-ddraw src/bin/ddraw.dll` | DLL ≈1.2 MB |
| setup | `python installer/build_installer.py` | `installer/crt-emu-setup.exe` ≈1.4 MB |

- `build.py` accepts overrides: `python build.py GLOW=0.08 PIXEL_GAP=0.3` changes the default values in `out/`, not in `src/params.json`.
- The setup takes `src/bin/ddraw.dll` or `--dll <path>`, and the shaders from `out/`. Hence the order: `build.py` → `build_ddraw.py` → `build_installer.py`.
- Releases are built by hand for now; CI builds are planned.

## Comparing a new DLL with the reference `src/bin/ddraw.dll`
- **Same compiler.** Build into a separate folder under the name `ddraw.dll`: then the builds differ only in the timestamp
  in the PE header (offset 0x80). The linker writes the output file name into the export table. With another name (`ddraw-test.dll`)
  the addresses in `.rdata` and `.text` shift: thousands of differing bytes with the same code (checked 2026-10-29).
- **Another compiler version.** The size and the bytes differ. An earlier reference built in another environment (unknown llvm-mingw version) was
  1536 bytes smaller than the Windows build (clang 23.1.4) from the same sources: less code, more data. In that case compare like this:
  - exports: `llvm-readobj --coff-exports <dll>` — the same 30 names, `DirectDrawCreate` among them;
  - strings in the DLL are the same (the earlier build has a different version signature `git~pccrt-dpi, pc-crt`; on Windows the ImGui paths are written with `\`);
  - sources: the commits of the `crt-emu` branch match `cnc-ddraw/patches` by `git patch-id --stable`;
  - finally, the manual in-game checklist (`docs/testing.md`).
- Since 2026-10-29 the reference is the Windows build: it passed the in-game checklist. The one in the 2.1.0 setup is
  `68FF89FEE019…`, 1 234 944 bytes, fork `cdb808f`.

## Where to find things
- The cnc-ddraw fork: `docs/cnc-ddraw-fork.md`.
