# The crt-emu tube model (formerly PC-CRT), version 2

The source of truth for the parameters is `src/params.json` (name, group, label, hint, range) and
`src/presets.json`. This document covers how the model is built and why.

## The chain, in the order of a real TV or monitor
1. **Signal (in gamma space):** noise (`NOISE`, changes every frame) → horizontal bandwidth for each gun separately. It is a Gaussian spot integrated over the pixel through erf (`H_SIGMA`), with a high-frequency boost (`H_PEAKING`, a light rim on contrasty edges). Then composite colour bleed (`COMPOSITE`: chroma is wider than luma and lags behind it) and saturation (`SATURATION`).
2. **Tube (in linear light):** the tube's gamma (`CRT_GAMMA`). Each line is a Gaussian beam whose width grows with the current (`BEAM_MIN` → `BEAM_MAX`, curve `BEAM_SHAPE`). The beam is integrated over the physical display pixel, so there is no ripple at 4x. Gun convergence: `CONV_R`, `CONV_B`.
3. **Gaps between pixels** (`PIXEL_GAP`, `GAP_WIDTH`): a band at the right and bottom edge of each game pixel, also integrated over the physical pixel. At 4x and a width of 0.25 this is exactly one display pixel. This is a stylisation: a real tube has no gaps in the horizontal direction.
4. **Phosphor mask** (`MASK_TYPE` 0–6) in the physical display pixels: a 2/3 px aperture grille (Trinitron), a 2 px shadow mask, a 3 px slot mask, 4 px TV masks with a gap. `MASK_DARK` is the brightness of the dimmed dots, `MASK_COMP` is how much of the lost brightness to give back.
5. **Light:** near phosphor glow (`GLOW`, only from bright dots) and a wide haze in the glass (`HALATION`, a separate 13x13 pass, σ = 3). Then the greyness of the glass (`BLACK_LEVEL`), the white point (`TEMPERATURE`), corner darkening (`VIGNETTE`), brightness (`BRIGHTNESS`).
6. **Overexposure:** overdriven dots spread towards white (`SPILL`), a soft shoulder on the brightest channel that keeps the hue, so that overexposed orange stays orange instead of turning yellow. The output is in the monitor's gamma (`OUT_GAMMA`).

## Why
- **The mask is tied to the display, not to the game:** in a tube the triad pitch does not depend on the signal resolution. On 5K (218 ppi) a 3-pixel grille ≈ 0.35 mm, like the monitors of the 90s.
- **Integer scale (4x):** with a fractional factor the lines land unevenly, and a "wave" shows in a close-up.
- **Restrained glow:** the tester asked twice to weaken it. GLOW 0.06 and HALATION 0.035 are already half of the original values.

## Calibration against photos
`refs/` is local only and not in the repository: third-party photos and game frames.
- `refs/photos/` — photos of real CRTs next to an LCD. `refs/src/` — the source pixel grid reconstructed from the photos (`test/depixel.py`).
- `python test/calibrate.py` renders each source with a preset and assembles a sheet "source | crt-emu | photo". The latest sheet is `refs/calibration-sheet.png`. The presets were tuned against it.
- Presets: Trinitron TV (default), Slot-mask TV, Soft composite, Arcade cabinet, Trinitron monitor 21″, Office monitor 17″.

## Build targets
cnc-ddraw (GLSL 130/150, `#define` or `PARAMETER_UNIFORM`), ShaderGlass/RetroArch (`.slang` + `.slangp`, two passes). Both are built from the same `core.glsl`: `build.py` only adds the wrapper code.
