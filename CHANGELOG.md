# Changelog

The release text on GitHub takes the section of its version from here (`tools/release.py`).

## 2.2.1
- Releases are built by GitHub Actions from the tag. `ddraw.dll` is built from the same sources
  with the same compiler as in 2.2.0 and differs from it only in the build timestamp.
- New release file `crt-emu-<version>.zip`: the files the setup installs, for a manual install.
- The setup's manifest carries its real version (2.2.0 still said 2.1.0.0 there).
- No changes to the tube, the F12 panel or what the setup does.

## 2.2.0
- EN / RU buttons in the F12 panel switch its language at once; the choice is kept.
- The panel speaks the game's language (else that of Windows, else English); the setup follows
  Windows (or your choice in its first line) and no longer sets the panel's language.

## 2.1.0
- First public build: the CRT tube shader, a cnc-ddraw build with the F12 panel over the game,
  and the setup.
