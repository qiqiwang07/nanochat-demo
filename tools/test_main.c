#include <stdio.h>

int main(void) {
#ifdef _WIN32
    SetConsoleOutputCP(65001);
#endif
    if (load_corpus("zhchat_corpus.txt") != 0) return 1;
    BT = B * T;
    init_params();
    alloc_activations();
    if (load_weights("zhchat.bin") != 0) return 1;
    char out[8192];
    const char *qs[] = {"你好", "讲个笑话", "再见", "谢谢", "我有点难过",
                        "12+15*3", "一件衣服原价200元，打八折后需要多少钱？", "2x+3=7"};
    for (int i = 0; i < 8; i++) {
        printf("\nQ: %s\nA: ", qs[i]);
        fflush(stdout);
        answer_q(qs[i], out, sizeof out);
        printf("%s\n", out);
        fflush(stdout);
    }
    printf("\n全部完成\n");
    return 0;
}
