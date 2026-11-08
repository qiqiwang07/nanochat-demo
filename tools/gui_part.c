/* ====================== 回复缓冲与统一应答 ================================ */
#include <stdarg.h>
static char RB[16384];
static size_t RL;

static void rep(const char *s) {
    size_t l = strlen(s);
    if (RL + l < sizeof RB - 1) { memcpy(RB + RL, s, l); RL += l; RB[RL] = 0; }
}
static void repf(const char *fmt, ...) {
    char tmp[2048];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(tmp, sizeof tmp, fmt, ap);
    va_end(ap);
    rep(tmp);
}

static int is_arith_s(const char *s) {
    int digits = 0;
    for (; *s; s++) {
        if (isdigit((unsigned char)*s)) { digits = 1; continue; }
        if (strchr("+-*/^%(). \t", *s)) continue;
        return 0;
    }
    return digits;
}

/* 会话记忆：只对神经网络部分生效 */
static char session[8192];
static size_t sess_len;

static void sess_append(const char *s) {
    size_t l = strlen(s);
    if (sess_len + l > sizeof session - 1) { sess_len = 0; }
    memcpy(session + sess_len, s, l);
    sess_len += l;
    session[sess_len] = 0;
}

static void answer_q(const char *q, char *out, size_t cap) {
    RL = 0; RB[0] = 0;
    if (chat_reply(q)) { snprintf(out, cap, "%s", RB); return; }
    if (is_arith_s(q)) {
        double v = eval_expr(q);
        if (!isnan(v)) {
            snprintf(out, cap, "%s = %.10g\n（精确计算结果，可自行验证。）", q, v);
            return;
        }
    }
    if (strchr(q, '=') && (strchr(q, 'x') || strchr(q, 'X'))) {
        double x; char why[512];
        if (solve_linear(q, &x, why, sizeof why)) {
            snprintf(out, cap, "x = %.6g\n%s", x, why);
            return;
        }
    }
    if (try_rules(q)) { snprintf(out, cap, "%s", RB); return; }

    /* 未知话题：小模型(0.89M)会胡说，为保证每条回复都能读懂，统一回引导话 */
    {
        static const char *fb[] = {
            "这个话题我还在学。目前我擅长：聊天寒暄（心情、天气、吃饭、学习等）、算算术、解方程、解应用题。你可以问我“你会什么”。",
            "这个我暂时答不上来。要不考我一道数学题，比如 12+15*3，或者聊聊今天过得怎么样？",
            "我还不太懂这个。试试问我：2x+3=7，或者“一件衣服打八折多少钱”。",
        };
        snprintf(out, cap, "%s", fb[g_rr++ % 3]);
        return;
    }
}

/* ====================== Win32 聊天窗口 ================================== */
static HWND g_hist, g_inp;
static WNDPROC g_oldInp;

static wchar_t *utf8_to_w(const char *u) {
    int len = MultiByteToWideChar(CP_UTF8, 0, u, -1, NULL, 0);
    wchar_t *w = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)len);
    MultiByteToWideChar(CP_UTF8, 0, u, -1, w, len);
    return w;
}
static char *w_to_utf8(const wchar_t *w) {
    int len = WideCharToMultiByte(CP_UTF8, 0, w, -1, NULL, 0, NULL, NULL);
    char *u = (char *)malloc((size_t)len);
    WideCharToMultiByte(CP_UTF8, 0, w, -1, u, len, NULL, NULL);
    return u;
}

static void append_history(const wchar_t *who, const wchar_t *text) {
    int len = GetWindowTextLengthW(g_hist);
    SendMessageW(g_hist, EM_SETSEL, (WPARAM)len, (LPARAM)len);
    wchar_t line[16384];
    /* 不用 swprintf：MinGW 的 %s 有 MS 语义，会把宽指针当窄串读，窗口显示乱码 */
    line[0] = 0;
    wcscat(line, who);
    wcscat(line, L"\uFF1A");
    wcscat(line, text);
    wcscat(line, L"\r\n\r\n");
    SendMessageW(g_hist, EM_REPLACESEL, FALSE, (LPARAM)line);
}

static void do_send(void) {
    wchar_t wt[4096];
    GetWindowTextW(g_inp, wt, 4096);
    if (!wt[0]) return;
    SetWindowTextW(g_inp, L"");
    append_history(L"我", wt);
    char *u = w_to_utf8(wt);
    char out[8192];
    answer_q(u, out, sizeof out);
    free(u);
    wchar_t *wo = utf8_to_w(out);
    append_history(L"AI", wo);
    free(wo);
    /* 诊断日志：把每一轮问答写到文件里（UTF-8），方便排查 */
    FILE *lf = fopen("chat_log.txt", "ab");
    if (lf) {
        char *w2 = w_to_utf8(wt);
        fprintf(lf, "我：%s\nAI：%s\n---\n", w2, out);
        free(w2);
        fclose(lf);
    }
}

static LRESULT CALLBACK inp_proc(HWND h, UINT m, WPARAM w, LPARAM l) {
    if (m == WM_KEYDOWN && w == VK_RETURN) {
        SendMessage(GetParent(h), WM_COMMAND, 1, 0);
        return 0;
    }
    return CallWindowProc(g_oldInp, h, m, w, l);
}

static LRESULT CALLBACK wndproc(HWND h, UINT msg, WPARAM w, LPARAM l) {
    switch (msg) {
    case WM_CREATE: {
        g_hist = CreateWindowW(L"EDIT", NULL,
            WS_CHILD | WS_VISIBLE | ES_MULTILINE | ES_READONLY | WS_VSCROLL | ES_AUTOVSCROLL,
            12, 12, 520, 400, h, NULL, NULL, NULL);
        g_inp = CreateWindowW(L"EDIT", NULL,
            WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL,
            12, 428, 408, 30, h, NULL, NULL, NULL);
        CreateWindowW(L"BUTTON", L"发送",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            432, 426, 100, 34, h, (HMENU)1, NULL, NULL);
        HFONT f = CreateFontW(-17, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY,
            DEFAULT_PITCH | FF_DONTCARE, L"Microsoft YaHei");
        SendMessageW(g_hist, WM_SETFONT, (WPARAM)f, TRUE);
        SendMessageW(g_inp, WM_SETFONT, (WPARAM)f, TRUE);
        g_oldInp = (WNDPROC)SetWindowLongPtrW(g_inp, GWLP_WNDPROC, (LONG_PTR)inp_proc);
        append_history(L"AI", L"你好！我是 AI 助手，用 C 语言写的，模型是本机自己训练的。\r\n想聊什么直接输入，回车或点“发送”。");
        SetFocus(g_inp);
        return 0;
    }
    case WM_COMMAND:
        if (LOWORD(w) == 1) do_send();
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, msg, w, l);
}

/* ====================== 入口 ============================================ */
int main(int argc, char **argv) {
    if (argc < 3) {
        MessageBoxA(NULL, "用法: gui <corpus.txt> <权重.bin>\n例如: gui zhchat_corpus.txt zhchat.bin",
                    "AI 助手", MB_OK);
        return 1;
    }
    if (load_corpus(argv[1]) != 0) return 1;
    BT = B * T;
    init_params();
    alloc_activations();
    if (load_weights(argv[2]) != 0) return 1;

    WNDCLASSW wc;
    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = wndproc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"AIChatWnd";
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    RegisterClassW(&wc);
    HWND h = CreateWindowW(L"AIChatWnd", L"AI 助手（纯 C）",
        WS_OVERLAPPEDWINDOW & ~WS_MAXIMIZEBOX & ~WS_THICKFRAME,
        CW_USEDEFAULT, CW_USEDEFAULT, 560, 530, NULL, NULL, wc.hInstance, NULL);
    ShowWindow(h, SW_SHOW);
    MSG m;
    while (GetMessageW(&m, NULL, 0, 0)) {
        TranslateMessage(&m);
        DispatchMessageW(&m);
    }
    return 0;
}
