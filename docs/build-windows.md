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

## Releases
GitHub Actions (`.github/workflows/release.yml`) builds everything on a Windows runner with the same llvm-mingw (20261020, checked by SHA-256) and runs the checks (`docs/testing.md`). A push to `main` keeps the files in the run's artifact; a tag `vX.Y.Z` publishes a release: `crt-emu-setup-X.Y.Z.exe`, `crt-emu-X.Y.Z.zip` (the setup's files in the layout of the game folder, for a manual install) and `SHA256SUMS.txt`. A tag with a suffix (`v2.3.0-rc.1`) gives a pre-release, any other tag the latest release.
1. Raise the version in `installer/build_installer.py` (`VERSION`), `installer/setup.rc` (four places) and `installer/app.manifest`; add the `## X.Y.Z` section to `CHANGELOG.md` (it becomes "What's new" in the release text, `.github/release-notes.md`).
2. `python tools/release.py check vX.Y.Z`.
3. Commit, push, wait for the build on `main`, then `git tag vX.Y.Z` and `git push origin vX.Y.Z`.

By hand, if CI is not available: build as above into a new empty folder, `build_installer.py --out dist/X.Y.Z/crt-emu-setup-X.Y.Z.exe`, then `python tools/release.py pack vX.Y.Z dist/X.Y.Z <notes.md>` and name the three files: `gh release create vX.Y.Z dist/X.Y.Z/crt-emu-setup-X.Y.Z.exe dist/X.Y.Z/crt-emu-X.Y.Z.zip dist/X.Y.Z/SHA256SUMS.txt --title "crt-emu X.Y.Z" --notes-file <notes.md> --latest`. Not `dist/*`: `dist/` holds other local files too.

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
- Since 2026-10-29 the reference is the Windows build: it passed the in-game checklist. The one in the 2.2.0 setup is
  `6701857C35F0…`, 1 238 016 bytes, fork `e45f03b`. The CI build of the same sources differs from it only in the timestamp
  (first CI run, 2026-10-30).

## Where to find things
- The cnc-ddraw fork: `docs/cnc-ddraw-fork.md`.
