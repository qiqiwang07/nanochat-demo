/* swiglu_test.c -- 单独验证 SwiGLU 前向/反向推导
 *
 * 做法：随机 u、g、上游梯度 d，
 *   解析梯度：用我们的公式算 du、dg
 *   数值梯度：逐元素扰动 u（或 g），重算 act，与 d 点积，中心差分对比
 * 两者一致才说明公式和代码没问题。
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#define N 8

static float sigmoidf_(float x) { return 1.0f / (1.0f + expf(-x)); }

/* 前向：act = SiLU(u) * g */
static void fwd(const float *u, const float *g, float *act, int n) {
    for (int i = 0; i < n; i++) {
        float s = sigmoidf_(u[i]);
        act[i] = (u[i] * s) * g[i];
    }
}

/* 反向：给定上游梯度 d，求 du、dg */
static void bwd(const float *u, const float *g, const float *d, float *du, float *dg, int n) {
    for (int i = 0; i < n; i++) {
        float s = sigmoidf_(u[i]);
        float silu = u[i] * s;
        float dsilu = s * (1.0f + u[i] * (1.0f - s));
        du[i] = d[i] * g[i] * dsilu;
        dg[i] = d[i] * silu;
    }
}

int main(void) {
    float u[N], g[N], d[N], act[N], du[N], dg[N];
    srand(12345);
    for (int i = 0; i < N; i++) {
        u[i] = ((float)rand() / RAND_MAX - 0.5f) * 4.0f;   /* [-2, 2] */
        g[i] = ((float)rand() / RAND_MAX - 0.5f) * 4.0f;
        d[i] = ((float)rand() / RAND_MAX - 0.5f) * 2.0f;
    }

    bwd(u, g, d, du, dg, N);

    const float eps = 1e-3f;
    float worst_u = 0, worst_g = 0;

    /* 对 u 做数值微分 */
    for (int j = 0; j < N; j++) {
        float orig = u[j];
        u[j] = orig + eps; fwd(u, g, act, N);
        float fp = 0; for (int i = 0; i < N; i++) fp += act[i] * d[i];
        u[j] = orig - eps; fwd(u, g, act, N);
        float fm = 0; for (int i = 0; i < N; i++) fm += act[i] * d[i];
        u[j] = orig;
        float num = (fp - fm) / (2 * eps);
        float rel = fabsf(num - du[j]) / (fabsf(num) + fabsf(du[j]) + 1e-6f);
        if (rel > worst_u) worst_u = rel;
        printf("  u[%d] 数值=%+.6f 解析=%+.6f 相对误差=%.2e %s\n",
               j, num, du[j], rel, rel < 1e-3f ? "OK" : "BAD");
    }

    /* 对 g 做数值微分 */
    for (int j = 0; j < N; j++) {
        float orig = g[j];
        g[j] = orig + eps; fwd(u, g, act, N);
        float fp = 0; for (int i = 0; i < N; i++) fp += act[i] * d[i];
        g[j] = orig - eps; fwd(u, g, act, N);
        float fm = 0; for (int i = 0; i < N; i++) fm += act[i] * d[i];
        g[j] = orig;
        float num = (fp - fm) / (2 * eps);
        float rel = fabsf(num - dg[j]) / (fabsf(num) + fabsf(dg[j]) + 1e-6f);
        if (rel > worst_g) worst_g = rel;
        printf("  g[%d] 数值=%+.6f 解析=%+.6f 相对误差=%.2e %s\n",
               j, num, dg[j], rel, rel < 1e-3f ? "OK" : "BAD");
    }

    printf("\n最大相对误差：du %.2e, dg %.2e\n", worst_u, worst_g);
    if (worst_u < 1e-3f && worst_g < 1e-3f) {
        printf("SwiGLU 反向推导正确 ✔\n");
        return 0;
    }
    printf("SwiGLU 反向有误 ✘\n");
    return 1;
}
