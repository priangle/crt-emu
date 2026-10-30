/* Driver for test/osd_meta_test.py: loads a shader into the F12 panel (crtemu_osd.cpp built with
 * CRTEMU_OSD_TEST; nothing is drawn, so no GL is needed) and prints what the panel would show,
 * one "kind<TAB>index<TAB>text" line per item.
 * After the shader: "set:NAME=value" changes a live value, "switch:xx" presses that language button. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void crtemu_osd_load(const char* shader_path);
const char* crtemu_osd_param_name(int i);
float crtemu_osd_param_value(int i);
const char* crtemu_osd_test_lang(void);
int crtemu_osd_test_count(int what);
const char* crtemu_osd_test_label(int i);
const char* crtemu_osd_test_hint(int i);
const char* crtemu_osd_test_option(int i, int k);
const char* crtemu_osd_test_group(int i);
const char* crtemu_osd_test_preset(int i);
const char* crtemu_osd_test_ui(int s);
const char* crtemu_osd_test_status(void);
void crtemu_osd_test_set(const char* name, float v);
void crtemu_osd_test_set_lang(int lang);

int main(int argc, char** argv)
{
    if (argc < 2) { fprintf(stderr, "usage: osd_meta_test <shader.glsl> [set:NAME=value] [switch:en|ru]\n"); return 2; }
    crtemu_osd_load(argv[1]);
    for (int a = 2; a < argc; a++)
    {
        const char* eq = strchr(argv[a], '=');
        if (strncmp(argv[a], "set:", 4) == 0 && eq)
        {
            char name[64];
            snprintf(name, sizeof(name), "%.*s", (int)(eq - argv[a] - 4), argv[a] + 4);
            crtemu_osd_test_set(name, (float)atof(eq + 1));
        }
        else if (strncmp(argv[a], "switch:", 7) == 0)
            crtemu_osd_test_set_lang(strcmp(argv[a] + 7, "ru") == 0 ? 1 : 0);
    }
    printf("lang\t0\t%s\n", crtemu_osd_test_lang());
    int np = crtemu_osd_test_count(0), ng = crtemu_osd_test_count(1), npr = crtemu_osd_test_count(2);
    for (int i = 0; i < np; i++)
    {
        printf("name\t%d\t%s\n", i, crtemu_osd_param_name(i));
        printf("label\t%d\t%s\n", i, crtemu_osd_test_label(i));
        printf("hint\t%d\t%s\n", i, crtemu_osd_test_hint(i));
        printf("value\t%d\t%s=%.3f\n", i, crtemu_osd_param_name(i), crtemu_osd_param_value(i));
        for (int k = 0; crtemu_osd_test_option(i, k)[0]; k++) printf("option\t%d\t%s\n", i, crtemu_osd_test_option(i, k));
    }
    for (int i = 0; i < ng; i++) printf("group\t%d\t%s\n", i, crtemu_osd_test_group(i));
    for (int i = 0; i < npr; i++) printf("preset\t%d\t%s\n", i, crtemu_osd_test_preset(i));
    for (int s = 0; crtemu_osd_test_ui(s)[0]; s++) printf("ui\t%d\t%s\n", s, crtemu_osd_test_ui(s));
    printf("status\t0\t%s\n", crtemu_osd_test_status());
    return 0;
}
