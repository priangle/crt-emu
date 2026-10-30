crt-emu - a CRT tube for Heroes of Might and Magic III HD
=========================================================

What is included
  ddraw.dll                                      cnc-ddraw 7.1.0.1, crt-emu build
                                                 (fixed for Windows scaling above 100%,
                                                 tested at 200%)
  ddraw.ini                                      cnc-ddraw settings
  Shaders/crt-emu/crt-emu-pass1scale.glsl        pass 1: light scattered in the glass
  Shaders/crt-emu/crt-emu-pass1scale.glsl.pass1  pass 2: the tube (settings live here)
  Shaders/crt-emu/crt-emu-lite.glsl              fallback single-pass version
  crt-emu-LICENSE.txt                            licence of crt-emu (MIT)
  cnc-ddraw-LICENSE.txt, imgui-LICENSE.txt       licences of cnc-ddraw and Dear ImGui (MIT)

Install with the setup program (easiest)
  Close the game and HD_Launcher and run crt-emu-setup.exe. It finds the game
  (or pick the folder with "Browse..."), puts cnc-ddraw, the shader and
  ddraw.ini in place and switches the HD mod to "16-bit DirectDraw (original)".
  An HD mod update may delete ddraw.dll - just run the setup again, your tube
  settings are kept. The same window has an "Uninstall" button: it puts back
  the files the setup replaced and the HD mod settings it switched (unless
  you changed them yourself since) and deletes your tube settings too.
  The first line of the window is the language of the setup (English or
  Русский). The F12 panel in the game speaks the game's language (else that
  of Windows, else English); the EN and RU buttons in the panel switch it at
  once, and the choice is kept.
  Windows may warn about an unknown publisher:
  "More info" -> "Run anyway".

Manual install
  1. Copy the files into the game folder next to "h3hota HD.exe".
     If ddraw.dll and ddraw.ini are already there, replace them.
  2. HD_Launcher:
       Renderer          - 16-bit DirectDraw (original)
       Full screen       - on (cnc-ddraw makes the borderless full-screen
                           window itself, see ddraw.ini; F4 switches between
                           window and full screen)
       System cursors    - off
       Source size       - this is the "tube mode". The game is scaled by a
                           whole number (boxing=true in ddraw.ini); on
                           5120x2880:
                           1280x720  - 4x, full 16:9 screen without borders
                           960x720   - 4x, 4:3 at full height
                           800x600   - 4x, with a black border
                           1024x768  - 3x
  3. Start the game through HD_Launcher.
     If you get a black screen instead of the picture, switch ddraw.ini to
     crt-emu-lite.glsl (everything except the wide glow in the glass).

  In the game: F12 - the shader panel over the game: sliders act live,
                     "Save" writes the values into the shader file (keyosd in ddraw.ini);
                     "Magnifier" in the panel shows the screen's pixels up close
                     (drag it with the mouse, the wheel over it zooms),
               F11 - shader on/off (keytoggleshader),
               PrintScreen - a frame without the shader into the Screenshots folder.
  To undo: delete ddraw.dll.
  HD mod updates may remove ddraw.dll from the folder - then put it back.

Why a custom cnc-ddraw build
  In "16-bit DirectDraw" mode the HD mod switches the game's window thread to
  "DPI unaware". With Windows scaling above 100% the system then stretches the
  window itself while cnc-ddraw draws real pixels: every other pixel is dropped
  (the tube mask turns green) and the mouse reaches only part of the screen.
  The crt-emu build blocks that switch (key fix_dpi_unaware in ddraw.ini).

Brightness
  A phosphor mask and scanlines take light away, as on a real tube. If the
  picture is too dark, raise the monitor's own brightness first and keep the
  shader's Brightness moderate, so that highlights are not burnt out.

Tuning
  Everything is tuned in the game: press F12, move the sliders, press "Save".
  The values are stored in the "#define" block of crt-emu-pass1scale.glsl.pass1,
  and the setup program keeps them when you reinstall.
