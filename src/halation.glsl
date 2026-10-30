// ======================================================================
//  crt-emu pass 1 — light scattered in the faceplate glass (halation).
//  Runs at game resolution. Wide disc-gaussian blur of the bright light,
//  stored sqrt-encoded so an 8-bit target keeps the dark tails.
//  The target provides: vec3 src_texel(vec2 ip)
// ======================================================================
vec3 hal_shade(vec2 ip)
{
    vec3 acc = vec3(0.0);
    float wsum = 0.0;
    for (int y = -6; y <= 6; y++)
    {
        for (int x = -6; x <= 6; x++)
        {
            float r2 = float(x * x + y * y);
            if (r2 > 42.25) continue;
            float w = exp(-r2 * 0.0555556);          // sigma = 3 game px
            vec3 t = src_texel(ip + vec2(float(x), float(y)));
            vec3 l = t * t;                            // ~linear light (gamma 2)
            acc += l * (w * smoothstep(0.12, 0.75, dot(l, vec3(0.299, 0.587, 0.114))));   // only bright light scatters
            wsum += w;
        }
    }
    return sqrt(acc / wsum);
}
// ======================================================================
