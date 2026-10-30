# cnc-ddraw fork

Base: [FunkyFr3sh/cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw), commit `279a057` (7.1.0.1), MIT license.
Fork: [priangle/cnc-ddraw](https://github.com/priangle/cnc-ddraw) (public), included in crt-emu as the submodule `third_party/cnc-ddraw`.
The `crt-emu` branch has nine commits (a copy is in `cnc-ddraw/patches/`). Before the project was renamed to crt-emu, the branch was called `pccrt`. GitHub redirects only web links to the old name; git will not find the branch by the name `pccrt`.

| Commit | What | Files |
|---|---|---|
| 1 | `fix_dpi_unaware` (on by default): the HD mod cannot switch the window to DPI unaware. Screenshot names are cleaned of `<>:"/\|?*` | `src/winapi_hooks.c`, `src/hook.c`, `src/dllmain.c`, `src/config.c`, `inc/config.h`, `inc/winapi_hooks.h`, `src/screenshot.c` |
| 2 | `keytoggleshader` (F11): the frame without the shader via `glBlitFramebuffer` | `src/render_ogl.c`, `src/keyboard.c`, `src/opengl_utils.c`, `inc/*` |
| 3 | `keyosd` (F12): a Dear ImGui 1.92.9 panel (embedded in `src/imgui`), parameters as uniforms, input via `WH_GETMESSAGE`. The `HOOKLIST` hook table is extended from 39 to 48 entries: user32 overflowed it and lost the terminator | `src/crtemu/crtemu_osd.cpp`, `inc/crtemu_osd.h` (in this commit still `src/pccrt/pccrt_osd.cpp`, `inc/pccrt_osd.h`), `src/render_ogl.c`, `src/opengl_utils.c`, `src/keyboard.c`, `src/winapi_hooks.c`, `inc/hook.h`, `Makefile` |
| 4 | Rename PC-CRT → crt-emu: panel files, identifiers `crtemu_*`/`g_crtemu_*`/`CRTEMU_*`, marker comments, panel title "crt-emu · кинескоп". No change in behavior | all files of commits 1–3 that carry markers |
| 5 | Panel language: `lang=` from `install.ini` next to the shader (`en` by default, `ru`), metadata blocks `//@lang|xx`, the panel's own strings in an EN/RU table. Under `CRTEMU_OSD_TEST` — getters for `test/osd_meta_test.py` | `src/crtemu/crtemu_osd.cpp`, `inc/crtemu_osd.h` |
| 6 | EN / RU buttons in the panel: the language switches at once (live values kept), the choice goes to `install.ini`. Without `lang=` the panel follows the game's language (HD mod profile), then Windows, then English. One helper writes the shader file and `install.ini` through `.tmp` | `src/crtemu/crtemu_osd.cpp` |
| 7 | Magnifier in the panel: a round lens under it with the screen's own pixels enlarged x2…x8, dragged with the mouse, shown only with the panel. The square under it is copied from the back buffer before ImGui draws (`glCopyTexSubImage2D` through the backend's loader) and drawn with the backend's nearest sampler | `src/crtemu/crtemu_osd.cpp`, `inc/crtemu_osd.h` |
| 8 | Pill sliders: a thin line with a pill-shaped handle that carries the value, so the number is never under the handle. Input as in `ImGui::SliderScalar` (`SliderBehavior`, `TempInputScalar`); the magnifier's zoom and size become rows like the parameters | `src/crtemu/crtemu_osd.cpp` |
| 9 | The magnifier's window gets a margin for its rim (ImGui clips a window's drawing to its rectangle, the rings were cut flat at four points); the pill slider's comment names the input the panel has | `src/crtemu/crtemu_osd.cpp` |

New `ddraw.ini` keys: `fix_dpi_unaware=true`, `keytoggleshader=0x7A`, `keyosd=0x7B`.

## Getting the source
```
git clone --recurse-submodules https://github.com/priangle/crt-emu
```
- In an existing crt-emu clone: `git submodule update --init`. The submodule is checked out at the commit recorded in crt-emu, with a detached HEAD — before making changes, run `git -C third_party/cnc-ddraw checkout crt-emu`.
- The original, for updates: `git -C third_party/cnc-ddraw remote add upstream https://github.com/FunkyFr3sh/cnc-ddraw`. The fork has no tags; `git fetch upstream --tags` brings them.
- The part in parentheses in `git submodule status` is the output of `git describe`: in a fresh clone `remotes/origin/crt-emu`, and if the upstream tags are present, the nearest tag (`experimental-29-gcdb808f`). The commit is the same.
- Without GitHub, from the patches: `git checkout -b crt-emu 279a057 && git am ../../cnc-ddraw/patches/*.patch`.

## Building
`python tools/build_ddraw.py third_party/cnc-ddraw src/bin/ddraw.dll`. Requires i686 llvm-mingw, see docs/build-windows.md.
The script writes `inc/git.h` itself, compiles C99 and C++ without a runtime and links with `exports.def`.

## Rules for changes
- Mark every change with a `crt-emu` comment (in commits 1–3 the markers are still `PC-CRT`; commit 4 changed them). Keep general fixes in separate commits: that makes them easier to offer to the upstream author.
- Do not ignore compiler warnings in your own files. `excess elements in array initializer` once already meant a lost terminator.
- A new hotkey: `inc/config.h` (a field in `hotkeys`), `src/config.c` (`GET_INT`), `src/keyboard.c` (before the screenshot block, `return 1` so that the game does not see it).
- After a commit in the fork: `git format-patch 279a057..crt-emu -o ../../cnc-ddraw/patches/` (delete the old patches), and in crt-emu, together with the patches, the new submodule pointer (`git add third_party/cnc-ddraw`). Push to the fork with `git push origin crt-emu` only when the maintainer asks: the fork is public.
- Updating to a new upstream: `git fetch upstream --tags`, `git rebase` of the `crt-emu` branch onto the new FunkyFr3sh tag, rebuild, the manual checklist from docs/testing.md. Rebase changes the hashes: push to the fork with `git push --force-with-lease origin crt-emu`.
