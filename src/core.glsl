// ======================================================================
//  crt-emu 2 core (main pass) — shared by the cnc-ddraw and slang builds.
//
//  The target provides before this block:
//    vec3 src_texel(vec2 ip)  - sRGB signal of game pixel ip (integer coords, clamped)
//    vec3 hal_texel(vec2 ip)  - pass-1 halation texel (only with HAS_HALATION)
//    SRC_SIZE, OUT_SIZE       - game frame size and viewport size, in pixels
//    FRAME                    - frame counter (float), for noise
//    all parameters from params.json as plain names
//
//  Signal chain, in the order a real set processes it:
//    signal (gamma space): noise -> per-gun horizontal bandwidth + peaking
//      -> composite chroma bleed -> saturation
//    tube: gamma -> gaussian scanline per gun, width grows with beam current,
//      integrated over the physical pixel -> phosphor mask
//    light: near glow of the phosphors + wide halation in the glass
//      -> raised black of the glass -> white point -> vignette
//      -> over-driven phosphors spill toward white, soft shoulder
// ======================================================================

#define CRT_LUMA vec3(0.299, 0.587, 0.114)

#ifndef MASK_SCALE
#define MASK_SCALE 1.0
#endif

vec4 crt_erf4(vec4 x)
{
    vec4 x2 = x * x;
    vec4 ax2 = 0.147 * x2;
    return sign(x) * sqrt(max(vec4(1.0) - exp(-x2 * (1.2732395 + ax2) / (1.0 + ax2)), vec4(0.0)));
}

vec3 crt_erf3(vec3 x)
{
    return crt_erf4(vec4(x, 0.0)).xyz;
}

float crt_hash(vec3 p)
{
    p = fract(p * vec3(0.1031, 0.1030, 0.0973));
    p += dot(p, p.yzx + 33.33);
    return fract((p.x + p.y) * p.z);
}

// Area of each source pixel [c-1 .. c+2] under a gaussian beam centred at x.
vec4 crt_hw(float x, float c, float sigma)
{
    float s = 0.70710678 / sigma;
    vec4 bl = (vec4(c - 1.0, c, c + 1.0, c + 2.0) - vec4(x)) * s;
    vec4 w = crt_erf4(bl + vec4(s)) - crt_erf4(bl);
    return w / max(dot(w, vec4(1.0)), 1e-5);
}

vec4 crt_hweights(float x, float c)
{
    vec4 w = crt_hw(x, c, H_SIGMA);
    if (H_PEAKING > 0.0)
        w = w * (1.0 + H_PEAKING) - crt_hw(x, c, H_SIGMA * 2.5) * H_PEAKING;
    return w;
}

// Normalised gaussian over the 8 taps [c-3 .. c+4].
void crt_gauss8(float x, float c, float sigma, out vec4 a, out vec4 b)
{
    vec4 ka = vec4(c - 3.0, c - 2.0, c - 1.0, c) + vec4(0.5 - x);
    vec4 kb = ka + vec4(4.0);
    float k = -0.5 / (sigma * sigma);
    a = exp(ka * ka * k);
    b = exp(kb * kb * k);
    float n = dot(a, vec4(1.0)) + dot(b, vec4(1.0));
    a /= n;
    b /= n;
}

vec3 crt_lin(vec3 c)
{
    return pow(max(c, vec3(0.0)), vec3(CRT_GAMMA));
}

// Only bright light blooms: dark and mid tones keep their black surroundings.
vec3 crt_bright(vec3 l)
{
    return l * smoothstep(0.12, 0.75, dot(l, CRT_LUMA));
}

vec3 crt_tap(vec2 ip)
{
    vec3 t = src_texel(ip);
    if (NOISE > 0.0)
        t += vec3((crt_hash(vec3(ip, mod(FRAME, 4096.0))) - 0.5) * NOISE);
    return t;
}

vec3 crt_chroma(vec3 t)
{
    return t - vec3(dot(t, CRT_LUMA));
}

// One scanline: returns the linear colour the beam carries at x; accumulates near glow.
vec3 crt_line(float l, float c, vec4 wr, vec4 wg, vec4 wb, vec4 ca, vec4 cb,
              vec4 ga, vec4 gb, float gy, inout vec3 glow)
{
    vec3 t0 = crt_tap(vec2(c - 3.0, l));
    vec3 t1 = crt_tap(vec2(c - 2.0, l));
    vec3 t2 = crt_tap(vec2(c - 1.0, l));
    vec3 t3 = crt_tap(vec2(c,       l));
    vec3 t4 = crt_tap(vec2(c + 1.0, l));
    vec3 t5 = crt_tap(vec2(c + 2.0, l));
    vec3 t6 = crt_tap(vec2(c + 3.0, l));
    vec3 t7 = crt_tap(vec2(c + 4.0, l));

    // video amplifier bandwidth, per gun (misconvergence shifts each gun)
    vec3 s = vec3(dot(wr, vec4(t2.r, t3.r, t4.r, t5.r)),
                  dot(wg, vec4(t2.g, t3.g, t4.g, t5.g)),
                  dot(wb, vec4(t2.b, t3.b, t4.b, t5.b)));

    // composite video: chroma carried at a fraction of the luma bandwidth
    vec3 cw = crt_chroma(t0) * ca.x + crt_chroma(t1) * ca.y + crt_chroma(t2) * ca.z + crt_chroma(t3) * ca.w
            + crt_chroma(t4) * cb.x + crt_chroma(t5) * cb.y + crt_chroma(t6) * cb.z + crt_chroma(t7) * cb.w;
    float y = dot(s, CRT_LUMA);
    vec3 sig = vec3(y) + mix(s - vec3(y), cw, COMPOSITE) * SATURATION;

    if (GLOW > 0.0)
        glow += (crt_bright(crt_lin(t0)) * ga.x + crt_bright(crt_lin(t1)) * ga.y
               + crt_bright(crt_lin(t2)) * ga.z + crt_bright(crt_lin(t3)) * ga.w
               + crt_bright(crt_lin(t4)) * gb.x + crt_bright(crt_lin(t5)) * gb.y
               + crt_bright(crt_lin(t6)) * gb.z + crt_bright(crt_lin(t7)) * gb.w) * gy;

    return crt_lin(sig);
}

// Normalised gaussian scanline profile averaged over the pixel footprint [d-h, d+h].
vec3 crt_beam(vec3 col, float d, float h)
{
    vec3 c = max(col, vec3(0.0));
    vec3 sigma = mix(vec3(BEAM_MIN), vec3(BEAM_MAX), pow(min(c, vec3(1.0)), vec3(BEAM_SHAPE)));
    vec3 s = 0.70710678 / sigma;
    return c * (crt_erf3((d + h) * s) - crt_erf3((d - h) * s)) / (4.0 * h);
}

vec3 crt_rgb3(float a, float d)
{
    return (a < 0.5) ? vec3(1.0, d, d) : ((a < 1.5) ? vec3(d, 1.0, d) : vec3(d, d, 1.0));
}

// Phosphor pattern in physical screen pixels.
vec3 crt_mask(vec2 fc)
{
    vec2 p = floor(fc / MASK_SCALE);
    float d = MASK_DARK;
    float t = MASK_TYPE;
    vec3 m = vec3(1.0);
    if (t > 0.5 && t < 1.5)            // aperture grille 2 px, magenta/green (0.23 mm at 218 ppi)
        m = (mod(p.x, 2.0) < 0.5) ? vec3(1.0, d, 1.0) : vec3(d, 1.0, d);
    else if (t > 1.5 && t < 2.5)       // aperture grille 3 px RGB
        m = crt_rgb3(mod(p.x, 3.0), d);
    else if (t > 2.5 && t < 3.5)       // fine shadow mask, staggered magenta/green dots
        m = (mod(p.x + p.y, 2.0) < 0.5) ? vec3(1.0, d, 1.0) : vec3(d, 1.0, d);
    else if (t > 3.5 && t < 4.5)       // slot mask 3 px, slots 3 rows + 1 gap, brick offset
    {
        m = crt_rgb3(mod(p.x, 3.0), d);
        if (mod(p.y + 2.0 * mod(floor(p.x / 3.0), 2.0), 4.0) > 2.5) m *= d;
    }
    else if (t > 4.5 && t < 5.5)       // TV slot mask 4 px: R G B + dark gap, brick offset
    {
        float a = mod(p.x, 4.0);
        m = (a < 2.5) ? crt_rgb3(a, d) : vec3(d);
        if (mod(p.y + 2.0 * mod(floor(p.x / 4.0), 2.0), 4.0) > 2.5) m *= d;
    }
    else if (t > 5.5)                  // TV aperture grille 4 px: R G B + dark stripe
    {
        float a = mod(p.x, 4.0);
        m = (a < 2.5) ? crt_rgb3(a, d) : vec3(d);
    }
    return m;
}

float crt_mask_mean()
{
    float d = MASK_DARK;
    float t = MASK_TYPE;
    if (t < 0.5) return 1.0;
    if (t < 1.5) return 0.5 * (1.0 + d);
    if (t < 2.5) return (1.0 + 2.0 * d) / 3.0;
    if (t < 3.5) return 0.5 * (1.0 + d);
    if (t < 4.5) return (1.0 + 2.0 * d) / 3.0 * (3.0 + d) * 0.25;
    if (t < 5.5) return (1.0 + 3.0 * d) * 0.25 * (3.0 + d) * 0.25;
    return (1.0 + 3.0 * d) * 0.25;
}

#ifdef HAS_HALATION
vec3 crt_halation(vec2 pos)
{
    vec2 p = pos - vec2(0.5);
    vec2 i = floor(p);
    vec2 f = p - i;
    vec3 a = hal_texel(i);
    vec3 b = hal_texel(i + vec2(1.0, 0.0));
    vec3 c = hal_texel(i + vec2(0.0, 1.0));
    vec3 e = hal_texel(i + vec2(1.0, 1.0));
    vec3 v = mix(mix(a, b, f.x), mix(c, e, f.x), f.y);
    return v * v;
}
#endif

vec3 crt_white(float t)
{
    // t > 0: warmer (towards ~5000 K), t < 0: colder (consumer sets ran 9300 K)
    return (t >= 0.0) ? mix(vec3(1.0), vec3(1.0, 0.90, 0.74), t)
                      : mix(vec3(1.0), vec3(0.80, 0.90, 1.0), -t);
}

vec3 crt_tonemap(vec3 c)
{
    // over-driven phosphor dots bleed light into their neighbours: hot cores go white
    vec3 ex = max(c - vec3(1.0), vec3(0.0));
    c += vec3(ex.r + ex.g + ex.b) * SPILL * 0.5;
    // hue-preserving soft shoulder: compress by the brightest channel, keep the ratios,
    // so an over-driven orange stays orange instead of clipping toward yellow-white
    float m = max(max(c.r, c.g), c.b);
    const float k = 0.8;
    if (m > k)
        c *= (k + (1.0 - k) * (1.0 - exp(-(m - k) / (1.0 - k)))) / m;
    return clamp(c, 0.0, 1.0);
}

// share of the physical pixel [p - f/2, p + f/2] that falls into the gaps: a dark band of
// width GAP_WIDTH at the right/bottom edge of every game pixel. Integrated analytically, so
// at 4x and GAP_WIDTH 0.25 the band is exactly one crisp physical pixel and it stays
// alias-free at fractional scales.
float crt_gap_cov(float p, float f)
{
    float g = GAP_WIDTH;
    float a = p - 0.5 * f, b = p + 0.5 * f;
    float A = floor(a) * g + max(fract(a) - (1.0 - g), 0.0);
    float B = floor(b) * g + max(fract(b) - (1.0 - g), 0.0);
    return (B - A) / f;
}

vec2 crt_gap(vec2 pos)
{
    vec2 f = SRC_SIZE / OUT_SIZE;
    return vec2(1.0) - PIXEL_GAP * vec2(crt_gap_cov(pos.x, f.x), crt_gap_cov(pos.y, f.y));
}

// pos: continuous position in game pixels (0..SRC_SIZE), fc: physical output pixel
vec3 crt_shade(vec2 pos, vec2 fc)
{
    float c  = floor(pos.x - 0.5);
    float cl = floor(pos.y - 0.5);

    vec4 wr = crt_hweights(pos.x - CONV_R, c);
    vec4 wg = crt_hweights(pos.x, c);
    vec4 wb = crt_hweights(pos.x - CONV_B, c);

    vec4 ca, cb, ga, gb;
    crt_gauss8(pos.x - 0.35 * COMPOSITE, c, 1.0 + 0.8 * COMPOSITE, ca, cb);   // chroma lags and smears
    crt_gauss8(pos.x, c, 0.85, ga, gb);                                          // near glow

    vec4 ly = vec4(cl - 1.0, cl, cl + 1.0, cl + 2.0);
    vec4 dy = vec4(pos.y) - (ly + vec4(0.5));
    vec4 gy = exp(-dy * dy * 0.8);
    gy /= dot(gy, vec4(1.0));

    float h = 0.5 * SRC_SIZE.y / OUT_SIZE.y;

    vec3 glow = vec3(0.0);
    vec3 l0 = crt_line(ly.x, c, wr, wg, wb, ca, cb, ga, gb, gy.x, glow);
    vec3 l1 = crt_line(ly.y, c, wr, wg, wb, ca, cb, ga, gb, gy.y, glow);
    vec3 l2 = crt_line(ly.z, c, wr, wg, wb, ca, cb, ga, gb, gy.z, glow);
    vec3 l3 = crt_line(ly.w, c, wr, wg, wb, ca, cb, ga, gb, gy.w, glow);

    vec3 col = crt_beam(l0, dy.x, h) + crt_beam(l1, dy.y, h)
             + crt_beam(l2, dy.z, h) + crt_beam(l3, dy.w, h);

    vec2 gap = crt_gap(pos);
    float gap_mean = (1.0 - PIXEL_GAP * GAP_WIDTH) * (1.0 - PIXEL_GAP * GAP_WIDTH);
    col *= gap.x * gap.y;
    col *= crt_mask(fc) * mix(1.0, 1.0 / (crt_mask_mean() * gap_mean), MASK_COMP);
    col += glow * GLOW;
#ifdef HAS_HALATION
    col += crt_halation(pos) * HALATION;
#endif
    col += vec3(BLACK_LEVEL);
    col *= crt_white(TEMPERATURE);

    vec2 uv = pos / SRC_SIZE - vec2(0.5);
    float r = dot(uv, uv) * 2.0;
    col *= (1.0 - VIGNETTE * r * sqrt(r)) * BRIGHTNESS;

    return pow(crt_tonemap(col), vec3(1.0 / OUT_GAMMA));
}
// ======================================================================
