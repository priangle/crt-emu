#ifndef CRTEMU_LOGIC_H
#define CRTEMU_LOGIC_H
#include <stddef.h>

/* New shader text with the "#define NAME value" settings (and #pragma parameter defaults) taken
   from the old shader for every name present in both. *merged = number of #define values kept.
   Returns a malloc'd string. */
char* crtemu_merge_settings(const char* new_text, const char* old_text, int* merged);

/* HD mod settings line "<Key> = value  {comment}": set value; *changed counts edits. malloc'd. */
char* crtemu_set_hd_key(const char* text, const char* key, const char* value, int* changed);

/* The value of the first such line into out (n bytes with the terminator); 1 if found and it fits. */
int crtemu_get_hd_key(const char* text, const char* key, char* out, size_t n);

/* LF -> CRLF (existing CRLF kept). malloc'd. */
char* crtemu_to_crlf(const char* text);

int crtemu_contains(const char* hay, size_t n, const char* needle);

/* Every occurrence of `from` (ASCII case-insensitive) replaced by `to`; *count = replacements. malloc'd. */
char* crtemu_replace_ci(const char* text, const char* from, const char* to, int* count);

#endif
