/* Host test for installer/logic.c (any C compiler, no WinAPI):
 *   cc -I installer installer/logic.c installer/test_logic.c -o test_logic
 *   ./test_logic <new.pass1> <old.pass1> <merged.out> <hd-settings.ini> <hd-settings.out>
 * Then: the #define / #pragma parameter values in merged.out must equal old.pass1,
 * every other line must equal new.pass1; hd-settings.out differs only in the two keys. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "logic.h"

static char* rd(const char* p)
{
    FILE* f = fopen(p, "rb");
    if (!f) { perror(p); exit(2); }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    char* b = malloc(n + 1);
    if (fread(b, 1, n, f) != (size_t)n) { perror(p); exit(2); }
    b[n] = 0;
    fclose(f);
    return b;
}

static void wr(const char* p, const char* s)
{
    FILE* f = fopen(p, "wb");
    if (!f) { perror(p); exit(2); }
    fwrite(s, 1, strlen(s), f);
    fclose(f);
}

int main(int argc, char** argv)
{
    if (argc < 6) { fprintf(stderr, "usage: test_logic new.pass1 old.pass1 merged.out hd.ini hd.out\n"); return 2; }
    int merged = 0, changed = 0, fails = 0;
    char* out = crtemu_merge_settings(rd(argv[1]), rd(argv[2]), &merged);
    wr(argv[3], out);
    printf("merged %d settings\n", merged);
    char* hd = rd(argv[4]);
    char* a = crtemu_set_hd_key(hd, "<Graphics.v2.Mode>", "0", &changed);
    char* b = crtemu_set_hd_key(a, "<Graphics.SystemCursors>", "0", &changed);
    wr(argv[5], b);
    printf("hd keys changed %d\n", changed);
    if (strcmp(crtemu_to_crlf("a\nb\r\nc\n"), "a\r\nb\r\nc\r\n") != 0) { puts("FAIL crlf"); fails++; }
    if (!crtemu_contains("xxkeyosdyy", 10, "keyosd") || crtemu_contains("abc", 3, "abcd")) { puts("FAIL contains"); fails++; }
    /* old PC-CRT install: shader paths in ddraw.ini move to Shaders\crt-emu, any case, commented lines too */
    int moved = 0;
    char* ini = crtemu_replace_ci("; PC-CRT build\r\nshader=Shaders\\pc-crt\\pc-crt-pass1scale.glsl\r\n"
                                  ";shader=Shaders\\PC-CRT\\Pc-Crt-lite.glsl\r\nshader=Shaders\\pc-crt\\other.glsl\r\n",
                                  "pc-crt\\pc-crt-", "crt-emu\\crt-emu-", &moved);
    if (moved != 2 || strcmp(ini, "; PC-CRT build\r\nshader=Shaders\\crt-emu\\crt-emu-pass1scale.glsl\r\n"
                                  ";shader=Shaders\\crt-emu\\crt-emu-lite.glsl\r\nshader=Shaders\\pc-crt\\other.glsl\r\n") != 0)
    { puts("FAIL replace"); fails++; }
    /* HD profile values for uninstall: first matching line, spaces and {comment} around the value */
    const char* prof = "<Graphics.v2.Mode.Old> = 7\r\n  <Graphics.v2.Mode>\t=  2  {renderer}\r\n"
                       "<Graphics.SystemCursors> = 1\r\n<Graphics.v2.Mode> = 5\r\n<Broken.Key> 3\r\n";
    char v[8];
    if (!crtemu_get_hd_key(prof, "<Graphics.v2.Mode>", v, sizeof(v)) || strcmp(v, "2") != 0) { puts("FAIL get mode"); fails++; }
    if (!crtemu_get_hd_key(prof, "<Graphics.SystemCursors>", v, sizeof(v)) || strcmp(v, "1") != 0) { puts("FAIL get cursors"); fails++; }
    if (crtemu_get_hd_key(prof, "<Graphics.Missing>", v, sizeof(v)) || crtemu_get_hd_key(prof, "<Broken.Key>", v, sizeof(v)))
    { puts("FAIL get missing"); fails++; }
    if (crtemu_get_hd_key(prof, "<Graphics.v2.Mode>", v, 1)) { puts("FAIL get too long"); fails++; }
    /* the value from the backup goes back with set_hd_key and the line keeps its spacing and comment */
    int back = 0;
    char* undo = crtemu_set_hd_key("<Graphics.v2.Mode>\t=  0  {renderer}\r\n", "<Graphics.v2.Mode>", "2", &back);
    if (back != 1 || strcmp(undo, "<Graphics.v2.Mode>\t=  2  {renderer}\r\n") != 0) { puts("FAIL set back"); fails++; }
    puts(fails ? "FAILED" : "ok");
    return fails != 0;
}
