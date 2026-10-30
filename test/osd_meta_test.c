/* Driver for test/osd_meta_test.py: loads a shader into the F12 panel (crtemu_osd.cpp built with
 * CRTEMU_OSD_TEST; nothing is drawn, so no GL is needed) and prints what the panel would show,
 * one "kind<TAB>index<TAB>text" line per item. */
#include <stdio.h>

void crtemu_osd_load(const char* shader_path);
const char* crtemu_osd_param_name(int i);
const char* crtemu_osd_test_lang(void);
int crtemu_osd_test_count(int what);
const char* crtemu_osd_test_label(int i);
const char* crtemu_osd_test_hint(int i);
const char* crtemu_osd_test_option(int i, int k);
const char* crtemu_osd_test_group(int i);
const char* crtemu_osd_test_preset(int i);
const char* crtemu_osd_test_ui(int s);

int main(int argc, char** argv)
{
    if (argc < 2) { fprintf(stderr, "usage: osd_meta_test <shader.glsl>\n"); return 2; }
    crtemu_osd_load(argv[1]);
    printf("lang\t0\t%s\n", crtemu_osd_test_lang());
    int np = crtemu_osd_test_count(0), ng = crtemu_osd_test_count(1), npr = crtemu_osd_test_count(2);
    for (int i = 0; i < np; i++)
    {
        printf("name\t%d\t%s\n", i, crtemu_osd_param_name(i));
        printf("label\t%d\t%s\n", i, crtemu_osd_test_label(i));
        printf("hint\t%d\t%s\n", i, crtemu_osd_test_hint(i));
        for (int k = 0; crtemu_osd_test_option(i, k)[0]; k++) printf("option\t%d\t%s\n", i, crtemu_osd_test_option(i, k));
    }
    for (int i = 0; i < ng; i++) printf("group\t%d\t%s\n", i, crtemu_osd_test_group(i));
    for (int i = 0; i < npr; i++) printf("preset\t%d\t%s\n", i, crtemu_osd_test_preset(i));
    for (int s = 0; crtemu_osd_test_ui(s)[0]; s++) printf("ui\t%d\t%s\n", s, crtemu_osd_test_ui(s));
    return 0;
}
