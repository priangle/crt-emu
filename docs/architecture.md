# Architecture

```
src/core.glsl ─┐                        ┌─ out/cnc-ddraw/Shaders/crt-emu/*.glsl ─┐
src/halation  ─┼─ build.py ─────────────┤                                        │
src/params    ─┤  (+presets → //@ meta) └─ out/shaderglass/*.slang(p)            │
src/presets   ─┘                                                                 │
cnc-ddraw (fork) ── tools/build_ddraw.py → src/bin/ddraw.dll ────────────────────┤
                                 installer/build_installer.py ←──────────────────┘ → crt-emu-setup.exe
tag vX.Y.Z → .github/workflows/release.yml: the chain above → tools/release.py pack → release
             (crt-emu-setup-X.Y.Z.exe, crt-emu-X.Y.Z.zip, SHA256SUMS.txt)
```

## Shader
- `src/core.glsl` — the whole model (`crt_shade(pos, fc)`); `src/halation.glsl` — the first pass (scattering in the glass). The targets (`build.py`) only supply the wrapper: how to read the texture, the sizes, the frame number.
- Two passes in cnc-ddraw: `crt-emu-pass1scale.glsl` (halation, at the game resolution) and `crt-emu-pass1scale.glsl.pass1` (the tube, at the screen resolution). The `-pass1scale` suffix is required: it is what makes cnc-ddraw run the first pass at the game resolution. `crt-emu-lite.glsl` — a single pass without halation.
- Layout of the `.pass1` file: `#pragma parameter` (name, English description, default, min, max, step) → panel metadata in two blocks, `//@lang|en`, then `//@lang|ru`; each holds the lines `//@group|…`, `//@param|NAME|group|label|hint`, `//@options|NAME|…`, `//@preset|id|name|K=V;…` → in the FRAGMENT section, `#ifdef PARAMETER_UNIFORM` uniforms, `#else` a block of `#define NAME value // label`.
  - Block texts: `ru`, `hint`, `options`, `name` and `label_en`, `hint_en`, `options_en`, `name_en` from `params.json` / `presets.json`; groups — `GROUP_RU` / `GROUP_EN` in `build.py`. `check()` in `build.py` requires all English fields (and `note_en` for presets) and forbids `|` and line breaks.
  - `//@` lines before the first `//@lang` apply to all languages: this is how shaders from before the panel language support are read. There is no backward compatibility: a panel from before the language support reads both blocks one after the other — group headers in English, labels in Russian, 12 presets. Install the new shader only together with the DLL that has the language support (the setup does exactly that).
- The model: see `docs/crt-model.md`.

## cnc-ddraw fork (details in docs/cnc-ddraw-fork.md)
- `fix_dpi_unaware` — `SetThreadDpiAwarenessContext` with UNAWARE contexts is blocked (a hook in the user32 list and a substitute via `GetProcAddress`), the main thread is switched to PMv2.
- `keytoggleshader` (F11) — the `g_crtemu_shader_off` flag: the frame without the shader via `glBlitFramebuffer` from the FBO, flipped.
- `keyosd` (F12) — `src/crtemu/crtemu_osd.cpp`, the window "crt-emu · CRT tube" / "crt-emu · кинескоп":
  - `crtemu_osd_load(shader)` parses `.pass1`; `opengl_utils.c` compiles this file with `#define PARAMETER_UNIFORM`;
  - language — `lang=` from `install.ini` in the shader folder (`en` or `ru`); with no such line or any other value — the game's language, `<Language> = "#ru.ini"` in the HD mod profile `_HD3_Data\Settings\hota.ini` two folders above the shader; if that is not `en`/`ru` either — the Windows display language (`GetUserDefaultUILanguage`, Russian → `ru`), else `en`. The panel reads the `//@lang` block of its language, if there is none — `en`, if there is no `en` — the first block; it takes its own buttons and captions from the `STR` table in the same language;
  - only the HotA profile (`hota.ini`) is read for the game's language;
  - the EN / RU buttons at the right end of the Save row switch the language before the next frame: the shader file is parsed again for the new block, live and saved values are carried over by name, the file itself is not written. The choice goes to `install.ini` as `lang=` (that line replaced, the rest kept; appended or the file created if missing); a press on the lit button writes it too, so the language the panel opened with becomes a choice. If that write fails, the panel says so and keeps the language until the game is closed. If the shader file has no parameters any more when it is parsed again, the panel closes. Group headers have their group id as the ImGui ID, so open and closed groups stay as they were;
  - every frame `crtemu_apply_params()` sets the uniforms (a location cache per program);
  - before `SwapBuffers`, `crtemu_osd_render()` draws ImGui (GL3 backend, Segoe UI font, scaled by the window DPI);
  - input: on the first opening, a `WH_GETMESSAGE` hook is set on the window thread. While the panel is open, mouse and keyboard messages go to the panel queue and are turned into `WM_NULL`; `GetCursorPos` gives the game the last point, `GetKeyState`/`GetAsyncKeyState` — 0;
  - "Save" rewrites the numbers in `#define` and `#pragma parameter` via a temporary file (`MoveFileEx`); `install.ini` is written the same way.
- Screenshot (PrintScreen) — the original game frame; the file name is cleaned of `<>:"/\|?*`.

## Setup (`installer/`)
- `setup.c`: a dialog from `setup.rc`, PerMonitorV2, no administrator rights.
  - Language of the setup itself — the first line of the window (English / Русский): a choice made in that line is stored in `HKCU\Software\crt-emu\Language` (`en`/`ru`); without one, the Windows display language (Russian → Русский, any other → English). Setup 2.1 also stored its language on every install, so on a machine where it ran, that value counts as a choice. The dialog template and VERSIONINFO are in English; all texts of the window and the messages are in the `STR` table (EN/RU); changing the language rewrites the window at once (`apply_texts`).
  - It does not set the F12 panel's language. A reinstall carries the `lang=` line of the old `install.ini` over (the panel's choice), except from a record with a version below 2.2: those setups wrote their own language there, and the line is dropped so the panel follows the game. A new install writes none.
  - Finding the game: the saved path (`HKCU\Software\crt-emu\GamePath`, then the old `HKCU\Software\PC-CRT\GamePath`) → the GOG and NWC registry entries → typical folders on all fixed drives.
  - The "our DLL" marker is the string `fix_dpi_unaware` inside it; the "our ini" marker is `crt-emu build` (from the comments of our `ddraw.ini`; plain `crt-emu` would match the shader path) or the old `PC-CRT`.
  - Install: a `ddraw.dll`/`ddraw.ini` that is not ours is copied to `*.crt-emu-backup`; the DLL is installed atomically (temporary file + `MoveFileEx`); with "Keep my tube settings when reinstalling", our `ddraw.ini` is not touched; the shaders get their values from the old `.pass1` (`crtemu_merge_settings`); if the checkbox is on, `<Graphics.v2.Mode> = 0` and `<Graphics.SystemCursors> = 0` are set in `_HD3_Data\Settings\*.ini`; at the end `Shaders\crt-emu\install.ini` is written.
  - An install under the old name PC-CRT (`Shaders\pc-crt\install.ini` or `pc-crt-pass1scale.glsl.pass1` — this is also how a manual install is recognized) is migrated:
    - the settings are taken from the old `.pass1`;
    - in `ddraw.ini`, the paths `pc-crt\pc-crt-` are changed to `crt-emu\crt-emu-` (`crtemu_replace_ci`), the rest is not touched;
    - the `*.pccrt-backup` copies (`ddraw.dll`, `ddraw.ini`, HD mod profiles) are renamed to `*.crt-emu-backup` before the install;
    - after the new files are written, the files of the old payload and `install.ini` in `Shaders\pc-crt` are deleted, and the folder itself only if it is empty. If `ddraw.ini` still refers to `pc-crt\` or `pc-crt/` (the path is written differently), the old files stay, otherwise the game would lose the shader. The final window reports a folder that was left in place;
    - the `HKCU\Software\PC-CRT` key is deleted.
  - If writing is not possible (`ERROR_ACCESS_DENIED`), the setup restarts itself via `runas` with `/install "<folder>" hd keep lang=xx`; without `lang=` — English.
  - Both READMEs (`README.txt` and `README.ru.txt`) and the licenses go into the shader folder: `crt-emu-LICENSE.txt`, `cnc-ddraw-LICENSE.txt`, `imgui-LICENSE.txt`.
  - HD mod profiles: before the two keys are switched (`<Graphics.v2.Mode>`, `<Graphics.SystemCursors>` → 0), the profile is copied to `*.ini.crt-emu-backup`; if the copy already exists, only the keys being switched now are updated in it. If the copy cannot be saved, the profile is left alone.
  - Uninstall:
    - first the HD profiles: each of the two keys goes back to the value from the copy if the profile still has our 0; otherwise the user changed it and the key stays; the other lines of the profile are not touched; the copy is deleted;
    - our files are deleted (and the files of an old PC-CRT install), the copies of `ddraw.dll`/`ddraw.ini` are put back (and the old `*.pccrt-backup` ones);
    - the `HKCU\Software\crt-emu` key (and the old `PC-CRT` one) is deleted if there is no `GamePath` or it points to this folder.
  - The uninstall question is a TaskDialog with buttons in the setup language, "Cancel" by default.
- `logic.c` — text operations without WinAPI (portable and tested on Linux).

## Tuning
Only in the game, with the F12 panel. The web tuner is gone.
