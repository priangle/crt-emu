# Testing

## Automated
| What is checked | Command | Where it runs | Passes when |
|---|---|---|---|
| The shader builds in all variants | `python test/glrun.py modes out/cnc-ddraw/Shaders/crt-emu/crt-emu-pass1scale.glsl <folder> 5120 2880 src/testcard.png 'src/shots/*.webp'` — define, `--uniform` and `--uniform --core` in one command | Windows (WGL, the game's graphics card) and Linux/WSL (EGL, Mesa llvmpipe) | `ok` for each variant, `over ±1: 0` everywhere, summary `modes: … OK`, exit code 0 |
| ShaderGlass version | `python test/glrun.py slangcheck out/shaderglass/crt-emu.slang` and the same for `crt-emu-halation.slang` | Windows and Linux/WSL | `compiled + linked OK` for both |
| F12 panel language (no GL) | `python test/osd_meta_test.py <folder outside the repository> [.pass1 shader] [old .pass1]` — builds the panel with `test/osd_meta_test.c` and loads the shader with different `lang=` in `install.ini` | Windows (i686 llvm-mingw) and Linux (clang) | `ok` for each case, summary `osd_meta: … OK`, exit code 0; old `.pass1` (without `//@lang`) — Russian labels, buttons in the `install.ini` language |
| F12 panel outside the game | `sh test/build_osd_host.sh third_party/cnc-ddraw out/osdhost`, then `CRTEMU_OSD_SCALE=2 python test/osd_test.py out/osdhost/libosd.so <copy of the .pass1 shader> <background.png> out.png 2560 1440 move:x,y down up save` | Linux/WSL (EGL) | the panel is visible, "Save" changes only the numbers in the file |
| Settings carry-over in the setup | `cc -I installer installer/logic.c installer/test_logic.c -o test_logic`, how to run it — see the header of `test_logic.c` | any C compiler (on Windows — `i686-w64-mingw32-clang`) | `ok`; `#define` values = the old ones, the rest of the text = the new one |
| Moving an old PC-CRT install | a mock game folder in a temporary directory (empty `h3hota HD.exe`, `HD_Launcher.exe`, `_HD3_.dll`, copies of the game files), `installer\crt-emu-setup.exe /install "<folder>" 1 1 lang=en` (or `lang=ru`), close the summary window. The setup writes this folder and the language to `HKCU\Software\crt-emu`: after the check, restore `GamePath`, and restore or delete `Language` | Windows | exit code 0; the summary window is in the `lang=` language, `install.ini` has the same `lang=`; no `Shaders\pc-crt`; the `#define` and `#pragma parameter` values = the old `#define`; only the paths changed in `ddraw.ini` |

- Frames for the checks: `src/shots/*.webp` (game frames, local only) or `src/testcard.png`.
- `modes` writes the frames into the given folder: `<frame>-define.png`, `-uniform.png`, `-core.png`. Use a folder outside the repository: game frames do not go into git. One frame of one variant: `glrun.py ddraw <shader> <frame.png> <out.png> W H [--uniform] [--core]`.
- Negative check: `set:NAME=value` at the end of the `modes` command changes the parameter only in the uniform variants, and the comparison must fail (exit code 1).
- On Windows the game's graphics card does the rendering (the `GL:` line in the output): the compat context is created as in the game, with a plain `wglCreateContext`, the core one as in cnc-ddraw with `opengl_core`. Do not compare frames from the NVIDIA driver and from llvmpipe pixel by pixel: the drivers differ.
- Calibration against photos: `python test/calibrate.py` renders with the two-pass cnc-ddraw build through `glrun.py ddraw` (Windows or Linux/WSL, numpy and pillow).

## Manual in-game checklist (after DLL or shader changes)
1. Close the game and HD_Launcher → copy the build into the game folder (run the setup and press "Reinstall") → verify the checksums.
2. Start through HD_Launcher: the intro videos and the menu are visible at once, without Alt+F4.
3. The mask is not green, the frame is not thinned out; the cursor reaches the right and bottom edges; clicks work.
4. F11 — the effect turns off and on, the picture is not upside down.
5. F12 — the panel opens, a slider changes the picture at once, clicks on the panel do not go to the game, the game cursor is frozen. "Save" → restart the game → the values are kept.
6. PrintScreen — a plain `.png` with the source frame appears in `Screenshots`.
7. Evidence: a screenshot or a photo; attach it to the test report.

## Live setup test (after setup changes)
The setup window is started with `Start-Process installer\crt-emu-setup.exe`; a person presses the buttons. Windows itself puts Win+Shift+S snapshots into `Pictures\Screenshots`; the report takes them from `src/shots/<test>/`.
1. Before the test:
   - a copy in `dist/backup-<date>/`: `ddraw.dll`, `ddraw.ini`, `Shaders\crt-emu\*` and `_HD3_Data\Settings\*.ini` (the "Set up the HD mod" checkbox may rewrite the profiles);
   - a snapshot of the `#define` and `#pragma parameter` values from `.pass1`.
2. **Reinstall over the install** (game folder): values = the snapshot, the shader text without the values = `out/`, `ddraw.dll` = `src/bin`, the user's `ddraw.ini` is untouched.
3. **"The HD mod deleted the DLL"**: the game and HD_Launcher are closed (check with `tasklist`: the file is moved by hand, not by the setup, so the setup's check for a running game does not work here), move `ddraw.dll` into the copy → the status line says "ddraw.dll is missing or replaced" → "Reinstall" → compare as in step 2.
4. **Game**: F12 shows the snapshot values, F11 works.
5. **Uninstall with foreign files** — a mock folder, not the game folder (uninstalling would erase `.pass1`). Its contents:
   - empty `h3hota HD.exe`, `HD_Launcher.exe`, `_HD3_.dll`;
   - foreign `ddraw.dll` and `ddraw.ini`;
   - `_HD3_Data\Settings\hota.ini` with a different `<Graphics.v2.Mode>` and `<Graphics.SystemCursors>`, and its copy `second.ini`;
   - a foreign shader in `Shaders\other`.

   The helper scripts are not in the repository yet. One makes such a folder and lists and compares the file checksums; another can drive the window (UI Automation and `WM_COMMAND`, snapshots through `PrintWindow`: a screen snapshot would capture the windows lying on top).

   After installing, the foreign files and profiles are in `*.crt-emu-backup`, and the summary names both copies. Then set `Mode = 3` in `second.ini` (as if the user had changed the renderer themselves). The uninstall question: buttons in the window's language, "Cancel" is the default and changes nothing. After uninstalling: the foreign files are in place with the same checksums, `Shaders\other` is intact, `hota.ini` is byte for byte as before installing, `Mode = 3` in `second.ini` stays, the cursors are back; no copies are left; the `HKCU\Software\crt-emu` key is deleted if `GamePath` pointed to this folder.
6. **Folder without write access** — a mock one. The GOG game folder will not do: `C:\Program Files\GOG Galaxy\Games` gives Users write access, and the setup writes without UAC. The owner sets Program Files-like permissions, without administrator rights:
   `icacls "<folder>" /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX'`, then `icacls "<folder>\*" /reset /T /Q`. No `/T` in the first command: with it, the files inside are left with an empty access list.

   Passes when:
   - "No" in UAC — the message "This folder needs administrator rights, and the request was declined.", the folder is unchanged;
   - "Yes" — the summary is shown by the elevated copy, in the window's language; our files are owned by `BUILTIN\Administrators`;
   - uninstalling through UAC returns the folder to its original state.

   Cleanup:
   - `icacls "<folder>" /reset /T /Q`, delete the folder;
   - keep the path in a variable and check that it is not empty: an empty one turns `"\*" /reset /T` into a permission reset of the whole drive;
   - this works only if the uninstall through UAC succeeded. If files owned by Administrators are left (the test broke off after installing), first "Uninstall" through UAC, or clean up from PowerShell run as administrator.
7. After the mock folders, restore in `HKCU\Software\crt-emu` both `GamePath` (to the game folder) and `Language`: installing into a mock folder and changing the language in the window write both, and uninstalling from a mock folder deletes the whole key. Write down both values before the test (`reg query 'HKCU\Software\crt-emu'`).
