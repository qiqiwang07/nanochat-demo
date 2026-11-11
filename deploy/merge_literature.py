# -*- coding: utf-8 -*-
"""
把文学语料与文学常识合并进现有知识库。

步骤：
1. 备份原 corpus.txt
2. corpus.txt = 原数学语料 + 文学常识 + 诗文语料
3. 打印最终大小
可重复执行（每次从备份重建，不会重复叠加）。
"""
import io
import os

APP = '/home/qiqiwang/airelay/app'
CORPUS = os.path.join(APP, 'corpus.txt')
BACKUP = os.path.join(APP, 'corpus_math_backup.txt')
LIT_TEXT = os.path.join(APP, 'literature.txt')
LIT_KNOW = os.path.join(APP, 'literature_knowledge.txt')


def read(path):
    """读文本，不存在返回空串。"""
    if not os.path.exists(path):
        print('  缺失: %s' % path)
        return ''
    return io.open(path, encoding='utf-8', errors='ignore').read()


def main():
    """重建知识库。"""
    # 第一次运行时先把数学语料备份出来，之后都从备份重建
    if not os.path.exists(BACKUP):
        if not os.path.exists(CORPUS):
            raise SystemExit('找不到原始语料: ' + CORPUS)
        data = read(CORPUS)
        io.open(BACKUP, 'w', encoding='utf-8').write(data)
        print('已备份数学语料 %.1f MB' % (len(data) / 1e6))
    else:
        print('数学语料备份已存在，直接复用')

    math = read(BACKUP)
    know = read(LIT_KNOW)
    lit = read(LIT_TEXT)
    print('数学语料 %.2f MB，文学常识 %.1f KB，诗文语料 %.1f KB'
          % (len(math) / 1e6, len(know) / 1024, len(lit) / 1024))

    # 用分隔标题拼接，便于检索时区分来源
    merged = (math + '\n\n' + ('=' * 40) + ' 中国文学常识 ' + ('=' * 40) + '\n\n'
              + know + '\n\n' + ('=' * 40) + ' 中国古典诗文 ' + ('=' * 40) + '\n\n' + lit)

    io.open(CORPUS, 'w', encoding='utf-8').write(merged)
    print('新语料 %.2f MB (%.1f 万字符)' % (len(merged) / 1e6, len(merged) / 1e4))


if __name__ == '__main__':
    main()
