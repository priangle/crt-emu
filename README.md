# crt-emu — a CRT tube for Heroes of Might and Magic III HD

crt-emu makes Heroes III (Horn of the Abyss + HD mod) look like it runs on a
cathode-ray tube monitor: beam scanlines whose width grows with brightness, a phosphor mask drawn
in the display's physical pixels, glow, and light scattered in the glass. It is designed for
high-density displays (5K, 4K) at an integer scale: 1280x720 → 4x on 5120x2880.

- **F12** — tune the tube right over the game: sliders change the picture live, "Save" keeps the values.
  "Magnifier" in the panel shows the screen's own pixels up close (x2 to x8): drag it with the mouse,
  the wheel over it zooms. Handy for a screenshot of the mask and the lines (Win+Shift+S).
- **F11** — effect on/off, handy for comparing.
- **PrintScreen** — a screenshot of the game frame without the effect.
- Windows display scaling above 100% is supported (tested at 200%): a custom cnc-ddraw build fixes
  the conflict with the HD mod.
- English or Russian: the setup follows Windows (or your choice in its first line), the F12 panel
  follows the game's language (else that of Windows, else English), and its EN / RU buttons switch it at once.

All tuning happens inside the game; there is no separate configuration tool.

**Status:** tested on one machine (see below).

## Requirements
- Heroes of Might and Magic III: Horn of the Abyss with the HD mod. The HD mod renderer must be
  "16-bit DirectDraw (original)" — the setup switches it.
- Windows and a graphics card with OpenGL.
- Tested on: Windows 11, HotA + HD mod `1.8.1_HD_5.8_R25` (GOG), NVIDIA GeForce RTX 5080,
  27-inch 5K display (5120x2880) at 200% scaling, game at 1280x720.

## Installation
1. Close the game and HD_Launcher.
2. Download `crt-emu-setup-<version>.exe` from [Releases](https://github.com/priangle/crt-emu/releases)
   and run it. The first line of the window is the language of the setup.
   The setup finds the game (or pick the folder with "Browse..."), installs the files and
   switches the HD mod to the "16-bit DirectDraw (original)" renderer.
   The setup is not signed, so Windows may warn about an unknown publisher:
   "More info" → "Run anyway".
3. Start the game through HD_Launcher and press F12.

Without the setup: `crt-emu-<version>.zip` from the same release holds the same files in the
layout of the game folder; see "Manual install" in its `Shaders/crt-emu/README.txt`. It does not
keep your tube settings and does not switch the HD mod renderer or system cursors.

Run the setup again to reinstall: your tube settings and the panel language are kept
("Keep my tube settings when reinstalling" is on by default).
The same window has an "Uninstall" button: it removes crt-emu, puts back the `ddraw.dll` and
`ddraw.ini` it replaced and the HD mod renderer and system cursors it switched (unless you changed
them yourself since). Your tube settings are deleted too: they live in the shader file.

## Known issues
- An HD mod update may delete `ddraw.dll` from the game folder, and the effect is gone. Run the
  setup again: your settings are kept.

## Building from source
See `docs/build-windows.md`. In short: Python 3 with pillow (numpy too for the tests) and
llvm-mingw (i686). The modified cnc-ddraw is a git submodule
([priangle/cnc-ddraw](https://github.com/priangle/cnc-ddraw), branch `crt-emu`): clone with
`git clone --recurse-submodules`, or run `git submodule update --init` in an existing clone.
The setup embeds `src/bin/ddraw.dll`, which is not in git, so build the DLL before the setup:
```
python build.py
python tools/build_ddraw.py third_party/cnc-ddraw src/bin/ddraw.dll
python installer/build_installer.py
```
Releases are built the same way by GitHub Actions from a version tag (`docs/build-windows.md`, "Releases").

## How it works
The shader model lives in `src/core.glsl`, one source for every build. `build.py` makes the
cnc-ddraw shaders that the setup installs (two-pass, plus a single-pass lite fallback) and a
`.slang` version for ShaderGlass and RetroArch; the `.slang` files are compile-checked in the
tests but not tried in those programs.
The project is developed with Claude Code. Developer documents in `docs/`:
`docs/architecture.md` (layout), `docs/crt-model.md` (the tube model),
`docs/cnc-ddraw-fork.md` (changes to cnc-ddraw), `docs/hd-mod.md` (HD mod notes),
`docs/build-windows.md` (building on Windows), `docs/testing.md` (checks).

## License
crt-emu is released under the [MIT License](LICENSE), © 2026 priangle.

- [cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw) © FunkyFr3sh — MIT, used in modified form;
  the changes in the fork are under MIT too.
- [Dear ImGui](https://github.com/ocornut/imgui) © Omar Cornut — MIT, part of the cnc-ddraw fork
  (the F12 panel).
- Heroes of Might and Magic is a trademark of Ubisoft; HotA and the HD mod are projects of their
  respective authors. crt-emu is not affiliated with them.
