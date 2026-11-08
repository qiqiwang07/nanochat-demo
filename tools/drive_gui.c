/* drive_gui.c -- 远程驱动 AI 窗口：发一句话，读出历史内容（UTF-8 输出） */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static DWORD target_pid;
static HWND main_wnd;
static HWND edits[8];
static int n_edits;

static BOOL CALLBACK enum_top(HWND h, LPARAM lp) {
    (void)lp;
    DWORD pid = 0;
    GetWindowThreadProcessId(h, &pid);
    if (pid == target_pid) {
        wchar_t cls[64], ttl[256];
        GetClassNameW(h, cls, 64);
        GetWindowTextW(h, ttl, 256);
        printf("[top] h=%p pid=%lu class='%ls' title='%ls'\n", (void *)h, (unsigned long)pid, cls, ttl);
        if (wcscmp(cls, L"AIChatWnd") == 0) { main_wnd = h; }
    }
    return TRUE;
}
static BOOL CALLBACK enum_child(HWND h, LPARAM lp) {
    (void)lp;
    wchar_t cls[64], ttl[256];
    GetClassNameW(h, cls, 64);
    GetWindowTextW(h, ttl, 256);
    printf("[child] h=%p class='%ls' title='%ls'\n", (void *)h, cls, ttl);
    if (wcscmp(cls, L"Edit") == 0 && n_edits < 8) edits[n_edits++] = h;
    return TRUE;
}

int main(int argc, char **argv) {
    SetConsoleOutputCP(65001);
    if (argc < 3) { printf("用法: drive_gui <pid> <消息>\n"); return 1; }
    target_pid = (DWORD)atoi(argv[1]);
    /* 消息参数：PowerShell 传过来是系统 ANSI(GBK) 编码，转成宽字符 */
    int wlen = MultiByteToWideChar(CP_ACP, 0, argv[2], -1, NULL, 0);
    wchar_t *msg = (wchar_t *)malloc(sizeof(wchar_t) * wlen);
    MultiByteToWideChar(CP_ACP, 0, argv[2], -1, msg, wlen);

    EnumWindows(enum_top, 0);
    printf("== 枚举 main_wnd 的子窗口 ==\n");
    EnumChildWindows(main_wnd, enum_child, 0);
    printf("窗口=%p, Edit 控件 %d 个\n", (void *)main_wnd, n_edits);
    if (n_edits < 2) { printf("控件不足\n"); return 1; }
    HWND hist = edits[0], inp = edits[1];

    SendMessageW(inp, WM_SETTEXT, 0, (LPARAM)msg);
    SendMessageW(main_wnd, WM_COMMAND, 1, 0);
    Sleep(2500);

    int len = (int)SendMessageW(hist, WM_GETTEXTLENGTH, 0, 0);
    wchar_t *buf = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)(len + 2));
    SendMessageW(hist, WM_GETTEXT, (WPARAM)(len + 1), (LPARAM)buf);
    printf("== 历史字符数=%d，前 24 个字符的码点 ==\n", len);
    int shown = len < 24 ? len : 24;
    for (int i = 0; i < shown; i++) printf("U+%04X ", (unsigned)buf[i]);
    printf("\n== 转成 UTF-8 的字节 ==\n");
    int ulen = WideCharToMultiByte(CP_UTF8, 0, buf, -1, NULL, 0, NULL, NULL);
    char *u = (char *)malloc((size_t)ulen);
    WideCharToMultiByte(CP_UTF8, 0, buf, -1, u, ulen, NULL, NULL);
    fwrite(u, 1, (size_t)(ulen - 1), stdout);
    return 0;
}
