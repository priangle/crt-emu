#!/usr/bin/env python3
"""Generate crt-emu 2 for every target from src/core.glsl, src/halation.glsl, src/params.json.

out/cnc-ddraw/Shaders/crt-emu/
    crt-emu-pass1scale.glsl         pass 1: glass halation at game resolution
    crt-emu-pass1scale.glsl.pass1   pass 2: the tube (settings live here)
    crt-emu-lite.glsl               single pass, everything except the wide halation
out/shaderglass/  crt-emu-halation.slang, crt-emu.slang, crt-emu.slangp   (ShaderGlass, RetroArch)

cnc-ddraw runs a second file "<shader>.pass1" when it exists; "-pass1scale" in the name
makes it run the first pass at game resolution and feed pass 2 both textures:
Texture = pass-1 output, PassPrev2Texture = the original frame.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
VERSION = "2.0"


def read(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


def fmt(v, step=0.01):
    d = 3 if step < 0.01 else 2
    return f"{float(v):.{d}f}"


HEADER = """// crt-emu {ver} - CRT simulation for HoMM3 HD and other 2D games  ({part})
// Copyright (c) 2026 priangle - MIT License - https://github.com/priangle/crt-emu
// SPDX-License-Identifier: MIT
// -------------------------------------------------------------------------------
// Consumer-tube look on a high-density panel: beam-current-dependent gaussian
// scanlines integrated over each physical pixel, video bandwidth + peaking,
// composite chroma bleed, phosphor masks in physical screen pixels, phosphor glow,
// glass halation, hot-phosphor spill, raised glass black, white point, vignette, noise.
// Tuned for 27" 5K (218 ppi); game resolution 800x600 or 1280x720.
// -------------------------------------------------------------------------------
"""

GLSL_VERTEX = """#if defined(VERTEX)

#if __VERSION__ >= 130
#define COMPAT_VARYING out
#define COMPAT_ATTRIBUTE in
#else
#define COMPAT_VARYING varying
#define COMPAT_ATTRIBUTE attribute
#endif

COMPAT_ATTRIBUTE vec4 VertexCoord;
COMPAT_ATTRIBUTE vec4 TexCoord;
COMPAT_VARYING vec4 TEX0;
uniform mat4 MVPMatrix;

void main()
{
    gl_Position = MVPMatrix * VertexCoord;
    TEX0 = TexCoord;
}

#elif defined(FRAGMENT)

#if __VERSION__ >= 130
#define COMPAT_VARYING in
#define COMPAT_TEXTURE texture
out vec4 FragColor;
#else
#define COMPAT_VARYING varying
#define COMPAT_TEXTURE texture2D
#define FragColor gl_FragColor
#endif

#ifdef GL_ES
precision highp float;
#define COMPAT_PRECISION highp
#else
#define COMPAT_PRECISION
#endif
"""


def pragmas(params):
    return "\n".join(
        f'#pragma parameter {p["name"]} "{p["en"]}" {fmt(p["def"], p["step"])} {fmt(p["min"], p["step"])} '
        f'{fmt(p["max"], p["step"])} {fmt(p["step"], p["step"])}' for p in params)


GROUP_RU = {"signal": "Сигнал", "beam": "Луч и строки", "mask": "Маска люминофора",
            "light": "Свечение", "screen": "Экран"}
GROUP_EN = {"signal": "Signal", "beam": "Beam and scanlines", "mask": "Phosphor mask",
            "light": "Glow", "screen": "Screen"}
PRESETS = []

# panel texts per language: (groups, param label / hint / options keys, preset name key)
LANGS = {
    "en": (GROUP_EN, "label_en", "hint_en", "options_en", "name_en"),
    "ru": (GROUP_RU, "ru", "hint", "options", "name"),
}


def check(params, presets):
    """Every panel text exists in both languages and fits the '|'-separated metadata lines."""
    assert GROUP_EN.keys() == GROUP_RU.keys(), "GROUP_EN and GROUP_RU must have the same groups"
    texts = list(GROUP_EN.values()) + list(GROUP_RU.values())
    for p in params:
        for k in ("label_en", "hint_en"):
            assert p.get(k), f"params.json: {p['name']} has no {k}"
        assert p["group"] in GROUP_RU, f"params.json: {p['name']} has unknown group {p['group']}"
        if p.get("options"):
            assert len(p.get("options_en", [])) == len(p["options"]), \
                f"params.json: {p['name']} needs options_en with {len(p['options'])} entries"
        texts += [p["ru"], p["hint"], p["label_en"], p["hint_en"], *p.get("options", []), *p.get("options_en", [])]
    for pr in presets:
        for k in ("name_en", "note_en"):
            assert pr.get(k), f"presets.json: {pr['id']} has no {k}"
        texts += [pr["name"], pr["note"], pr["name_en"], pr["note_en"]]
    for t in texts:
        assert "|" not in t and "\n" not in t, f"'|' or a line break in a panel text: {t!r}"


def osd_meta(params):
    """Comment block read by the in-game panel of the crt-emu cnc-ddraw build (F12).
    One record per line, fields separated by '|'. Plain comments for every other loader.
    "//@lang|xx" starts the records of one language; the panel keeps only the block of its
    language (records before the first "//@lang" would count for all of them). A panel older
    than the blocks reads both and mixes the languages (presets listed twice): this shader
    needs the panel of the same release, which the setup installs with it."""
    lines = ["// ---- in-game panel (cnc-ddraw crt-emu build, F12): groups, labels, presets ----"]
    for lang, (groups, label, hint, options, name) in LANGS.items():
        lines.append(f"//@lang|{lang}")
        lines += [f"//@group|{g}|{t}" for g, t in groups.items()]
        for p in params:
            lines.append(f"//@param|{p['name']}|{p['group']}|{p[label]}|{p[hint]}")
            if p.get(options):
                lines.append(f"//@options|{p['name']}|" + "|".join(p[options]))
        for pr in PRESETS:
            vals = ";".join(f"{k}={v:g}" for k, v in pr["v"].items())
            lines.append(f"//@preset|{pr['id']}|{pr[name]}|{vals}")
    text = "\n".join(lines)
    assert all(t.count("|") >= (1 if t.startswith("//@lang|") else 2) for t in lines[1:])
    return text


def settings_block(params):
    uniforms = "\n".join(f"uniform COMPAT_PRECISION float {p['name']};" for p in params)
    defines = "\n".join(f"#define {p['name']:<12} {fmt(p['def'], p['step']):>6}   // {p['en']}" for p in params)
    return f"""#ifdef PARAMETER_UNIFORM
{uniforms}
#else
// ---- settings (edit these, or tune them in the game with F12 and press Save) ----
{defines}
#endif
"""


def glsl_halation(hal):
    return f"""#version 130
{HEADER.format(ver=VERSION, part="pass 1 of 2: glass halation")}
{GLSL_VERTEX}
uniform COMPAT_PRECISION vec2 TextureSize;
uniform COMPAT_PRECISION vec2 InputSize;
uniform sampler2D Texture;
COMPAT_VARYING vec4 TEX0;

vec3 src_texel(vec2 ip)
{{
    ip = clamp(ip, vec2(0.0), InputSize - vec2(1.0));
    return COMPAT_TEXTURE(Texture, (ip + vec2(0.5)) / TextureSize).rgb;
}}

{hal}
void main()
{{
    FragColor = vec4(hal_shade(floor(TEX0.xy * TextureSize)), 1.0);
}}

#endif
"""


def glsl_main(params, core, two_pass):
    part = "pass 2 of 2: the tube - settings are here" if two_pass else "single pass, no wide halation"
    if two_pass:
        io = """uniform sampler2D Texture;            // pass-1 halation, game resolution
uniform sampler2D PassPrev2Texture;   // original frame
#define HAS_HALATION
vec3 src_texel(vec2 ip)
{
    ip = clamp(ip, vec2(0.0), InputSize - vec2(1.0));
    return COMPAT_TEXTURE(PassPrev2Texture, (ip + vec2(0.5)) / TextureSize).rgb;
}
vec3 hal_texel(vec2 ip)
{
    ip = clamp(ip, vec2(0.0), InputSize - vec2(1.0));
    return COMPAT_TEXTURE(Texture, (ip + vec2(0.5)) / TextureSize).rgb;
}"""
    else:
        io = """uniform sampler2D Texture;
vec3 src_texel(vec2 ip)
{
    ip = clamp(ip, vec2(0.0), InputSize - vec2(1.0));
    return COMPAT_TEXTURE(Texture, (ip + vec2(0.5)) / TextureSize).rgb;
}"""
    return f"""#version 130
{HEADER.format(ver=VERSION, part=part)}
{pragmas(params)}

{osd_meta(params)}

{GLSL_VERTEX}
uniform COMPAT_PRECISION vec2 OutputSize;
uniform COMPAT_PRECISION vec2 TextureSize;
uniform COMPAT_PRECISION vec2 InputSize;
uniform int FrameCount;
COMPAT_VARYING vec4 TEX0;

{settings_block(params)}
#define SRC_SIZE InputSize
#define OUT_SIZE OutputSize
#define FRAME float(FrameCount)

{io}

{core}
void main()
{{
    vec2 pos = TEX0.xy * TextureSize;
#ifdef DEBUG_SPLIT
    // diagnostic: left half shows the raw game frame, right half the tube
    if (pos.x < SRC_SIZE.x * 0.5)
    {{
        FragColor = vec4(src_texel(floor(pos)), 1.0);
        return;
    }}
#endif
    FragColor = vec4(crt_shade(pos, gl_FragCoord.xy), 1.0);
}}

#endif
"""


SLANG_HEAD = """#version 450
{header}
layout(push_constant) uniform Push
{{
    vec4 SourceSize;
    vec4 OriginalSize;
    vec4 OutputSize;
    uint FrameCount;
}} params;
"""

SLANG_VERT = """
#pragma stage vertex
layout(location = 0) in vec4 Position;
layout(location = 1) in vec2 TexCoord;
layout(location = 0) out vec2 vTexCoord;

void main()
{
    gl_Position = global.MVP * Position;
    vTexCoord = TexCoord;
}
"""


def slang_halation(hal):
    return SLANG_HEAD.format(header=HEADER.format(ver=VERSION, part="pass 1 of 2: glass halation")) + """
layout(std140, set = 0, binding = 0) uniform UBO
{
    mat4 MVP;
} global;
""" + SLANG_VERT + f"""
#pragma stage fragment
layout(location = 0) in vec2 vTexCoord;
layout(location = 0) out vec4 FragColor;
layout(set = 0, binding = 2) uniform sampler2D Source;

vec3 src_texel(vec2 ip)
{{
    ip = clamp(ip, vec2(0.0), params.SourceSize.xy - vec2(1.0));
    return texture(Source, (ip + vec2(0.5)) * params.SourceSize.zw).rgb;
}}

{hal}
void main()
{{
    FragColor = vec4(hal_shade(floor(vTexCoord * params.SourceSize.xy)), 1.0);
}}
"""


def slang_main(params, core):
    ubo = "\n".join(f"    float {p['name']};" for p in params)
    defines = "\n".join(f"#define {p['name']} global.{p['name']}" for p in params)
    return SLANG_HEAD.format(header=HEADER.format(ver=VERSION, part="pass 2 of 2: the tube")) + f"""
layout(std140, set = 0, binding = 0) uniform UBO
{{
    mat4 MVP;
{ubo}
}} global;

{pragmas(params)}

{defines}
#define SRC_SIZE params.OriginalSize.xy
#define OUT_SIZE params.OutputSize.xy
#define FRAME float(params.FrameCount)
#define HAS_HALATION
""" + SLANG_VERT + f"""
#pragma stage fragment
layout(location = 0) in vec2 vTexCoord;
layout(location = 0) out vec4 FragColor;
layout(set = 0, binding = 2) uniform sampler2D Source;     // pass-1 halation
layout(set = 0, binding = 3) uniform sampler2D Original;   // original frame

vec3 src_texel(vec2 ip)
{{
    ip = clamp(ip, vec2(0.0), params.OriginalSize.xy - vec2(1.0));
    return texture(Original, (ip + vec2(0.5)) * params.OriginalSize.zw).rgb;
}}
vec3 hal_texel(vec2 ip)
{{
    ip = clamp(ip, vec2(0.0), params.SourceSize.xy - vec2(1.0));
    return texture(Source, (ip + vec2(0.5)) * params.SourceSize.zw).rgb;
}}

{core}
void main()
{{
    FragColor = vec4(crt_shade(vTexCoord * params.OriginalSize.xy, gl_FragCoord.xy), 1.0);
}}
"""


SLANGP = """shaders = 2

shader0 = crt-emu-halation.slang
scale_type0 = source
scale0 = 1.0
filter_linear0 = false

shader1 = crt-emu.slang
scale_type1 = viewport
filter_linear1 = false
"""


def main():
    params = json.loads(read("src", "params.json"))
    PRESETS[:] = json.loads(read("src", "presets.json"))
    check(params, PRESETS)
    core, hal = read("src", "core.glsl"), read("src", "halation.glsl")
    for arg in sys.argv[1:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            for p in params:
                if p["name"] == k:
                    p["def"] = float(v)
    files = {
        "cnc-ddraw/Shaders/crt-emu/crt-emu-pass1scale.glsl": glsl_halation(hal),
        "cnc-ddraw/Shaders/crt-emu/crt-emu-pass1scale.glsl.pass1": glsl_main(params, core, True),
        "cnc-ddraw/Shaders/crt-emu/crt-emu-lite.glsl": glsl_main(params, core, False),
        "shaderglass/crt-emu-halation.slang": slang_halation(hal),
        "shaderglass/crt-emu.slang": slang_main(params, core),
        "shaderglass/crt-emu.slangp": SLANGP,
    }
    for name, text in files.items():
        path = os.path.join(OUT, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print("built", len(files), "files")


if __name__ == "__main__":
    main()
