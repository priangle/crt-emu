# HD mod and the game: findings

Tested install: `C:\Program Files\GOG Galaxy\Games\Heroes of Might and Magic III - Horn of the Abyss` (GOG, id 1718139055), HotA 1.8.1, HD mod 5.8 (after the 2026-10-26 update `<Version> = 5008319`).
Display: Samsung Odyssey G80HF, 27″ 5120x2880 (218 ppi), Windows scaling 200%, RTX 5080.

## Renderer
- `_HD3_Data\Settings\hota.ini` (the HotA profile; keys of the form `<Key> = value  {comment}`):
  - `<Graphics.v2.Mode> = 0` — "16-bit DirectDraw (original)", the only mode that takes `ddraw.dll` from the game folder, that is, our cnc-ddraw;
  - `<Graphics.Resolution> = 1280x720` — "Source size"; with `boxing=true` this is 4x on 5K;
  - `<Graphics.SystemCursors> = 0` — the game draws the cursor; needed so that the cursor is under the shader and freezes while the panel is open.
- More settings: `HotA_Settings.ini` in the game root; `_HD3_Data\HD_Launcher.ini`. `<Sys.WriteToIniInsteadRegistry> = 1` — the settings are kept in ini files, not in the registry.
- `_HD3_.dll` sets DPI awareness: `SetProcessDpiAwareness(2)`, then `SetThreadDpiAwarenessContext(-4)`. For modes 0, 1, 4 it then calls `SetThreadDpiAwarenessContext(-1)` (UNAWARE); modes 2, 3, 5, 6 stay DPI-aware. At 200% this gives 2:1 frame decimation and a mouse that covers half of the screen — fixed by `fix_dpi_unaware`.
- `_HD3_.dll` contains the message "Error loading DDRAW.DLL".

## Updates and the launcher
- The HD mod update (`_HD3_Data\HD3_Update.exe`) deleted `ddraw.dll` from the game folder three times (most recently on 2026-10-30), though not every update does; `ddraw.ini` and `Shaders\` stayed in place.
- `HD_LauncherNative.dll` deletes only the OpenGL wrapper by Verok: ProductName "Heroes3GL" or "verok" in the copyright. Our build does not match this.
- While the launcher or the game is running, they hold their files; the launcher may rewrite the settings on exit.

## Input
- `h3hota HD.exe` imports `GetMessageA`, `PeekMessageA`, `GetKeyState`, `GetCursorPos`, `ShowCursor` — DirectInput is not used.
- `HD_HOTA.dll` calls `SetWindowsHookExA` and reads `GetKeyState`; `_HD3_.dll` — `GetCursorPos`, `GetKeyState`. That is why the F12 panel intercepts input with a `WH_GETMESSAGE` hook installed after theirs (it fires first), and not in WndProc.

## Videos, menus, mouse (history)
- Before the right keys were in `ddraw.ini`, menus and videos stayed black until Alt+F4, and clicks did not get through. What helped: `maxfps=60`, `minfps=-2` (constant redraw), `devmode=true`, `nonexclusive=true`, `no_dinput_hook=true`.
- Borderless full-screen window: `windowed=true` + `fullscreen=true` + `border=false`; F4 (`keytogglefullscreen2=0x73`) toggles the mode.
