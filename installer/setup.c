/* crt-emu setup for Heroes of Might and Magic III (HD mod).
 *
 * One self-contained exe: the crt-emu cnc-ddraw build, ddraw.ini, the shader and docs are
 * RCDATA resources. Finds the game (saved path, GOG / New World Computing registry, usual
 * folders on fixed drives), lets the user pick another folder, installs, re-installs after an
 * HD mod update (keeping the user's shader settings) and uninstalls (restoring backups and the HD mod
 * settings it changed, forgetting the saved game path).
 * An install made under the project's old name (PC-CRT) is taken over: settings, ddraw.ini
 * shader paths, backups and the saved game path move to the new names, the old files go.
 * Runs as the current user; relaunches itself elevated only if the game folder is not writable.
 */
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <wctype.h>

#include "resource.h"
#include "logic.h"
#include "payload.h"

#define PATHN 1024
#define BACKUP_EXT L".crt-emu-backup"
#define REG_KEY L"Software\\crt-emu"
#define SHADER_DIR L"Shaders\\crt-emu"
#define SETTINGS SHADER_DIR L"\\crt-emu-pass1scale.glsl.pass1"
#define MARK_DLL "fix_dpi_unaware"   /* config key present in every crt-emu cnc-ddraw build */
#define MARK_INI "crt-emu build"     /* in the comments of our ddraw.ini; plain "crt-emu" would match a shader path */

/* the same things under the project's old name (PC-CRT) */
#define OLD_BACKUP_EXT L".pccrt-backup"
#define OLD_REG_KEY L"Software\\PC-CRT"
#define OLD_SHADER_DIR L"Shaders\\pc-crt"
#define OLD_SETTINGS OLD_SHADER_DIR L"\\pc-crt-pass1scale.glsl.pass1"
#define OLD_MARK_INI "PC-CRT"
#define OLD_INI_PATH "pc-crt\\pc-crt-"   /* shader paths in ddraw.ini ... */
#define NEW_INI_PATH "crt-emu\\crt-emu-" /* ... and what they become */

enum { RES_OK = 0, RES_FAIL = 1, RES_ELEVATE = 2, RES_RUNNING = 3, RES_NOGAME = 4 };

static HINSTANCE g_inst;
static HWND g_dlg;
static wchar_t g_msg[4096];

/* ------------------------------------------------------------------ language */

/* the setup's own texts: the choice saved in the registry, else the Windows display language. The F12
   panel has its own language (EN/RU in the panel, lang= in install.ini, else the game's language). */
enum { LANG_EN, LANG_RU, LANG_N };
static const wchar_t* const LANG_CODE[LANG_N] = { L"en", L"ru" };
static const wchar_t* const LANG_NAME[LANG_N] = { L"English", L"Русский" };
static int g_lang = LANG_EN;

enum
{
    S_TITLE, S_INFO, S_PATHLABEL, S_BROWSE, S_CHK_HD, S_CHK_KEEP, S_HINT, S_INSTALL, S_REINSTALL, S_UNINSTALL,
    S_CLOSE, S_CANCEL, S_BROWSE_TITLE,
    S_ST_NODIR, S_ST_NOGAME, S_ST_HOTA_HD, S_ST_HOTA, S_ST_H3_HD, S_ST_H3, S_ST_OLD, S_ST_INSTALLED, S_ST_DLL_GONE,
    S_ST_FOREIGN, S_ST_NONE,
    S_ERR_CODE, S_E_CREATE, S_E_WRITE, S_E_BUSY, S_E_REPLACE, S_E_MKDIR, S_E_BACKUP, S_E_NOINI, S_E_DELETE,
    S_E_RESTORE, S_E_NOGAME, S_E_RUNNING, S_E_ACCESS, S_E_ACCESS_ADMIN, S_E_ELEVATE,
    S_DONE, S_DONE_OLD, S_DONE_OLD_LEFT, S_DONE_KEPT, S_DONE_HD, S_DONE_HD_OK, S_DONE_FOREIGN, S_DONE_FOREIGN_INI,
    S_UNINST_DONE, S_UNINST_HD_BACK, S_UNINST_HD_LEFT, S_UNINST_HD_NONE, S_UNINST_HD_CHECK, S_ASK_UNINST, S_ASK_UNINST_MORE,
    S_COUNT
};

static const wchar_t* const STR[S_COUNT][LANG_N] = {
    [S_TITLE] = { L"crt-emu %s setup", L"crt-emu %s — установка" },
    [S_INFO] = { L"crt-emu turns the picture of Heroes of Might and Magic III with the HD mod into the image of a CRT tube. "
                 L"The setup puts into the game folder a cnc-ddraw build with a settings panel over the game (F12) and the tube shader.",
                 L"crt-emu превращает картинку Heroes of Might and Magic III с HD-модом в изображение кинескопа. "
                 L"Установка кладёт в папку игры сборку cnc-ddraw с настройкой поверх игры (F12) и шейдер кинескопа." },
    [S_PATHLABEL] = { L"Game folder:", L"Папка с игрой:" },
    [S_BROWSE] = { L"Browse...", L"Обзор…" },
    [S_CHK_HD] = { L"Set up the HD mod: renderer “16-bit DirectDraw (original)”, system cursors off",
                   L"Настроить HD-мод: рендерер «16-bit DirectDraw (original)», системные курсоры выключены" },
    [S_CHK_KEEP] = { L"Keep my tube settings when reinstalling", L"Сохранить мои настройки кинескопа при переустановке" },
    [S_HINT] = { L"In the game: F12 — tune the tube right over the game, F11 — effect on/off. After an HD mod update run "
                 L"this setup again. Close the game and HD_Launcher before installing.",
                 L"В игре: F12 — настройка кинескопа прямо поверх игры, F11 — эффект вкл/выкл. Обновили HD-мод — "
                 L"запустите установку ещё раз. Перед установкой закройте игру и HD_Launcher." },
    [S_INSTALL] = { L"Install", L"Установить" },
    [S_REINSTALL] = { L"Reinstall", L"Переустановить" },
    [S_UNINSTALL] = { L"Uninstall", L"Удалить" },
    [S_CLOSE] = { L"Close", L"Закрыть" },
    [S_CANCEL] = { L"Cancel", L"Отмена" },
    [S_BROWSE_TITLE] = { L"Folder with Heroes of Might and Magic III", L"Папка с Heroes of Might and Magic III" },

    [S_ST_NODIR] = { L"Choose the folder where Heroes is installed (it holds Heroes3.exe or h3hota.exe).",
                     L"Укажите папку, где установлены «Герои» (там лежит Heroes3.exe или h3hota.exe)." },
    [S_ST_NOGAME] = { L"There is no game in this folder. Choose the folder that holds Heroes3.exe or h3hota.exe.",
                      L"В этой папке нет игры. Укажите папку, где лежит Heroes3.exe или h3hota.exe." },
    [S_ST_HOTA_HD] = { L"Found Horn of the Abyss and the HD mod.", L"Найдены Horn of the Abyss и HD-мод." },
    [S_ST_HOTA] = { L"Found Horn of the Abyss without the HD mod.", L"Найден Horn of the Abyss без HD-мода." },
    [S_ST_H3_HD] = { L"Found Heroes III and the HD mod.", L"Найдены Heroes III и HD-мод." },
    [S_ST_H3] = { L"Found Heroes III without the HD mod.", L"Найдены Heroes III без HD-мода." },
    [S_ST_OLD] = { L"Found an earlier PC-CRT install. “Reinstall” moves it to crt-emu, your tube settings are kept.",
                   L"Найдена прежняя установка PC-CRT. «Переустановить» перенесёт её в crt-emu, ваши настройки кинескопа сохранятся." },
    [S_ST_INSTALLED] = { L"crt-emu is already installed. “Reinstall” updates the files, your tube settings are kept.",
                         L"crt-emu уже установлен. «Переустановить» обновит файлы, ваши настройки кинескопа сохранятся." },
    [S_ST_DLL_GONE] = { L"crt-emu was installed, but ddraw.dll is missing or replaced — this happens after an HD mod update. Press “Reinstall”.",
                        L"crt-emu стоял, но ddraw.dll пропал или заменён — так бывает после обновления HD-мода. Нажмите «Переустановить»." },
    [S_ST_FOREIGN] = { L"The folder already has another ddraw.dll — it will be saved next to it and comes back when crt-emu is uninstalled.",
                       L"В папке уже есть другой ddraw.dll — он будет сохранён рядом и вернётся при удалении crt-emu." },
    [S_ST_NONE] = { L"crt-emu is not installed yet.", L"crt-emu ещё не установлен." },

    [S_ERR_CODE] = { L"%s\n%s\n\n%s (code %lu).", L"%s\n%s\n\n%s (код %lu)." },
    [S_E_CREATE] = { L"Could not create the file:", L"Не удалось создать файл:" },
    [S_E_WRITE] = { L"Could not write the file:", L"Не удалось записать файл:" },
    [S_E_BUSY] = { L"The file is in use or protected — close the game and HD_Launcher:",
                   L"Файл занят или защищён — закройте игру и HD_Launcher:" },
    [S_E_REPLACE] = { L"Could not replace the file:", L"Не удалось заменить файл:" },
    [S_E_MKDIR] = { L"Could not create the folder:", L"Не удалось создать папку:" },
    [S_E_BACKUP] = { L"Could not save a copy:", L"Не удалось сохранить копию:" },
    [S_E_NOINI] = { L"The setup has no ddraw.ini inside.", L"В установщике нет ddraw.ini." },
    [S_E_DELETE] = { L"Could not delete the file (close the game):", L"Не удалось удалить файл (закройте игру):" },
    [S_E_RESTORE] = { L"Could not bring back the file:", L"Не удалось вернуть файл:" },
    [S_E_NOGAME] = { L"The folder\n%s\nhas no game (Heroes3.exe or h3hota.exe).",
                     L"В папке\n%s\nнет игры (Heroes3.exe или h3hota.exe)." },
    [S_E_RUNNING] = { L"%s is running now. Close the game and HD_Launcher and press again.",
                      L"Сейчас запущен %s. Закройте игру и HD_Launcher и нажмите ещё раз." },
    [S_E_ACCESS] = { L"No access to the folder:", L"Нет доступа к папке:" },
    [S_E_ACCESS_ADMIN] = { L"No access to the folder even with administrator rights:",
                           L"Нет доступа к папке даже с правами администратора:" },
    [S_E_ELEVATE] = { L"This folder needs administrator rights, and the request was declined.",
                      L"Для этой папки нужны права администратора, а запрос был отклонён." },

    [S_DONE] = { L"crt-emu %s is installed.\n\n%s%s%s%s%s%s\n"
                 L"Start the game through HD_Launcher. In the game: F12 — tune the tube, F11 — effect on/off.\n\n"
                 L"After an HD mod update run this setup again: your settings are kept.",
                 L"crt-emu %s установлен.\n\n%s%s%s%s%s%s\n"
                 L"Запустите игру через HD_Launcher. В игре: F12 — настройка кинескопа, F11 — эффект вкл/выкл.\n\n"
                 L"После обновления HD-мода запустите эту установку ещё раз: ваши настройки сохранятся." },
    [S_DONE_OLD] = { L"The earlier PC-CRT install has been moved to Shaders\\crt-emu.\n",
                     L"Прежняя установка PC-CRT перенесена в Shaders\\crt-emu.\n" },
    [S_DONE_OLD_LEFT] = { L"The Shaders\\pc-crt folder is left in place: it holds other files or ddraw.ini points to it.\n",
                          L"Папка Shaders\\pc-crt оставлена: в ней есть чужие файлы или на неё ссылается ddraw.ini.\n" },
    [S_DONE_KEPT] = { L"Your tube settings are kept.\n", L"Ваши настройки кинескопа сохранены.\n" },
    [S_DONE_HD] = { L"The HD mod is switched to “16-bit DirectDraw (original)”, system cursors are off.\n",
                    L"HD-мод переключён на «16-bit DirectDraw (original)», системные курсоры выключены.\n" },
    [S_DONE_HD_OK] = { L"The HD mod settings already fitted.\n", L"Настройки HD-мода уже подходили.\n" },
    [S_DONE_FOREIGN] = { L"The previous ddraw.dll is saved as ddraw.dll" BACKUP_EXT L".\n",
                         L"Прежний ddraw.dll сохранён как ddraw.dll" BACKUP_EXT L".\n" },
    [S_DONE_FOREIGN_INI] = { L"The previous ddraw.ini is saved as ddraw.ini" BACKUP_EXT L".\n",
                             L"Прежний ddraw.ini сохранён как ddraw.ini" BACKUP_EXT L".\n" },
    [S_UNINST_DONE] = { L"crt-emu is uninstalled, the previous files are back.\n\n%s",
                        L"crt-emu удалён, прежние файлы возвращены.\n\n%s" },
    [S_UNINST_HD_BACK] = { L"The HD mod renderer and system cursors are as they were before crt-emu.",
                           L"Рендерер и системные курсоры HD-мода — как были до crt-emu." },
    [S_UNINST_HD_LEFT] = { L"The HD mod renderer and system cursors are as they were before crt-emu, except the ones "
                           L"you changed yourself after installing: those are left as they are.",
                           L"Рендерер и системные курсоры HD-мода — как были до crt-emu, кроме тех, что вы меняли "
                           L"сами после установки: они оставлены как есть." },
    [S_UNINST_HD_NONE] = { L"The setup did not change the HD mod settings: the renderer can be chosen in HD_Launcher.",
                           L"Установка не меняла настройки HD-мода: рендерер можно выбрать в HD_Launcher." },
    [S_UNINST_HD_CHECK] = { L"The HD mod renderer can be chosen in HD_Launcher.", L"Рендерер HD-мода можно выбрать в HD_Launcher." },
    [S_ASK_UNINST] = { L"Uninstall crt-emu from this folder?", L"Удалить crt-emu из этой папки?" },
    [S_ASK_UNINST_MORE] = { L"The files the setup replaced come back, and so do the HD mod settings it switched, unless you "
                            L"changed them yourself since. Your tube settings are deleted too.",
                            L"Файлы, которые заменила установка, вернутся, а с ними и настройки HD-мода, если вы не меняли "
                            L"их сами. Ваши настройки кинескопа тоже удалятся." },
};

#define T(s) STR[s][g_lang]

static int lang_from_code(const wchar_t* code)
{
    for (int i = 0; i < LANG_N; i++)
        if (_wcsicmp(code, LANG_CODE[i]) == 0) return i;
    return LANG_EN;
}

/* ------------------------------------------------------------------ small helpers */

static void path_join(wchar_t* out, const wchar_t* dir, const wchar_t* rel)
{
    size_t n = wcslen(dir);
    _snwprintf(out, PATHN, L"%s%s%s", dir, (n && dir[n - 1] == L'\\') ? L"" : L"\\", rel);
    out[PATHN - 1] = 0;
}

static BOOL file_exists(const wchar_t* p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

static BOOL dir_exists(const wchar_t* p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

static BOOL in_dir_exists(const wchar_t* dir, const wchar_t* rel)
{
    wchar_t p[PATHN];
    path_join(p, dir, rel);
    return file_exists(p);
}

static void normalize_dir(wchar_t* d)
{
    /* trim spaces and quotes, drop trailing backslash (keep "C:\") */
    wchar_t* s = d;
    while (*s == L' ' || *s == L'"') s++;
    if (s != d) memmove(d, s, (wcslen(s) + 1) * sizeof(wchar_t));
    size_t n = wcslen(d);
    while (n && (d[n - 1] == L' ' || d[n - 1] == L'"')) d[--n] = 0;
    while (n > 3 && d[n - 1] == L'\\') d[--n] = 0;
}

static char* read_all(const wchar_t* path, DWORD* size)
{
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
                           OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return NULL;
    DWORD n = GetFileSize(h, NULL), got = 0;
    char* b = (n != INVALID_FILE_SIZE && n < 64u * 1024 * 1024) ? (char*)malloc(n + 1) : NULL;
    if (b && (!ReadFile(h, b, n, &got, NULL) || got != n)) { free(b); b = NULL; }
    CloseHandle(h);
    if (b) { b[n] = 0; if (size) *size = n; }
    return b;
}

static void last_error_text(DWORD e, wchar_t* out, size_t n)
{
    out[0] = 0;
    FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, NULL, e, 0, out, (DWORD)n, NULL);
    size_t k = wcslen(out);
    while (k && (out[k - 1] == L'\r' || out[k - 1] == L'\n' || out[k - 1] == L' ' || out[k - 1] == L'.')) out[--k] = 0;
}

static BOOL fail_msg(const wchar_t* what, const wchar_t* path)
{
    DWORD e = GetLastError();
    wchar_t t[512];
    last_error_text(e, t, 512);
    _snwprintf(g_msg, 4096, T(S_ERR_CODE), what, path, t, e);
    g_msg[4095] = 0;
    return FALSE;
}

/* write through a temp file so a failed write never leaves a half file */
static BOOL write_atomic(const wchar_t* path, const void* data, DWORD size)
{
    wchar_t tmp[PATHN];
    _snwprintf(tmp, PATHN, L"%s.crt-emu-new", path);
    tmp[PATHN - 1] = 0;
    HANDLE h = CreateFileW(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return fail_msg(T(S_E_CREATE), tmp);
    DWORD put = 0;
    BOOL ok = WriteFile(h, data, size, &put, NULL) && put == size;
    DWORD e = GetLastError();
    CloseHandle(h);
    if (!ok) { DeleteFileW(tmp); SetLastError(e); return fail_msg(T(S_E_WRITE), tmp); }
    if (!MoveFileExW(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
    {
        e = GetLastError();
        DeleteFileW(tmp);
        SetLastError(e);
        return fail_msg(e == ERROR_SHARING_VIOLATION || e == ERROR_ACCESS_DENIED ? T(S_E_BUSY) : T(S_E_REPLACE), path);
    }
    return TRUE;
}

static const BYTE* res_data(int id, DWORD* size)
{
    HRSRC r = FindResourceW(g_inst, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(10) /* RT_RCDATA */);
    HGLOBAL g = r ? LoadResource(g_inst, r) : NULL;
    if (!g) return NULL;
    *size = SizeofResource(g_inst, r);
    return (const BYTE*)LockResource(g);
}

/* resource text as a NUL-terminated malloc'd string */
static char* res_text(int id)
{
    DWORD n = 0;
    const BYTE* p = res_data(id, &n);
    if (!p) return NULL;
    char* s = (char*)malloc(n + 1);
    if (!s) return NULL;
    memcpy(s, p, n);
    s[n] = 0;
    return s;
}

static int payload_find(int kind, const wchar_t* path_end)
{
    for (int i = 0; i < PAYLOAD_COUNT; i++)
    {
        if (PAYLOAD[i].kind != kind) continue;
        size_t a = wcslen(PAYLOAD[i].path), b = path_end ? wcslen(path_end) : 0;
        if (!path_end || (a >= b && _wcsicmp(PAYLOAD[i].path + a - b, path_end) == 0)) return i;
    }
    return -1;
}

static BOOL file_has(const wchar_t* path, const char* marker)
{
    DWORD n = 0;
    char* b = read_all(path, &n);
    BOOL r = b && crtemu_contains(b, n, marker);
    free(b);
    return r;
}

/* ddraw.ini written by this setup, under the new or the old name */
static BOOL ini_ours(const wchar_t* path)
{
    return file_has(path, MARK_INI) || file_has(path, OLD_MARK_INI);
}

/* ------------------------------------------------------------------ game detection */

static const wchar_t* GAME_EXES[] = { L"h3hota HD.exe", L"Heroes3 HD.exe", L"h3hota.exe", L"Heroes3.exe", L"HD_Launcher.exe" };

typedef struct
{
    BOOL game, hd, hota;
    BOOL installed, dll_ours, dll_present, dll_foreign;
    BOOL old;   /* files of an install under the old name (PC-CRT), made by its setup or by hand */
} gameinfo_t;

static void game_info(const wchar_t* dir, gameinfo_t* gi)
{
    memset(gi, 0, sizeof(*gi));
    if (!dir[0] || !dir_exists(dir)) return;
    gi->hota = in_dir_exists(dir, L"h3hota.exe") || in_dir_exists(dir, L"h3hota HD.exe");
    gi->game = gi->hota || in_dir_exists(dir, L"Heroes3.exe") || in_dir_exists(dir, L"Heroes3 HD.exe");
    gi->hd = in_dir_exists(dir, L"HD_Launcher.exe") && in_dir_exists(dir, L"_HD3_.dll");
    wchar_t p[PATHN];
    path_join(p, dir, SHADER_DIR L"\\install.ini");
    gi->installed = file_exists(p);
    gi->old = in_dir_exists(dir, OLD_SHADER_DIR L"\\install.ini") || in_dir_exists(dir, OLD_SETTINGS);
    path_join(p, dir, L"ddraw.dll");
    gi->dll_present = file_exists(p);
    gi->dll_ours = gi->dll_present && file_has(p, MARK_DLL);
    gi->dll_foreign = gi->dll_present && !gi->dll_ours;
}

/* a running game or HD launcher from this folder would lock ddraw.dll / rewrite settings */
static BOOL running_from(const wchar_t* dir, wchar_t* name, size_t n)
{
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return FALSE;
    PROCESSENTRY32W pe;
    pe.dwSize = sizeof(pe);
    BOOL found = FALSE;
    size_t dl = wcslen(dir);
    for (BOOL ok = Process32FirstW(snap, &pe); ok && !found; ok = Process32NextW(snap, &pe))
    {
        for (int i = 0; i < (int)(sizeof(GAME_EXES) / sizeof(GAME_EXES[0])); i++)
        {
            if (_wcsicmp(pe.szExeFile, GAME_EXES[i]) != 0) continue;
            HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pe.th32ProcessID);
            wchar_t img[PATHN];
            DWORD len = PATHN;
            BOOL same = TRUE;   /* unknown path: be careful */
            if (h && QueryFullProcessImageNameW(h, 0, img, &len))
                same = _wcsnicmp(img, dir, dl) == 0 && img[dl] == L'\\';
            if (h) CloseHandle(h);
            if (same) { wcsncpy(name, pe.szExeFile, n - 1); name[n - 1] = 0; found = TRUE; }
            break;
        }
    }
    CloseHandle(snap);
    return found;
}

/* cheap check used while scanning many folders: only looks for the game executables */
static BOOL is_game_dir(const wchar_t* dir)
{
    return in_dir_exists(dir, L"h3hota HD.exe") || in_dir_exists(dir, L"h3hota.exe") ||
           in_dir_exists(dir, L"Heroes3 HD.exe") || in_dir_exists(dir, L"Heroes3.exe");
}

static void add_candidate(HWND combo, const wchar_t* raw)
{
    wchar_t d[PATHN];
    wcsncpy(d, raw, PATHN - 1);
    d[PATHN - 1] = 0;
    normalize_dir(d);
    if (!d[0] || !is_game_dir(d)) return;
    if (SendMessageW(combo, CB_FINDSTRINGEXACT, (WPARAM)-1, (LPARAM)d) != CB_ERR) return;
    SendMessageW(combo, CB_ADDSTRING, 0, (LPARAM)d);
}

static void reg_value(HKEY root, const wchar_t* sub, const wchar_t* name, REGSAM view, HWND combo)
{
    HKEY k;
    if (RegOpenKeyExW(root, sub, 0, KEY_READ | view, &k) != ERROR_SUCCESS) return;
    wchar_t v[PATHN];
    DWORD type = 0, size = sizeof(v) - sizeof(wchar_t);
    if (RegQueryValueExW(k, name, NULL, &type, (BYTE*)v, &size) == ERROR_SUCCESS && (type == REG_SZ || type == REG_EXPAND_SZ))
    {
        v[size / sizeof(wchar_t)] = 0;
        add_candidate(combo, v);
    }
    RegCloseKey(k);
}

static void scan_gog(HWND combo, REGSAM view)
{
    HKEY k;
    if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, L"SOFTWARE\\GOG.com\\Games", 0, KEY_READ | view, &k) != ERROR_SUCCESS) return;
    wchar_t sub[256], full[512];
    for (DWORD i = 0;; i++)
    {
        DWORD n = 256;
        if (RegEnumKeyExW(k, i, sub, &n, NULL, NULL, NULL, NULL) != ERROR_SUCCESS) break;
        _snwprintf(full, 512, L"SOFTWARE\\GOG.com\\Games\\%s", sub);
        full[511] = 0;
        reg_value(HKEY_LOCAL_MACHINE, full, L"path", view, combo);
    }
    RegCloseKey(k);
}

static void scan_root(HWND combo, const wchar_t* root)
{
    wchar_t pat[PATHN], d[PATHN];
    if (!dir_exists(root)) return;
    add_candidate(combo, root);
    _snwprintf(pat, PATHN, L"%s\\*", root);
    pat[PATHN - 1] = 0;
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do
    {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || fd.cFileName[0] == L'.') continue;
        path_join(d, root, fd.cFileName);
        add_candidate(combo, d);
    } while (FindNextFileW(h, &fd));
    FindClose(h);
}

static void find_games(HWND combo)
{
    /* the folder used last time comes first (saved under the new or the old name) */
    reg_value(HKEY_CURRENT_USER, REG_KEY, L"GamePath", 0, combo);
    reg_value(HKEY_CURRENT_USER, OLD_REG_KEY, L"GamePath", 0, combo);
    scan_gog(combo, KEY_WOW64_32KEY);
    scan_gog(combo, KEY_WOW64_64KEY);
    reg_value(HKEY_LOCAL_MACHINE, L"SOFTWARE\\New World Computing\\Heroes of Might and Magic\u00AE III\\1.0", L"AppPath", KEY_WOW64_32KEY, combo);
    reg_value(HKEY_LOCAL_MACHINE, L"SOFTWARE\\New World Computing\\Heroes of Might and Magic III\\1.0", L"AppPath", KEY_WOW64_32KEY, combo);

    static const wchar_t* roots[] = {
        L"%c:\\GOG Games", L"%c:\\Games", L"%c:\\Games\\GOG", L"%c:\\Program Files (x86)\\GOG Galaxy\\Games",
        L"%c:\\Program Files\\GOG Galaxy\\Games", L"%c:\\Program Files (x86)\\GOG.com", L"%c:\\GOG",
        L"%c:\\Program Files (x86)\\3DO", L"%c:\\Program Files (x86)", L"%c:\\Program Files", L"%c:\\"
    };
    DWORD drives = GetLogicalDrives();
    for (int c = 'C'; c <= 'Z'; c++)
    {
        if (!(drives & (1u << (c - 'A')))) continue;
        wchar_t r[8];
        _snwprintf(r, 8, L"%c:\\", c);
        r[7] = 0;
        if (GetDriveTypeW(r) != DRIVE_FIXED) continue;
        for (int i = 0; i < (int)(sizeof(roots) / sizeof(roots[0])); i++)
        {
            wchar_t root[PATHN];
            _snwprintf(root, PATHN, roots[i], c);
            root[PATHN - 1] = 0;
            normalize_dir(root);
            scan_root(combo, root);
        }
    }
}

/* ------------------------------------------------------------------ install / uninstall */

static BOOL ensure_dir(const wchar_t* p)
{
    if (dir_exists(p)) return TRUE;
    if (CreateDirectoryW(p, NULL) || GetLastError() == ERROR_ALREADY_EXISTS) return TRUE;
    return fail_msg(T(S_E_MKDIR), p);
}

/* move a foreign file aside once, so uninstall can bring it back; *saved - copied now (an older backup is kept) */
static BOOL backup_foreign(const wchar_t* path, int* saved)
{
    wchar_t bak[PATHN];
    _snwprintf(bak, PATHN, L"%s" BACKUP_EXT, path);
    bak[PATHN - 1] = 0;
    *saved = 0;
    if (file_exists(bak)) return TRUE;
    if (CopyFileW(path, bak, TRUE)) { *saved = 1; return TRUE; }
    return fail_msg(T(S_E_BACKUP), path);
}

/* a backup made under the old name becomes ours: X.pccrt-backup -> X.crt-emu-backup */
static void rename_old_backup(const wchar_t* path)
{
    wchar_t o[PATHN], n[PATHN];
    _snwprintf(o, PATHN, L"%s" OLD_BACKUP_EXT, path);
    o[PATHN - 1] = 0;
    _snwprintf(n, PATHN, L"%s" BACKUP_EXT, path);
    n[PATHN - 1] = 0;
    if (file_exists(o) && !file_exists(n)) MoveFileExW(o, n, 0);
}

static void rename_old_backups(const wchar_t* dir)
{
    wchar_t p[PATHN];
    path_join(p, dir, L"ddraw.dll");
    rename_old_backup(p);
    path_join(p, dir, L"ddraw.ini");
    rename_old_backup(p);

    /* HD mod profiles: _HD3_Data\Settings\<name>.ini.pccrt-backup */
    path_join(p, dir, L"_HD3_Data\\Settings\\*.ini" OLD_BACKUP_EXT);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(p, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do
    {
        size_t n = wcslen(fd.cFileName), k = wcslen(OLD_BACKUP_EXT);
        if ((fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || n <= k) continue;
        fd.cFileName[n - k] = 0;   /* the profile itself */
        _snwprintf(p, PATHN, L"%s\\_HD3_Data\\Settings\\%s", dir, fd.cFileName);
        p[PATHN - 1] = 0;
        rename_old_backup(p);
    } while (FindNextFileW(h, &fd));
    FindClose(h);
}

static BOOL writable(const wchar_t* dir, DWORD* err)
{
    wchar_t p[PATHN];
    path_join(p, dir, L"crt-emu-write-test.tmp");
    HANDLE h = CreateFileW(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, NULL);
    if (h == INVALID_HANDLE_VALUE) { *err = GetLastError(); return FALSE; }
    CloseHandle(h);
    return TRUE;
}

static BOOL write_text(const wchar_t* path, const char* text) { return write_atomic(path, text, (DWORD)strlen(text)); }

static BOOL install_ini(const wchar_t* dir, BOOL keep, int* saved)
{
    wchar_t p[PATHN];
    path_join(p, dir, L"ddraw.ini");
    BOOL exists = file_exists(p), ours = exists && ini_ours(p);
    *saved = 0;
    if (ours && keep)
    {
        /* the user's own ddraw.ini stays; only shader paths of an old PC-CRT install move to Shaders\crt-emu */
        char* t = read_all(p, NULL);
        int moved = 0;
        char* out = t ? crtemu_replace_ci(t, OLD_INI_PATH, NEW_INI_PATH, &moved) : NULL;
        BOOL ok = !t || !moved || (out && write_text(p, out));
        free(t);
        free(out);
        return ok;
    }
    if (exists && !ours && !backup_foreign(p, saved)) return FALSE;

    int i = payload_find(P_INI, NULL);
    char* t = i >= 0 ? res_text(PAYLOAD[i].id) : NULL;
    if (!t) { _snwprintf(g_msg, 4096, L"%s", T(S_E_NOINI)); return FALSE; }

    /* one section per HD exe: the [ddraw] defaults already cover the rest */
    size_t cap = strlen(t) + 2048;
    char* out = (char*)malloc(cap);
    strcpy(out, t);
    free(t);
    static const char* hd_exes[] = { "Heroes3 HD" };
    for (int k = 0; k < 1; k++)
    {
        wchar_t w[64];
        _snwprintf(w, 64, L"%S.exe", hd_exes[k]);
        w[63] = 0;
        if (!in_dir_exists(dir, w)) continue;
        char sec[512];
        _snprintf(sec, sizeof(sec), "\n[%s]\nrenderer=opengl\nshader=Shaders\\crt-emu\\crt-emu-pass1scale.glsl\n"
                  "game_handles_close=true\nkeytogglefullscreen2=0x73\n", hd_exes[k]);
        sec[sizeof(sec) - 1] = 0;
        strcat(out, sec);
    }
    char* crlf = crtemu_to_crlf(out);
    free(out);
    BOOL ok = crlf && write_text(p, crlf);
    free(crlf);
    return ok;
}

static BOOL install_shaders(const wchar_t* dir, BOOL keep, int* kept)
{
    wchar_t sd[PATHN], p[PATHN], old_settings[PATHN];
    path_join(sd, dir, L"Shaders");
    if (!ensure_dir(sd)) return FALSE;
    path_join(sd, dir, SHADER_DIR);
    if (!ensure_dir(sd)) return FALSE;

    /* settings live in the pass-2 file; the user may have saved them from the in-game panel.
       No crt-emu install yet: take them from an install under the old name. */
    path_join(old_settings, dir, SETTINGS);
    if (!file_exists(old_settings)) path_join(old_settings, dir, OLD_SETTINGS);
    char* old = keep ? read_all(old_settings, NULL) : NULL;
    *kept = 0;

    for (int i = 0; i < PAYLOAD_COUNT; i++)
    {
        if (PAYLOAD[i].kind != P_SHADER && PAYLOAD[i].kind != P_DOC) continue;
        path_join(p, dir, PAYLOAD[i].path);
        char* t = res_text(PAYLOAD[i].id);
        if (!t) continue;
        char* out = t;
        if (PAYLOAD[i].kind == P_SHADER && old)
        {
            int m = 0;
            out = crtemu_merge_settings(t, old, &m);
            if (m > *kept) *kept = m;
            free(t);
        }
        else if (PAYLOAD[i].kind == P_DOC)
        {
            out = crtemu_to_crlf(t);
            free(t);
        }
        BOOL ok = out && write_text(p, out);
        free(out);
        if (!ok) { free(old); return FALSE; }
    }
    free(old);
    return TRUE;
}

/* HD mod profile keys the setup switches to 0: renderer "16-bit DirectDraw (original)", cursors drawn by the game */
static const char* const HD_KEYS[] = { "<Graphics.v2.Mode>", "<Graphics.SystemCursors>" };
#define HD_KEY_COUNT 2

/* the profile's backup keeps, for each HD key, its value right before the setup last switched it:
   the first time the whole profile is copied, later only the keys being switched now are updated in it */
static BOOL save_hd_backup(const wchar_t* p, const char* cur)
{
    wchar_t bak[PATHN];
    _snwprintf(bak, PATHN, L"%s" BACKUP_EXT, p);
    bak[PATHN - 1] = 0;
    if (!file_exists(bak)) return CopyFileW(p, bak, TRUE);
    char* old = read_all(bak, NULL);
    int n = 0;
    for (int i = 0; i < HD_KEY_COUNT && old; i++)
    {
        char v[32];
        if (!crtemu_get_hd_key(cur, HD_KEYS[i], v, sizeof(v)) || strcmp(v, "0") == 0) continue;
        char* u = crtemu_set_hd_key(old, HD_KEYS[i], v, &n);
        free(old);
        old = u;
    }
    BOOL ok = old && (!n || write_text(bak, old));
    free(old);
    return ok;
}

/* HD mod profiles (_HD3_Data\Settings\*.ini except #default...): renderer and cursors; a profile whose
   backup cannot be saved is left as it is, or uninstall could not bring it back */
static int configure_hd(const wchar_t* dir)
{
    wchar_t pat[PATHN], p[PATHN];
    path_join(pat, dir, L"_HD3_Data\\Settings\\*.ini");
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pat, &fd);
    int files = 0;
    if (h == INVALID_HANDLE_VALUE) return 0;
    do
    {
        if (fd.cFileName[0] == L'#' || (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
        _snwprintf(p, PATHN, L"%s\\_HD3_Data\\Settings\\%s", dir, fd.cFileName);
        p[PATHN - 1] = 0;
        char* t = read_all(p, NULL);
        if (!t) continue;
        int changed = 0;
        char* a = crtemu_set_hd_key(t, HD_KEYS[0], "0", &changed);
        char* b = a ? crtemu_set_hd_key(a, HD_KEYS[1], "0", &changed) : NULL;
        if (b && changed && save_hd_backup(p, t) && write_text(p, b)) files++;
        free(t); free(a); free(b);
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return files;
}

static void reg_set(const wchar_t* name, const wchar_t* value)
{
    HKEY k;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, REG_KEY, 0, NULL, 0, KEY_WRITE, NULL, &k, NULL) != ERROR_SUCCESS) return;
    RegSetValueExW(k, name, 0, REG_SZ, (const BYTE*)value, (DWORD)((wcslen(value) + 1) * sizeof(wchar_t)));
    RegCloseKey(k);
}

static void save_lang(void) { reg_set(L"Language", LANG_CODE[g_lang]); }

static void load_lang(void)
{
    g_lang = PRIMARYLANGID(GetUserDefaultUILanguage()) == LANG_RUSSIAN ? LANG_RU : LANG_EN;
    HKEY k;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, REG_KEY, 0, KEY_READ, &k) != ERROR_SUCCESS) return;
    wchar_t v[16];
    DWORD type = 0, size = sizeof(v) - sizeof(wchar_t);
    if (RegQueryValueExW(k, L"Language", NULL, &type, (BYTE*)v, &size) == ERROR_SUCCESS && type == REG_SZ)
    {
        v[size / sizeof(wchar_t)] = 0;
        g_lang = lang_from_code(v);
    }
    RegCloseKey(k);
}

static void remember_dir(const wchar_t* dir)
{
    /* the language is saved only when it is chosen in the window (CBN_SELCHANGE): otherwise the
       Windows language would hold only until the first install */
    reg_set(L"GamePath", dir);
    RegDeleteKeyW(HKEY_CURRENT_USER, OLD_REG_KEY);   /* the path saved under the old name is not needed any more */
}

static BOOL delete_if_exists(const wchar_t* p)
{
    if (!file_exists(p) || DeleteFileW(p)) return TRUE;
    return fail_msg(T(S_E_DELETE), p);
}

static BOOL restore_backup(const wchar_t* p)
{
    wchar_t bak[PATHN];
    rename_old_backup(p);
    _snwprintf(bak, PATHN, L"%s" BACKUP_EXT, p);
    bak[PATHN - 1] = 0;
    if (!file_exists(bak)) return TRUE;
    if (MoveFileExW(bak, p, MOVEFILE_REPLACE_EXISTING)) return TRUE;
    return fail_msg(T(S_E_RESTORE), p);
}

/* uninstall: the HD keys go back to the values in the profile's backup, but only where the profile still has
   ours (the user may have changed them since); the other lines stay as the HD mod left them. A backup whose
   profile is gone has nothing to come back to and goes too.
   *found - backups, *same - keys now as before the install, *left - keys the user changed;
   returns FALSE on a read or write error (that profile and its backup stay as they are) */
static BOOL restore_hd(const wchar_t* dir, int* found, int* same, int* left)
{
    wchar_t pat[PATHN], p[PATHN], bak[PATHN];
    *found = *same = *left = 0;
    path_join(pat, dir, L"_HD3_Data\\Settings\\*.ini" BACKUP_EXT);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) return TRUE;
    BOOL ok = TRUE;
    do
    {
        size_t n = wcslen(fd.cFileName), k = wcslen(BACKUP_EXT);
        if ((fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || n <= k) continue;
        _snwprintf(bak, PATHN, L"%s\\_HD3_Data\\Settings\\%s", dir, fd.cFileName);
        bak[PATHN - 1] = 0;
        fd.cFileName[n - k] = 0;   /* the profile itself */
        _snwprintf(p, PATHN, L"%s\\_HD3_Data\\Settings\\%s", dir, fd.cFileName);
        p[PATHN - 1] = 0;
        (*found)++;
        if (!file_exists(p)) { DeleteFileW(bak); continue; }
        char* old = read_all(bak, NULL);
        char* t = old ? read_all(p, NULL) : NULL;
        int changed = 0;
        for (int i = 0; i < HD_KEY_COUNT && t; i++)
        {
            char was[32], now[32];
            if (!crtemu_get_hd_key(old, HD_KEYS[i], was, sizeof(was)) || !crtemu_get_hd_key(t, HD_KEYS[i], now, sizeof(now))) continue;
            if (strcmp(now, was) == 0) { (*same)++; continue; }
            if (strcmp(now, "0") != 0) { (*left)++; continue; }
            char* u = crtemu_set_hd_key(t, HD_KEYS[i], was, &changed);
            free(t);
            t = u;
            (*same)++;
        }
        if (!t || (changed && !write_text(p, t))) ok = fail_msg(T(S_E_RESTORE), p);
        else DeleteFileW(bak);
        free(old);
        free(t);
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return ok;
}

/* uninstall: the saved game path is this folder (or there is none) - no other install needs the key */
static void forget_dir(const wchar_t* dir)
{
    static const wchar_t* keys[] = { REG_KEY, OLD_REG_KEY };
    for (int i = 0; i < 2; i++)
    {
        HKEY k;
        if (RegOpenKeyExW(HKEY_CURRENT_USER, keys[i], 0, KEY_READ, &k) != ERROR_SUCCESS) continue;
        wchar_t v[PATHN];
        DWORD type = 0, size = sizeof(v) - sizeof(wchar_t);
        LONG r = RegQueryValueExW(k, L"GamePath", NULL, &type, (BYTE*)v, &size);
        RegCloseKey(k);
        BOOL mine = r == ERROR_FILE_NOT_FOUND;
        if (r == ERROR_SUCCESS && type == REG_SZ)
        {
            v[size / sizeof(wchar_t)] = 0;
            normalize_dir(v);
            mine = _wcsicmp(v, dir) == 0;
        }
        if (mine) RegDeleteKeyW(HKEY_CURRENT_USER, keys[i]);
    }
}

/* files an install under the old name put into Shaders\pc-crt; the folder goes only if nothing else is left */
static BOOL remove_old_install(const wchar_t* dir)
{
    static const wchar_t* files[] = { L"pc-crt-pass1scale.glsl", L"pc-crt-pass1scale.glsl.pass1", L"pc-crt-lite.glsl",
                                      L"README.txt", L"README.ru.txt", L"cnc-ddraw-LICENSE.txt", L"imgui-LICENSE.txt",
                                      L"install.ini" };
    wchar_t p[PATHN], rel[PATHN];
    BOOL ok = TRUE;
    for (int i = 0; i < (int)(sizeof(files) / sizeof(files[0])); i++)
    {
        _snwprintf(rel, PATHN, OLD_SHADER_DIR L"\\%s", files[i]);
        rel[PATHN - 1] = 0;
        path_join(p, dir, rel);
        if (!delete_if_exists(p)) ok = FALSE;
    }
    path_join(p, dir, OLD_SHADER_DIR);
    RemoveDirectoryW(p);
    return ok;
}

/* ddraw.ini still points into Shaders\pc-crt (a path written another way, or an unreadable file):
   then the old folder stays, or the game would lose its shader */
static BOOL ini_uses_old_dir(const wchar_t* dir)
{
    wchar_t p[PATHN];
    path_join(p, dir, L"ddraw.ini");
    char* t = read_all(p, NULL);
    if (!t) return file_exists(p);
    int a = 0, b = 0;
    free(crtemu_replace_ci(t, "pc-crt\\", "", &a));   /* used only to count the occurrences */
    free(crtemu_replace_ci(t, "pc-crt/", "", &b));
    free(t);
    return a + b > 0;
}

static int do_install(const wchar_t* dir, BOOL hd, BOOL keep)
{
    gameinfo_t gi;
    wchar_t p[PATHN], who[MAX_PATH];
    game_info(dir, &gi);
    if (!gi.game)
    {
        _snwprintf(g_msg, 4096, T(S_E_NOGAME), dir);
        return RES_NOGAME;
    }
    if (running_from(dir, who, MAX_PATH))
    {
        _snwprintf(g_msg, 4096, T(S_E_RUNNING), who);
        return RES_RUNNING;
    }
    DWORD err = 0;
    if (!writable(dir, &err)) return err == ERROR_ACCESS_DENIED ? RES_ELEVATE : (fail_msg(T(S_E_ACCESS), dir), RES_FAIL);
    rename_old_backups(dir);   /* before backup_foreign: an old backup must not be taken for a missing one */

    /* ddraw.dll */
    path_join(p, dir, L"ddraw.dll");
    int dll_saved = 0;
    if (gi.dll_foreign && !backup_foreign(p, &dll_saved)) return RES_FAIL;
    int idll = payload_find(P_FILE, L"ddraw.dll");
    DWORD n = 0;
    const BYTE* dll = idll >= 0 ? res_data(PAYLOAD[idll].id, &n) : NULL;
    if (!dll || !write_atomic(p, dll, n)) return RES_FAIL;

    int ini_saved = 0;
    if (!install_ini(dir, keep, &ini_saved)) return RES_FAIL;
    int kept = 0;
    if (!install_shaders(dir, keep, &kept)) return RES_FAIL;
    int hd_files = hd && gi.hd ? configure_hd(dir) : 0;

    /* marker + record. lang= is the F12 panel's language, chosen in the panel: a reinstall keeps it,
       and without it the panel follows the game's language */
    path_join(p, dir, SHADER_DIR L"\\install.ini");
    char lang[16] = "";
    char* old_rec = read_all(p, NULL);
    if (old_rec)
    {
        if (!crtemu_panel_lang(old_rec, lang, sizeof(lang))) lang[0] = 0;
        free(old_rec);
    }
    SYSTEMTIME st;
    GetLocalTime(&st);
    char rec[512];
    _snprintf(rec, sizeof(rec), "[crt-emu]\r\nversion=%S\r\ninstalled=%04d-%02d-%02d %02d:%02d\r\nforeign_ddraw_backup=%d\r\n%s%s%s",
              CRTEMU_VERSION, st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, gi.dll_foreign,
              lang[0] ? "lang=" : "", lang, lang[0] ? "\r\n" : "");
    rec[sizeof(rec) - 1] = 0;
    if (!write_text(p, rec)) return RES_FAIL;
    remember_dir(dir);

    /* the new files are in place: the old name's files can go */
    BOOL old_left = FALSE;
    if (gi.old)
    {
        if (!ini_uses_old_dir(dir) && !remove_old_install(dir)) return RES_FAIL;
        path_join(p, dir, OLD_SHADER_DIR);
        old_left = dir_exists(p);
    }

    _snwprintf(g_msg, 4096, T(S_DONE), CRTEMU_VERSION,
               gi.old ? T(S_DONE_OLD) : L"",
               old_left ? T(S_DONE_OLD_LEFT) : L"",
               kept ? T(S_DONE_KEPT) : L"",
               hd_files ? T(S_DONE_HD) : (gi.hd && hd ? T(S_DONE_HD_OK) : L""),
               dll_saved ? T(S_DONE_FOREIGN) : L"",
               ini_saved ? T(S_DONE_FOREIGN_INI) : L"");
    return RES_OK;
}

static int do_uninstall(const wchar_t* dir)
{
    wchar_t p[PATHN], who[MAX_PATH];
    if (running_from(dir, who, MAX_PATH))
    {
        _snwprintf(g_msg, 4096, T(S_E_RUNNING), who);
        return RES_RUNNING;
    }
    DWORD err = 0;
    if (!writable(dir, &err)) return err == ERROR_ACCESS_DENIED ? RES_ELEVATE : (fail_msg(T(S_E_ACCESS), dir), RES_FAIL);
    rename_old_backups(dir);   /* backups made under the old name come back too */
    /* HD profiles first: if one cannot be written, crt-emu is still installed and "Uninstall" can be pressed again */
    int found = 0, same = 0, left = 0;
    if (!restore_hd(dir, &found, &same, &left)) return RES_FAIL;

    path_join(p, dir, L"ddraw.dll");
    if (file_exists(p) && file_has(p, MARK_DLL) && !delete_if_exists(p)) return RES_FAIL;
    if (!restore_backup(p)) return RES_FAIL;
    path_join(p, dir, L"ddraw.ini");
    if (file_exists(p) && ini_ours(p) && !delete_if_exists(p)) return RES_FAIL;
    if (!restore_backup(p)) return RES_FAIL;

    for (int i = 0; i < PAYLOAD_COUNT; i++)
    {
        if (PAYLOAD[i].kind != P_SHADER && PAYLOAD[i].kind != P_DOC) continue;
        path_join(p, dir, PAYLOAD[i].path);
        delete_if_exists(p);
    }
    path_join(p, dir, SHADER_DIR L"\\install.ini");
    delete_if_exists(p);
    path_join(p, dir, SHADER_DIR);
    RemoveDirectoryW(p);
    remove_old_install(dir);
    path_join(p, dir, L"Shaders");
    RemoveDirectoryW(p);   /* only if empty */
    forget_dir(dir);

    _snwprintf(g_msg, 4096, T(S_UNINST_DONE),
               !found ? T(S_UNINST_HD_NONE) : left ? T(S_UNINST_HD_LEFT) : same ? T(S_UNINST_HD_BACK) : T(S_UNINST_HD_CHECK));
    return RES_OK;
}

/* relaunch this exe elevated for one action, in the same language; returns the child's result */
static int run_elevated(HWND owner, const wchar_t* action, const wchar_t* dir, BOOL hd, BOOL keep)
{
    wchar_t self[PATHN], args[PATHN + 64];
    GetModuleFileNameW(NULL, self, PATHN);
    _snwprintf(args, PATHN + 64, L"%s \"%s\" %d %d lang=%s", action, dir, hd ? 1 : 0, keep ? 1 : 0, LANG_CODE[g_lang]);
    args[PATHN + 63] = 0;
    SHELLEXECUTEINFOW sei = { sizeof(sei) };
    sei.fMask = SEE_MASK_NOCLOSEPROCESS;
    sei.hwnd = owner;
    sei.lpVerb = L"runas";
    sei.lpFile = self;
    sei.lpParameters = args;
    sei.nShow = SW_SHOWNORMAL;
    if (!ShellExecuteExW(&sei) || !sei.hProcess)
    {
        _snwprintf(g_msg, 4096, L"%s", T(S_E_ELEVATE));
        return RES_FAIL;
    }
    WaitForSingleObject(sei.hProcess, INFINITE);
    DWORD code = RES_FAIL;
    GetExitCodeProcess(sei.hProcess, &code);
    CloseHandle(sei.hProcess);
    g_msg[0] = 0;   /* the elevated copy showed its own message */
    return (int)code;
}

/* ------------------------------------------------------------------ dialog */

static void get_dir(wchar_t* d)
{
    GetDlgItemTextW(g_dlg, IDC_PATH, d, PATHN);
    normalize_dir(d);
}

static void update_status(void)
{
    wchar_t d[PATHN], s[1024];
    get_dir(d);
    gameinfo_t gi;
    game_info(d, &gi);
    if (!d[0])
        wcscpy(s, T(S_ST_NODIR));
    else if (!gi.game)
        wcscpy(s, T(S_ST_NOGAME));
    else
    {
        const wchar_t* what = gi.hota ? (gi.hd ? T(S_ST_HOTA_HD) : T(S_ST_HOTA)) : (gi.hd ? T(S_ST_H3_HD) : T(S_ST_H3));
        const wchar_t* state;
        if (gi.old)
            state = T(S_ST_OLD);
        else if (gi.installed && gi.dll_ours)
            state = T(S_ST_INSTALLED);
        else if (gi.installed)
            state = T(S_ST_DLL_GONE);
        else if (gi.dll_foreign)
            state = T(S_ST_FOREIGN);
        else
            state = T(S_ST_NONE);
        _snwprintf(s, 1024, L"%s\n%s", what, state);
        s[1023] = 0;
    }
    BOOL ours = gi.installed || gi.dll_ours || gi.old;
    SetDlgItemTextW(g_dlg, IDC_STATUS, s);
    SetDlgItemTextW(g_dlg, IDC_INSTALL, ours ? T(S_REINSTALL) : T(S_INSTALL));
    EnableWindow(GetDlgItem(g_dlg, IDC_INSTALL), gi.game);
    EnableWindow(GetDlgItem(g_dlg, IDC_UNINSTALL), gi.game && ours);
    EnableWindow(GetDlgItem(g_dlg, IDC_CHK_HD), gi.hd);
    EnableWindow(GetDlgItem(g_dlg, IDC_CHK_KEEP), ours);
}

/* every text of the window in the current language */
static void apply_texts(void)
{
    static const struct { int id, s; } items[] = {
        { IDC_INFO, S_INFO }, { IDC_PATHLABEL, S_PATHLABEL }, { IDC_BROWSE, S_BROWSE }, { IDC_CHK_HD, S_CHK_HD },
        { IDC_CHK_KEEP, S_CHK_KEEP }, { IDC_HINT, S_HINT }, { IDC_UNINSTALL, S_UNINSTALL }, { IDCANCEL, S_CLOSE },
    };
    wchar_t title[128];
    _snwprintf(title, 128, T(S_TITLE), CRTEMU_VERSION);
    title[127] = 0;
    SetWindowTextW(g_dlg, title);
    for (int i = 0; i < (int)(sizeof(items) / sizeof(items[0])); i++) SetDlgItemTextW(g_dlg, items[i].id, T(items[i].s));
    update_status();   /* status and the install button */
}

static void browse(void)
{
    wchar_t cur[PATHN];
    get_dir(cur);
    IFileOpenDialog* dlg = NULL;
    if (FAILED(CoCreateInstance(&CLSID_FileOpenDialog, NULL, CLSCTX_INPROC_SERVER, &IID_IFileOpenDialog, (void**)&dlg))) return;
    DWORD opts = 0;
    IFileOpenDialog_GetOptions(dlg, &opts);
    IFileOpenDialog_SetOptions(dlg, opts | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST);
    IFileOpenDialog_SetTitle(dlg, T(S_BROWSE_TITLE));
    IShellItem* start = NULL;
    if (cur[0] && dir_exists(cur) && SUCCEEDED(SHCreateItemFromParsingName(cur, NULL, &IID_IShellItem, (void**)&start)))
    {
        IFileOpenDialog_SetFolder(dlg, start);
        IShellItem_Release(start);
    }
    if (SUCCEEDED(IFileOpenDialog_Show(dlg, g_dlg)))
    {
        IShellItem* it = NULL;
        if (SUCCEEDED(IFileOpenDialog_GetResult(dlg, &it)))
        {
            PWSTR path = NULL;
            if (SUCCEEDED(IShellItem_GetDisplayName(it, SIGDN_FILESYSPATH, &path)))
            {
                wchar_t d[PATHN];
                wcsncpy(d, path, PATHN - 1);
                d[PATHN - 1] = 0;
                normalize_dir(d);
                /* picked "Data" or another subfolder of the game: take the game folder */
                if (!is_game_dir(d))
                {
                    wchar_t up[PATHN];
                    wcscpy(up, d);
                    wchar_t* bs = wcsrchr(up, L'\\');
                    if (bs && bs > up + 2) { *bs = 0; if (is_game_dir(up)) wcscpy(d, up); }
                }
                SetDlgItemTextW(g_dlg, IDC_PATH, d);
                CoTaskMemFree(path);
                update_status();
            }
            IShellItem_Release(it);
        }
    }
    IFileOpenDialog_Release(dlg);
}

/* the uninstall question with buttons in the setup's language: MessageBox labels Yes/No in the language of Windows */
static BOOL ask_uninstall(void)
{
    TASKDIALOG_BUTTON buttons[] = { { IDYES, T(S_UNINSTALL) }, { IDCANCEL, T(S_CANCEL) } };
    TASKDIALOGCONFIG tc = { sizeof(tc) };
    tc.hwndParent = g_dlg;
    tc.hInstance = g_inst;
    tc.dwFlags = TDF_ALLOW_DIALOG_CANCELLATION | TDF_POSITION_RELATIVE_TO_WINDOW;
    tc.pszWindowTitle = L"crt-emu";
    tc.pszMainIcon = TD_WARNING_ICON;
    tc.pszMainInstruction = T(S_ASK_UNINST);
    tc.pszContent = T(S_ASK_UNINST_MORE);
    tc.cButtons = 2;
    tc.pButtons = buttons;
    tc.nDefaultButton = IDCANCEL;
    int pressed = 0;
    if (SUCCEEDED(TaskDialogIndirect(&tc, &pressed, NULL, NULL))) return pressed == IDYES;
    wchar_t q[1024];
    _snwprintf(q, 1024, L"%s\n\n%s", T(S_ASK_UNINST), T(S_ASK_UNINST_MORE));
    q[1023] = 0;
    return MessageBoxW(g_dlg, q, L"crt-emu", MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2) == IDYES;
}

static void act(BOOL install)
{
    wchar_t d[PATHN];
    get_dir(d);
    BOOL hd = IsDlgButtonChecked(g_dlg, IDC_CHK_HD) == BST_CHECKED && IsWindowEnabled(GetDlgItem(g_dlg, IDC_CHK_HD));
    BOOL keep = IsDlgButtonChecked(g_dlg, IDC_CHK_KEEP) == BST_CHECKED;
    if (!install && !ask_uninstall()) return;
    HCURSOR old = SetCursor(LoadCursorW(NULL, IDC_WAIT));
    g_msg[0] = 0;
    int r = install ? do_install(d, hd, keep) : do_uninstall(d);
    if (r == RES_ELEVATE) r = run_elevated(g_dlg, install ? L"/install" : L"/uninstall", d, hd, keep);
    SetCursor(old);
    if (g_msg[0]) MessageBoxW(g_dlg, g_msg, L"crt-emu", r == RES_OK ? MB_ICONINFORMATION : MB_ICONWARNING);
    update_status();
}

static INT_PTR CALLBACK dlg_proc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    (void)l;
    switch (m)
    {
    case WM_INITDIALOG:
    {
        g_dlg = h;
        HICON big = (HICON)LoadImageW(g_inst, MAKEINTRESOURCEW(IDI_APP), IMAGE_ICON, GetSystemMetrics(SM_CXICON), GetSystemMetrics(SM_CYICON), 0);
        HICON small = (HICON)LoadImageW(g_inst, MAKEINTRESOURCEW(IDI_APP), IMAGE_ICON, GetSystemMetrics(SM_CXSMICON), GetSystemMetrics(SM_CYSMICON), 0);
        SendMessageW(h, WM_SETICON, ICON_BIG, (LPARAM)big);
        SendMessageW(h, WM_SETICON, ICON_SMALL, (LPARAM)small);
        HWND lang = GetDlgItem(h, IDC_LANG);
        for (int i = 0; i < LANG_N; i++) SendMessageW(lang, CB_ADDSTRING, 0, (LPARAM)LANG_NAME[i]);
        SendMessageW(lang, CB_SETCURSEL, g_lang, 0);
        HWND combo = GetDlgItem(h, IDC_PATH);
        HCURSOR old = SetCursor(LoadCursorW(NULL, IDC_WAIT));
        find_games(combo);
        SetCursor(old);
        if (SendMessageW(combo, CB_GETCOUNT, 0, 0) > 0) SendMessageW(combo, CB_SETCURSEL, 0, 0);
        CheckDlgButton(h, IDC_CHK_HD, BST_CHECKED);
        CheckDlgButton(h, IDC_CHK_KEEP, BST_CHECKED);
        apply_texts();
        return TRUE;
    }
    case WM_COMMAND:
        switch (LOWORD(w))
        {
        case IDC_LANG:
            if (HIWORD(w) == CBN_SELCHANGE)
            {
                LRESULT i = SendMessageW(GetDlgItem(h, IDC_LANG), CB_GETCURSEL, 0, 0);
                g_lang = i >= 0 && i < LANG_N ? (int)i : LANG_EN;
                save_lang();
                apply_texts();
            }
            return TRUE;
        case IDC_PATH:
            if (HIWORD(w) == CBN_SELCHANGE)
            {
                /* the edit text changes after this notification */
                PostMessageW(h, WM_APP, 0, 0);
            }
            else if (HIWORD(w) == CBN_EDITCHANGE)
                update_status();
            return TRUE;
        case IDC_BROWSE: browse(); return TRUE;
        case IDC_INSTALL: act(TRUE); return TRUE;
        case IDC_UNINSTALL: act(FALSE); return TRUE;
        case IDCANCEL: EndDialog(h, 0); return TRUE;
        }
        break;
    case WM_APP:
        update_status();
        return TRUE;
    }
    return FALSE;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmd, int show)
{
    (void)prev; (void)cmd; (void)show;
    g_inst = inst;
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);

    /* elevated relaunch: /install "dir" hd keep lang=xx  |  /uninstall "dir" hd keep lang=xx */
    if (argv && argc >= 3 && (wcscmp(argv[1], L"/install") == 0 || wcscmp(argv[1], L"/uninstall") == 0))
    {
        for (int i = 3; i < argc; i++)
            if (_wcsnicmp(argv[i], L"lang=", 5) == 0) g_lang = lang_from_code(argv[i] + 5);
        wchar_t d[PATHN];
        wcsncpy(d, argv[2], PATHN - 1);
        d[PATHN - 1] = 0;
        normalize_dir(d);
        BOOL install = wcscmp(argv[1], L"/install") == 0;
        /* hd and keep only from plain numbers: "/install dir lang=ru" must not read as keep=0 and drop the settings */
        BOOL hd = argc > 3 && iswdigit(argv[3][0]) ? _wtoi(argv[3]) != 0 : TRUE;
        BOOL keep = argc > 4 && iswdigit(argv[3][0]) && iswdigit(argv[4][0]) ? _wtoi(argv[4]) != 0 : TRUE;
        int r = install ? do_install(d, hd, keep) : do_uninstall(d);
        if (r == RES_ELEVATE) { fail_msg(T(S_E_ACCESS_ADMIN), d); r = RES_FAIL; }
        if (g_msg[0]) MessageBoxW(NULL, g_msg, L"crt-emu", r == RES_OK ? MB_ICONINFORMATION : MB_ICONWARNING);
        LocalFree(argv);
        return r;
    }
    if (argv) LocalFree(argv);

    load_lang();
    INITCOMMONCONTROLSEX icc = { sizeof(icc), ICC_STANDARD_CLASSES };
    InitCommonControlsEx(&icc);
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
    DialogBoxParamW(inst, MAKEINTRESOURCEW(IDD_MAIN), NULL, dlg_proc, 0);
    CoUninitialize();
    return 0;
}
