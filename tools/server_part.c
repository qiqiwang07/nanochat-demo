/* ====================== 回复缓冲与统一应答 ================================ */
#include <stdarg.h>
#include <direct.h>
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
    /* 未知话题：保证可读，不放手让模型乱说 */
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

/* ====================== 会话管理（内存 + 落盘）=========================== */
typedef struct {
    char   id[32];
    char   title[128];
    char  *log;               /* "### User: ...\n### Assistant: ...\n" */
    size_t loglen, logcap;
} Session;

#define MAXSESSION 64
static Session sessions[MAXSESSION];
static int n_sessions;
static unsigned sess_counter = 1;

static void sess_append_log(Session *s, const char *user, const char *ai) {
    char line[16384];
    snprintf(line, sizeof line, "### User: %s\n### Assistant: %s\n", user, ai);
    size_t l = strlen(line);
    if (s->loglen + l + 1 > s->logcap) {
        s->logcap = (s->logcap ? s->logcap * 2 : 8192);
        while (s->logcap < s->loglen + l + 1) s->logcap *= 2;
        s->log = (char *)realloc(s->log, s->logcap);
    }
    memcpy(s->log + s->loglen, line, l + 1);
    s->loglen += l;
    /* 落盘 */
    char path[128];
    snprintf(path, sizeof path, "sessions/%s.txt", s->id);
    FILE *f = fopen(path, "wb");
    if (f) { fwrite(s->log, 1, s->loglen, f); fclose(f); }
}

static Session *find_session(const char *id) {
    for (int i = 0; i < n_sessions; i++) if (!strcmp(sessions[i].id, id)) return &sessions[i];
    return NULL;
}

static Session *new_session(void) {
    if (n_sessions >= MAXSESSION) return NULL;
    Session *s = &sessions[n_sessions++];
    snprintf(s->id, sizeof s->id, "s%u", sess_counter++);
    s->title[0] = 0;
    s->log = (char *)malloc(8192);
    s->log[0] = 0;
    s->loglen = 0;
    s->logcap = 8192;
    return s;
}

static void load_sessions(void) {
    _mkdir("sessions");
    char pattern[128] = "sessions/*.txt";
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (n_sessions >= MAXSESSION) break;
        Session *s = &sessions[n_sessions];
        snprintf(s->id, sizeof s->id, "%.*s", (int)(strlen(fd.cFileName) - 4), fd.cFileName);
        unsigned c;
        sscanf(s->id, "s%u", &c);
        if (c >= sess_counter) sess_counter = c + 1;
        s->title[0] = 0;
        s->log = NULL; s->loglen = 0; s->logcap = 0;
        char path[160];
        snprintf(path, sizeof path, "sessions/%s", fd.cFileName);
        FILE *f = fopen(path, "rb");
        if (f) {
            fseek(f, 0, SEEK_END);
            long sz = ftell(f);
            fseek(f, 0, SEEK_SET);
            s->log = (char *)malloc((size_t)sz + 1);
            if (fread(s->log, 1, (size_t)sz, f) == (size_t)sz) { s->log[sz] = 0; s->loglen = (size_t)sz; s->logcap = (size_t)sz + 1; }
            fclose(f);
        }
        if (!s->log) { s->log = (char *)malloc(8192); s->log[0] = 0; s->logcap = 8192; }
        /* 标题：第一句用户的话 */
        char *p = strstr(s->log, "### User: ");
        if (p) {
            p += 10;
            size_t k = 0;
            while (p[k] && p[k] != '\n' && k < sizeof s->title - 1) { s->title[k] = p[k]; k++; }
            s->title[k] = 0;
        }
        n_sessions++;
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

/* ====================== HTTP 服务器（WinSock）============================ */
static void json_escape(const char *s, char *o, size_t cap) {
    size_t k = 0;
    for (const char *p = s; *p && k + 4 < cap; p++) {
        if (*p == '"' || *p == '\\') { o[k++] = '\\'; o[k++] = *p; }
        else if (*p == '\n') { o[k++] = '\\'; o[k++] = 'n'; }
        else if (*p == '\r') { o[k++] = '\\'; o[k++] = 'r'; }
        else o[k++] = *p;
    }
    o[k] = 0;
}

static void http_send(SOCKET c, const char *body, size_t body_len, const char *ctype) {
    char hdr[512];
    snprintf(hdr, sizeof hdr,
             "HTTP/1.1 200 OK\r\nContent-Type: %s; charset=utf-8\r\n"
             "Content-Length: %d\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n",
             ctype, (int)body_len);
    send(c, hdr, (int)strlen(hdr), 0);
    send(c, body, (int)body_len, 0);
}

/* 从请求体里取 "key":"value" 的 value（不做完整 JSON 解析，够用） */
static int json_get(const char *body, const char *key, char *out, size_t cap) {
    char pat[64];
    snprintf(pat, sizeof pat, "\"%s\":\"", key);
    const char *p = strstr(body, pat);
    if (!p) return 0;
    p += strlen(pat);
    size_t k = 0;
    while (*p && *p != '"' && k < cap - 1) out[k++] = *p++;
    out[k] = 0;
    return 1;
}

/* 读完整 HTTP 请求：先读头，再按 Content-Length 把体读全 */
static int read_request(SOCKET c, char *buf, int cap) {
    int total = 0;
    buf[0] = 0;
    for (;;) {
        if (total >= cap - 1) break;
        int n = recv(c, buf + total, cap - 1 - total, 0);
        if (n <= 0) break;
        total += n;
        buf[total] = 0;
        char *hdr_end = strstr(buf, "\r\n\r\n");
        if (!hdr_end) continue;                       /* 头还没读完 */
        int content_len = 0;
        const char *cl = strstr(buf, "Content-Length:");
        if (!cl) cl = strstr(buf, "content-length:");
        if (cl) content_len = atoi(cl + 15);
        int have = total - (int)((hdr_end + 4) - buf);
        if (have >= content_len) break;               /* 体已收全 */
    }
    return total;
}

static void serve(int port) {
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
    SOCKET s = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons((u_short)port);
    if (bind(s, (struct sockaddr *)&addr, sizeof addr) != 0) {
        fprintf(stderr, "绑定端口 %d 失败（可能已有一个实例在运行）\n", port);
        return;
    }
    listen(s, 8);
    printf("AI 服务已启动: http://127.0.0.1:%d（关闭本窗口退出）\n", port);
    fflush(stdout);
    fprintf(stderr, "[srv] listening on %d\n", port);
    fflush(stderr);
    ShellExecuteA(NULL, "open", "http://127.0.0.1:8090", NULL, NULL, SW_SHOWNORMAL);

    for (;;) {
        SOCKET c = accept(s, NULL, NULL);
        if (c == INVALID_SOCKET) continue;
        static char req[131072];
        int n = read_request(c, req, sizeof req);
        if (n <= 0) { closesocket(c); continue; }
        fprintf(stderr, "[srv] req n=%d head=%.40s\n", n, req);
        fflush(stderr);

        if (strncmp(req, "GET /sessions", 13) == 0) {
            char resp[32768];
            size_t k = 0;
            k += (size_t)snprintf(resp + k, sizeof resp - k, "{\"sessions\":[");
            for (int i = 0; i < n_sessions; i++) {
                char tesc[256];
                json_escape(sessions[i].title[0] ? sessions[i].title : "新会话", tesc, sizeof tesc);
                k += (size_t)snprintf(resp + k, sizeof resp - k, "%s{\"id\":\"%s\",\"title\":\"%s\"}",
                                      i ? "," : "", sessions[i].id, tesc);
            }
            k += (size_t)snprintf(resp + k, sizeof resp - k, "]}");
            http_send(c, resp, k, "application/json");
        } else if (strncmp(req, "POST /new", 9) == 0) {
            Session *ns = new_session();
            char resp[256];
            int k = snprintf(resp, sizeof resp, "{\"id\":\"%s\"}", ns ? ns->id : "");
            http_send(c, resp, (size_t)k, "application/json");
        } else if (strncmp(req, "GET /session", 12) == 0) {
            char id[64] = "";
            const char *q = strstr(req, "id=");
            if (q) {
                q += 3;
                size_t k = 0;
                while (*q && *q != ' ' && *q != '&' && k < sizeof id - 1) id[k++] = *q++;
                id[k] = 0;
            }
            Session *sess = find_session(id);
            char *resp = (char *)malloc(65536);
            if (!sess) {
                strcpy(resp, "{\"log\":\"\"}");
            } else {
                char *esc = (char *)malloc(65536);
                json_escape(sess->log ? sess->log : "", esc, 65536);
                snprintf(resp, 65536, "{\"log\":\"%s\"}", esc);
                free(esc);
            }
            http_send(c, resp, strlen(resp), "application/json");
            free(resp);
        } else if (strncmp(req, "POST /chat", 10) == 0) {
            char text[4096] = "", sid[64] = "";
            char *body = strstr(req, "\r\n\r\n");
            if (body) {
                json_get(body, "text", text, sizeof text);
                json_get(body, "session", sid, sizeof sid);
            }
            fprintf(stderr, "[srv] text='%s' sid='%s' body='%.80s'\n",
                    text, sid, body ? body : "(null)");
            fflush(stderr);
            char out[8192];
            answer_q(text, out, sizeof out);
            Session *sess = find_session(sid);
            if (!sess) sess = new_session();
            if (sess) {
                if (!sess->title[0]) {
                    size_t k = 0;
                    while (text[k] && k < sizeof sess->title - 1) { sess->title[k] = text[k]; k++; }
                    sess->title[k] = 0;
                }
                sess_append_log(sess, text, out);
            }
            char esc[16384], resp[32768];
            json_escape(out, esc, sizeof esc);
            int k = snprintf(resp, sizeof resp, "{\"reply\":\"%s\",\"session\":\"%s\"}", esc,
                             sess ? sess->id : "");
            fprintf(stderr, "[srv] reply k=%d session=%s\n", k, sess ? sess->id : "(null)");
            fflush(stderr);
            http_send(c, resp, (size_t)k, "application/json");
        } else if (strncmp(req, "GET / ", 6) == 0 || strncmp(req, "GET /chat.html", 15) == 0 ||
                   strncmp(req, "GET /favicon", 12) == 0) {
            FILE *f = fopen("chat.html", "rb");
            if (f) {
                static char page[131072];
                size_t pl = fread(page, 1, sizeof page - 1, f);
                fclose(f);
                page[pl] = 0;
                http_send(c, page, pl, "text/html");
            } else {
                const char *err = "chat.html not found";
                http_send(c, err, strlen(err), "text/plain");
            }
        } else {
            const char *err = "404";
            http_send(c, err, strlen(err), "text/plain");
        }
        closesocket(c);
    }
}

/* ====================== 入口 ============================================ */
int main(int argc, char **argv) {
#ifdef _WIN32
    SetConsoleOutputCP(65001);
#endif
    if (argc < 3) {
        fprintf(stderr, "用法: server <corpus.txt> <权重.bin> [端口]\n");
        return 1;
    }
    if (load_corpus(argv[1]) != 0) return 1;
    BT = B * T;
    init_params();
    alloc_activations();
    if (load_weights(argv[2]) != 0) return 1;
    load_sessions();
    serve(argc > 3 ? atoi(argv[3]) : 8090);
    return 0;
}
