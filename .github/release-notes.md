crt-emu makes Heroes of Might and Magic III (Horn of the Abyss + HD mod) look like it runs on a CRT tube on high-density displays, tuned right in the game.

Tested on one machine: Windows 11, HotA + HD mod `1.8.1_HD_5.8_R25` (GOG), NVIDIA GeForce RTX 5080, 27-inch 5K display at 200% scaling, game at 1280x720.

## What's new
{changes}

## Install
1. Close the game and HD_Launcher.
2. Run `crt-emu-setup-{version}.exe`. The first line of the window is the language of the setup (English or Russian; by default that of Windows). The setup finds the game, installs the files and switches the HD mod to the "16-bit DirectDraw (original)" renderer.
   The setup is not signed: Windows may warn about an unknown publisher — "More info" → "Run anyway".
3. Start the game through HD_Launcher. **F12** — tune the tube over the game, **F11** — effect on/off.

The F12 panel speaks the game's language (else that of Windows, else English); its **EN / RU** buttons switch it at once and the choice is kept.

Run the setup again after an HD mod update (it may delete `ddraw.dll`); your tube settings and the panel language are kept. "Uninstall" in the same window puts back the files it replaced and the HD mod settings it switched (unless you changed them yourself since); your tube settings are deleted with it.

See the [README](https://github.com/priangle/crt-emu#readme) for details and known issues.

## Files
- `crt-emu-setup-{version}.exe` — the setup. SHA-256 `{sha_setup}`
- `crt-emu-{version}.zip` — the same files for a manual install: unpack into the game folder next to `h3hota HD.exe` and follow "Manual install" in `Shaders/crt-emu/README.txt`. Unlike the setup, it does not keep your tube settings (they live in the `.pass1` shader file it replaces) and does not switch the HD mod renderer or system cursors. SHA-256 `{sha_zip}`
- `SHA256SUMS.txt` — the two checksums above.
- The "Source code" archives below do not include the cnc-ddraw submodule ([priangle/cnc-ddraw](https://github.com/priangle/cnc-ddraw), branch `crt-emu`, commit `{fork}`). To build from source, `git clone --recurse-submodules`.

{built_by}

crt-emu is MIT-licensed; it includes a modified [cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw) and [Dear ImGui](https://github.com/ocornut/imgui), both MIT.
