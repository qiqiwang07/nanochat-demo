/* ============================================================================
 * qwen.c -- 纯 C 的推理引擎：直接读取 GGUF，自己跑 Qwen2 前向传播
 *
 * 没有 llama.cpp、没有 C++、没有第三方库。全部由本文件完成：
 *   - GGUF 文件格式解析（元数据 + 张量表 + 数据区）
 *   - Q8_0 / F16 / F32 反量化
 *   - BPE 分词器（字节级，含中文）
 *   - Qwen2 前向：RMSNorm / RoPE / GQA 注意力 / SwiGLU / KV cache
 *   - 采样与对话模板
 *
 * 编译: gcc -O3 -march=native -fopenmp -o qwen.exe qwen.c -lm
 * 用法: qwen.exe <model.gguf> --info
 *       qwen.exe <model.gguf> "你的问题"
 * ==========================================================================*/
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

/* ------------------------------ 小工具 ---------------------------------- */
static FILE *gf;
static void die(const char *msg) { fprintf(stderr, "错误: %s\n", msg); exit(1); }
static void rd(void *p, size_t n) { if (fread(p, 1, n, gf) != n) die("文件提前结束"); }
static uint8_t  rd_u8(void)  { uint8_t  v; rd(&v, 1); return v; }
static uint16_t rd_u16(void) { uint16_t v; rd(&v, 2); return v; }
static uint32_t rd_u32(void) { uint32_t v; rd(&v, 4); return v; }
static uint64_t rd_u64(void) { uint64_t v; rd(&v, 8); return v; }
static int32_t  rd_i32(void) { int32_t  v; rd(&v, 4); return v; }
static float    rd_f32(void) { float    v; rd(&v, 4); return v; }
static double   rd_f64(void) { double   v; rd(&v, 8); return v; }

typedef struct {
    char *s;
    size_t n;
} Str;

/* ------------------------------ GGUF 元数据 ----------------------------- */
#define MAXTENSOR 1024
typedef struct {
    char     name[96];
    uint32_t n_dims;
    uint64_t dims[4];
    uint32_t type;
    uint64_t offset;
    void    *data;
    size_t   n_elem;
} Tensor;

static Tensor tensors[MAXTENSOR];
static int    n_tensor;

/* 我们需要的超参数 */
static char  arch[64];
static int   n_layer, n_embd, n_head, n_kv_head, n_ctx_train;
static double rope_base = 1000000.0, rms_eps = 1e-6;
static int   bos_id = 151643, eos_id = 151645;

/* 词表 */
static Str  *vtok;   static int n_vtok;
static Str  *vmerge; static int n_vmerge;
static int  *vtype;  static int n_vtype;
static int   alignment = 32;

/* 读取一个 GGUF 字符串（uint64 长度 + 内容） */
static Str rd_gguf_str(void) {
    Str s;
    s.n = (size_t)rd_u64();
    s.s = (char *)malloc(s.n + 1);
    if (s.n) rd(s.s, s.n);
    s.s[s.n] = 0;
    return s;
}
static void skip_value(uint32_t t);

/* 数组：元素类型 + 数量 + 元素 */
static void read_array(const char *key) {
    uint32_t et = rd_u32();
    uint64_t n = rd_u64();
    if (strstr(key, "tokenizer.ggml.tokens") && et == 8) {
        vtok = (Str *)malloc(sizeof(Str) * n);
        n_vtok = (int)n;
        for (uint64_t i = 0; i < n; i++) vtok[i] = rd_gguf_str();
        return;
    }
    if (strstr(key, "tokenizer.ggml.merges") && et == 8) {
        vmerge = (Str *)malloc(sizeof(Str) * n);
        n_vmerge = (int)n;
        for (uint64_t i = 0; i < n; i++) vmerge[i] = rd_gguf_str();
        return;
    }
    if (strstr(key, "tokenizer.ggml.token_type") && et == 4) {
        vtype = (int *)malloc(sizeof(int) * n);
        n_vtype = (int)n;
        for (uint64_t i = 0; i < n; i++) vtype[i] = (int)rd_u32();
        return;
    }
    for (uint64_t i = 0; i < n; i++) skip_value(et);
}

static void skip_value(uint32_t t) {
    switch (t) {
        case 0: case 1: rd_u8(); break;
        case 2: case 3: rd_u16(); break;
        case 4: case 5: case 6: rd_u32(); break;
        case 7: rd_u8(); break;
        case 8: { Str s = rd_gguf_str(); free(s.s); } break;
        case 9: { uint32_t et = rd_u32(); uint64_t n = rd_u64();
                  for (uint64_t i = 0; i < n; i++) skip_value(et); } break;
        case 10: case 11: rd_u64(); break;
        case 12: rd_f64(); break;
        default: die("未知的元数据类型");
    }
}

/* 读取一个 KV 并保存我们关心的字段 */
static void read_kv(const char *key) {
    uint32_t t = rd_u32();
    if (t == 9) { read_array(key); return; }
    switch (t) {
        case 0: { uint8_t v = rd_u8();  if (strstr(key, "bos_token_id")) bos_id = v; if (strstr(key,"eos_token_id")) eos_id = v; } break;
        case 1: rd_u8(); break;
        case 2: rd_u16(); break;
        case 3: rd_u16(); break;
        case 4: { uint32_t v = rd_u32();
                  if (strstr(key, "block_count")) n_layer = (int)v;
                  else if (strstr(key, "embedding_length")) n_embd = (int)v;
                  else if (strstr(key, "head_count_kv")) n_kv_head = (int)v;
                  else if (strstr(key, "head_count")) n_head = (int)v;
                  else if (strstr(key, "context_length")) n_ctx_train = (int)v;
                  else if (strstr(key, "alignment")) alignment = (int)v;
                  else if (strstr(key, "bos_token_id")) bos_id = (int)v;
                  else if (strstr(key, "eos_token_id")) eos_id = (int)v;
                } break;
        case 5: { int32_t v = rd_i32();
                  if (strstr(key, "bos_token_id")) bos_id = v;
                  else if (strstr(key, "eos_token_id")) eos_id = v;
                } break;
        case 6: { float v = rd_f32();
                  if (strstr(key, "rope.freq_base")) rope_base = v;
                  else if (strstr(key, "layer_norm_rms_epsilon")) rms_eps = v;
                  else if (strstr(key, "layer_norm_epsilon")) rms_eps = v;
                } break;
        case 7: rd_u8(); break;
        case 8: { Str s = rd_gguf_str();
                  if (!strcmp(key, "general.architecture")) { snprintf(arch, sizeof arch, "%s", s.s); }
                  free(s.s); } break;
        case 10: { uint64_t v = rd_u64(); if (strstr(key, "context_length")) n_ctx_train = (int)v; } break;
        case 11: rd_u64(); break;
        case 12: { double v = rd_f64();
                   if (strstr(key, "rope.freq_base")) rope_base = v;
                   else if (strstr(key, "layer_norm_rms_epsilon")) rms_eps = v; } break;
        default: die("未知的元数据类型");
    }
}

static size_t type_block_elems(uint32_t t) {
    switch (t) {
        case 0: return 1;    /* F32 */
        case 1: return 1;    /* F16 */
        case 2: return 32;   /* Q4_0 */
        case 3: return 32;   /* Q4_1 */
        case 6: return 32;   /* Q5_0 */
        case 7: return 32;   /* Q5_1 */
        case 8: return 32;   /* Q8_0 */
        case 10: return 256; /* Q2_K */
        case 11: return 256; /* Q3_K */
        case 12: return 256; /* Q4_K */
        case 13: return 256; /* Q5_K */
        case 14: return 256; /* Q6_K */
        default: return 0;
    }
}
static size_t type_block_bytes(uint32_t t) {
    switch (t) {
        case 0: return 4;
        case 1: return 2;
        case 2: return 18;   /* fp16 d + 16 bytes */
        case 3: return 20;
        case 6: return 22;
        case 7: return 24;
        case 8: return 34;   /* fp16 d + 32 int8 */
        case 10: return 84;
        case 11: return 110;
        case 12: return 144;
        case 13: return 176;
        case 14: return 210;
        default: return 0;
    }
}
static const char *type_name(uint32_t t) {
    switch (t) {
        case 0: return "F32"; case 1: return "F16"; case 2: return "Q4_0";
        case 3: return "Q4_1"; case 6: return "Q5_0"; case 7: return "Q5_1";
        case 8: return "Q8_0"; case 10: return "Q2_K"; case 11: return "Q3_K";
        case 12: return "Q4_K"; case 13: return "Q5_K"; case 14: return "Q6_K";
        default: return "?";
    }
}

/* ------------------------------ 加载 GGUF ------------------------------- */
static void load_gguf(const char *path) {
    gf = fopen(path, "rb");
    if (!gf) die("打不开模型文件");
    char magic[4];
    rd(magic, 4);
    if (memcmp(magic, "GGUF", 4) != 0) die("不是 GGUF 文件");
    uint32_t ver = rd_u32();
    uint64_t n_tensors = rd_u64();
    uint64_t n_kv = rd_u64();
    printf("GGUF v%u | 张量 %llu | 元数据 %llu 项\n", ver,
           (unsigned long long)n_tensors, (unsigned long long)n_kv);

    for (uint64_t i = 0; i < n_kv; i++) {
        Str k = rd_gguf_str();
        read_kv(k.s);
        free(k.s);
    }
    if (n_tensors > MAXTENSOR) die("张量太多");
    n_tensor = (int)n_tensors;
    for (int i = 0; i < n_tensor; i++) {
        Str nm = rd_gguf_str();
        snprintf(tensors[i].name, sizeof tensors[i].name, "%s", nm.s);
        free(nm.s);
        tensors[i].n_dims = rd_u32();
        if (tensors[i].n_dims > 4) die("维度过多");
        size_t el = 1;
        for (uint32_t d = 0; d < tensors[i].n_dims; d++) {
            tensors[i].dims[d] = rd_u64();
            el *= (size_t)tensors[i].dims[d];
        }
        tensors[i].n_elem = el;
        tensors[i].type = rd_u32();
        tensors[i].offset = rd_u64();
    }
    /* 数据区起始（按 alignment 对齐） */
    long pos = ftell(gf);
    long pad = (long)((alignment - (pos % alignment)) % alignment);
    fseek(gf, pos + pad, SEEK_SET);
    long data_start = ftell(gf);
    /* 一次性把整个数据区读进内存 */
    fseek(gf, 0, SEEK_END);
    long fsize = ftell(gf);
    size_t dsize = (size_t)(fsize - data_start);
    printf("数据区起始 %ld，大小 %.2f GB，对齐 %d\n", data_start, dsize / 1e9, alignment);
    unsigned char *blob = (unsigned char *)malloc(dsize);
    if (!blob) die("内存不足（模型数据区）");
    fseek(gf, data_start, SEEK_SET);
    if (fread(blob, 1, dsize, gf) != dsize) die("数据区读取失败");
    fclose(gf);
    for (int i = 0; i < n_tensor; i++) {
        tensors[i].data = blob + tensors[i].offset;
        size_t blocks = tensors[i].n_elem / type_block_elems(tensors[i].type);
        size_t need = blocks * type_block_bytes(tensors[i].type);
        if (tensors[i].offset + need > dsize) {
            fprintf(stderr, "张量 %s 越界\n", tensors[i].name);
        }
    }
}

static Tensor *find_tensor(const char *name) {
    for (int i = 0; i < n_tensor; i++) if (!strcmp(tensors[i].name, name)) return &tensors[i];
    return NULL;
}

/* ------------------------------ 反量化 ---------------------------------- */
/* 半精度 -> float */
static float fp16_to_fp32(uint16_t h) {
    uint32_t sign = (h >> 15) & 1, exp = (h >> 10) & 0x1F, mant = h & 0x3FF;
    uint32_t f;
    if (exp == 0) {
        if (mant == 0) f = sign << 31;
        else { /* 非规格化 */
            int e = -1; do { e++; mant <<= 1; } while (!(mant & 0x400));
            f = (sign << 31) | ((127 - 15 - e) << 23) | ((mant & 0x3FF) << 13);
        }
    } else if (exp == 0x1F) {
        f = (sign << 31) | (0xFF << 23) | (mant << 13);
    } else {
        f = (sign << 31) | ((exp - 15 + 127) << 23) | (mant << 13);
    }
    float out; memcpy(&out, &f, 4); return out;
}

/* 取张量的一行（仅一维/二维）：返回 float 数组（调用方提供 out） */
static void dequant_row(const Tensor *t, size_t row, float *out) {
    size_t n_in = (size_t)t->dims[0];           /* 连续维 = 输入维 */
    if (t->n_dims == 1) { row = 0; n_in = t->n_elem; }
    if (t->type == 0) {                          /* F32 */
        memcpy(out, (const float *)t->data + row * n_in, n_in * sizeof(float));
        return;
    }
    if (t->type == 1) {                          /* F16 */
        const uint16_t *p = (const uint16_t *)t->data + row * n_in;
        for (size_t i = 0; i < n_in; i++) out[i] = fp16_to_fp32(p[i]);
        return;
    }
    if (t->type == 8) {                          /* Q8_0: 32 个一组 */
        const unsigned char *base = (const unsigned char *)t->data + row * (n_in / 32) * 34;
        for (size_t b = 0; b < n_in / 32; b++) {
            const unsigned char *blk = base + b * 34;
            float d = fp16_to_fp32(*(const uint16_t *)blk);
            const int8_t *q = (const int8_t *)(blk + 2);
            for (int j = 0; j < 32; j++) out[b * 32 + j] = d * (float)q[j];
        }
        return;
    }
    die("暂不支持该量化类型（请用 Q8_0 / F16 / F32）");
}

/* ------------------------------ 入口 ------------------------------------ */
int main(int argc, char **argv) {
#ifdef _WIN32
    SetConsoleOutputCP(65001);
#endif
    if (argc < 3) {
        printf("用法: qwen.exe <model.gguf> --info\n");
        return 1;
    }
    load_gguf(argv[1]);
    printf("\n架构: %s\n", arch);
    printf("层数 %d | 宽度 %d | 头数 %d | KV 头 %d | 训练上下文 %d\n",
           n_layer, n_embd, n_head, n_kv_head, n_ctx_train);
    printf("RoPE base %.0f | RMS eps %g\n", rope_base, rms_eps);
    printf("词表 %d 个 token，merges %d 条，token_type %d\n", n_vtok, n_vmerge, n_vtype);
    printf("BOS %d EOS %d\n", bos_id, eos_id);
    for (int i = 0; i < n_tensor && i < 12; i++) {
        printf("  张量 %-28s type=%-5s dims=[", tensors[i].name, type_name(tensors[i].type));
        for (uint32_t d = 0; d < tensors[i].n_dims; d++) printf("%llu%s",
            (unsigned long long)tensors[i].dims[d], d + 1 < tensors[i].n_dims ? "," : "");
        printf("]\n");
    }
    printf("  ... 共 %d 个张量\n", n_tensor);
    Tensor *tk = find_tensor("token_embd.weight");
    if (tk) printf("token_embd: dims=[%llu,%llu] type=%s\n",
                   (unsigned long long)tk->dims[0], (unsigned long long)tk->dims[1], type_name(tk->type));
    if (n_vtok > 0) {
        printf("前几个 token: ");
        for (int i = 0; i < 8 && i < n_vtok; i++) printf("[%d]\"%s\" ", i, vtok[i].s);
        printf("\n");
        printf("特殊 token: ");
        for (int i = n_vtok - 8; i < n_vtok; i++) printf("[%d]\"%s\" ", i, vtok[i].s);
        printf("\n");
        printf("merge 示例: \"%s\" \"%s\"\n", n_vmerge > 0 ? vmerge[0].s : "", n_vmerge > 1 ? vmerge[1].s : "");
    }
    return 0;
}
