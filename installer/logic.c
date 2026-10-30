/* crt-emu setup - text helpers shared by the installer and its host tests (plain C, UTF-8 bytes). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "logic.h"

static const char* skip_ws(const char* s, const char* e)
{
    while (s < e && (*s == ' ' || *s == '\t')) s++;
    return s;
}

static const char* word_end(const char* s, const char* e)
{
    while (s < e && *s != ' ' && *s != '\t' && *s != '\r' && *s != '\n') s++;
    return s;
}

static int is_num_char(char c) { return (c >= '0' && c <= '9') || c == '.' || c == '-' || c == '+'; }

static const char* num_end(const char* s, const char* e)
{
    const char* p = s;
    while (p < e && is_num_char(*p)) p++;
    /* at least one digit */
    for (const char* q = s; q < p; q++) if (*q >= '0' && *q <= '9') return p;
    return s;
}

/* growing output buffer */
typedef struct { char* p; size_t n, cap; } buf_t;

static void put(buf_t* b, const char* s, size_t n)
{
    if (b->n + n + 1 > b->cap)
    {
        size_t cap = (b->cap + n + 1) * 2;
        char* p = (char*)realloc(b->p, cap);
        if (!p) return;
        b->p = p;
        b->cap = cap;
    }
    memcpy(b->p + b->n, s, n);
    b->n += n;
    b->p[b->n] = 0;
}

static void puts_(buf_t* b, const char* s) { put(b, s, strlen(s)); }

typedef struct { char name[48]; char val[24]; } kv_t;

/* "#define NAME <number> ..." -> name and number; returns 1 on match */
static int parse_define(const char* ls, const char* le, const char** n0, const char** n1, const char** v0, const char** v1)
{
    const char* s = skip_ws(ls, le);
    if (le - s < 8 || strncmp(s, "#define", 7) != 0 || (s[7] != ' ' && s[7] != '\t')) return 0;
    s = skip_ws(s + 7, le);
    *n0 = s;
    *n1 = word_end(s, le);
    if (*n1 == *n0 || *n1 - *n0 >= 48) return 0;
    s = skip_ws(*n1, le);
    *v0 = s;
    *v1 = num_end(s, le);
    return *v1 > *v0 && (*v1 - *v0) < 24;
}

/* "#pragma parameter NAME "desc" <default> ..." */
static int parse_pragma(const char* ls, const char* le, const char** n0, const char** n1, const char** v0, const char** v1)
{
    const char* s = skip_ws(ls, le);
    if (le - s < 18 || strncmp(s, "#pragma parameter", 17) != 0) return 0;
    s = skip_ws(s + 17, le);
    *n0 = s;
    *n1 = word_end(s, le);
    if (*n1 == *n0 || *n1 - *n0 >= 48) return 0;
    const char* q1 = (const char*)memchr(*n1, '"', le - *n1);
    const char* q2 = q1 ? (const char*)memchr(q1 + 1, '"', le - q1 - 1) : NULL;
    if (!q2) return 0;
    s = skip_ws(q2 + 1, le);
    *v0 = s;
    *v1 = num_end(s, le);
    return *v1 > *v0;
}

static const char* next_line(const char* p, const char** ls, const char** le, const char** lend)
{
    if (!*p) return NULL;
    *ls = p;
    while (*p && *p != '\n') p++;
    *le = (p > *ls && p[-1] == '\r') ? p - 1 : p;
    if (*p) p++;
    *lend = p;
    return p;
}

char* crtemu_merge_settings(const char* new_text, const char* old_text, int* merged)
{
    kv_t* kv = (kv_t*)calloc(256, sizeof(kv_t));
    int nkv = 0;
    const char *ls, *le, *lend, *p, *n0, *n1, *v0, *v1;
    if (merged) *merged = 0;
    if (!kv) return NULL;

    for (p = old_text; old_text && (p = next_line(p, &ls, &le, &lend)) != NULL;)
    {
        if (nkv < 256 && parse_define(ls, le, &n0, &n1, &v0, &v1))
        {
            memcpy(kv[nkv].name, n0, n1 - n0); kv[nkv].name[n1 - n0] = 0;
            memcpy(kv[nkv].val, v0, v1 - v0); kv[nkv].val[v1 - v0] = 0;
            nkv++;
        }
    }

    /* only real parameters: names that have a #pragma parameter line in the new shader */
    int keep_n = 0;
    for (int i = 0; i < nkv; i++)
    {
        int is_param = 0;
        for (p = new_text; !is_param && (p = next_line(p, &ls, &le, &lend)) != NULL;)
            if (parse_pragma(ls, le, &n0, &n1, &v0, &v1) && (size_t)(n1 - n0) == strlen(kv[i].name) &&
                strncmp(n0, kv[i].name, n1 - n0) == 0)
                is_param = 1;
        if (is_param) kv[keep_n++] = kv[i];
    }
    nkv = keep_n;

    buf_t b = { 0 };
    puts_(&b, "");
    for (p = new_text; (p = next_line(p, &ls, &le, &lend)) != NULL;)
    {
        int done = 0, d = 0;
        if ((d = parse_define(ls, le, &n0, &n1, &v0, &v1)) || parse_pragma(ls, le, &n0, &n1, &v0, &v1))
        {
            for (int i = 0; i < nkv; i++)
            {
                if ((size_t)(n1 - n0) == strlen(kv[i].name) && strncmp(n0, kv[i].name, n1 - n0) == 0)
                {
                    char head[160];
                    if (d)
                        snprintf(head, sizeof(head), "#define %-12s %6s", kv[i].name, kv[i].val);
                    else
                        head[0] = 0;
                    if (d)
                        puts_(&b, head);
                    else
                    {
                        put(&b, ls, v0 - ls);
                        puts_(&b, kv[i].val);
                    }
                    put(&b, v1, lend - v1);
                    done = 1;
                    if (merged && d) (*merged)++;
                    break;
                }
            }
        }
        if (!done) put(&b, ls, lend - ls);
    }
    free(kv);
    return b.p;
}

char* crtemu_set_hd_key(const char* text, const char* key, const char* value, int* changed)
{
    buf_t b = { 0 };
    const char *ls, *le, *lend, *p;
    size_t kl = strlen(key);
    puts_(&b, "");
    for (p = text; (p = next_line(p, &ls, &le, &lend)) != NULL;)
    {
        const char* s = skip_ws(ls, le);
        if ((size_t)(le - s) > kl && strncmp(s, key, kl) == 0)
        {
            const char* eq = (const char*)memchr(s + kl, '=', le - s - kl);
            if (eq)
            {
                const char* v0 = skip_ws(eq + 1, le);
                const char* v1 = word_end(v0, le);
                if ((size_t)(v1 - v0) != strlen(value) || strncmp(v0, value, v1 - v0) != 0)
                {
                    put(&b, ls, v0 - ls);
                    puts_(&b, value);
                    put(&b, v1, lend - v1);
                    if (changed) (*changed)++;
                    continue;
                }
            }
        }
        put(&b, ls, lend - ls);
    }
    return b.p;
}

int crtemu_get_hd_key(const char* text, const char* key, char* out, size_t n)
{
    const char *ls, *le, *lend, *p;
    size_t kl = strlen(key);
    for (p = text; (p = next_line(p, &ls, &le, &lend)) != NULL;)
    {
        const char* s = skip_ws(ls, le);
        if ((size_t)(le - s) <= kl || strncmp(s, key, kl) != 0) continue;
        const char* eq = (const char*)memchr(s + kl, '=', le - s - kl);
        if (!eq) continue;
        const char* v0 = skip_ws(eq + 1, le);
        const char* v1 = word_end(v0, le);
        if ((size_t)(v1 - v0) >= n) return 0;
        memcpy(out, v0, v1 - v0);
        out[v1 - v0] = 0;
        return 1;
    }
    return 0;
}

char* crtemu_to_crlf(const char* text)
{
    buf_t b = { 0 };
    puts_(&b, "");
    for (const char* p = text; *p; p++)
    {
        if (*p == '\n' && (p == text || p[-1] != '\r')) put(&b, "\r\n", 2);
        else put(&b, p, 1);
    }
    return b.p;
}

int crtemu_contains(const char* hay, size_t n, const char* needle)
{
    size_t k = strlen(needle);
    if (k == 0 || n < k) return 0;
    for (size_t i = 0; i + k <= n; i++)
        if (hay[i] == needle[0] && memcmp(hay + i, needle, k) == 0) return 1;
    return 0;
}

static int lower(int c) { return (c >= 'A' && c <= 'Z') ? c + ('a' - 'A') : c; }

char* crtemu_replace_ci(const char* text, const char* from, const char* to, int* count)
{
    buf_t b = { 0 };
    size_t k = strlen(from);
    if (count) *count = 0;
    puts_(&b, "");
    for (const char* p = text; *p;)
    {
        size_t i = 0;
        while (i < k && p[i] && lower((unsigned char)p[i]) == lower((unsigned char)from[i])) i++;
        if (k && i == k)
        {
            puts_(&b, to);
            p += k;
            if (count) (*count)++;
        }
        else
            put(&b, p++, 1);
    }
    return b.p;
}

int crtemu_get_ini_value(const char* text, const char* key, char* out, size_t n)
{
    const char *ls, *le, *lend, *p;
    size_t kl = strlen(key);
    int found = 0;
    for (p = text; (p = next_line(p, &ls, &le, &lend)) != NULL;)
    {
        const char* s = skip_ws(ls, le);
        const char* eq = (const char*)memchr(s, '=', le - s);
        if (!eq) continue;
        const char* ke = eq;
        while (ke > s && (ke[-1] == ' ' || ke[-1] == '\t')) ke--;
        if ((size_t)(ke - s) != kl) continue;
        size_t i = 0;
        while (i < kl && lower((unsigned char)s[i]) == lower((unsigned char)key[i])) i++;
        if (i < kl) continue;
        const char* v0 = skip_ws(eq + 1, le);
        const char* v1 = le;
        while (v1 > v0 && (v1[-1] == ' ' || v1[-1] == '\t')) v1--;
        if ((size_t)(v1 - v0) >= n) { found = 0; continue; }
        memcpy(out, v0, v1 - v0);
        out[v1 - v0] = 0;
        found = 1;
    }
    return found;
}

int crtemu_panel_lang(const char* record, char* out, size_t n)
{
    char v[16];
    int maj = 0, min = 0;
    /* setups before 2.2 wrote their own language there: that is no choice made in the panel */
    if (crtemu_get_ini_value(record, "version", v, sizeof(v)) && sscanf(v, "%d.%d", &maj, &min) >= 1 &&
        (maj < 2 || (maj == 2 && min < 2)))
        return 0;
    return crtemu_get_ini_value(record, "lang", out, n);
}
