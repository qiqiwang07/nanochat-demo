"""把写作语料合并进知识库（幂等：每次从数学语料备份重建）。"""
import io
import os

APP = '/home/qiqiwang/airelay/app'
CORPUS = os.path.join(APP, 'corpus.txt')
BACKUP = os.path.join(APP, 'corpus_math_backup.txt')
PARTS = [
    ('literature_knowledge.txt', '中国文学常识'),
    ('literature.txt', '中国古典诗文'),
    ('writing_corpus.txt', '作文方法与好词好句'),
    ('coding_corpus.txt', '编程知识与代码示例'),
    ('coding_deep_c_py.txt', 'C 与 Python 深度手册'),
]


def read(path):
    """读文本，不存在返回空串。"""
    if not os.path.exists(path):
        print('  缺失: %s' % path)
        return ''
    return io.open(path, encoding='utf-8', errors='ignore').read()


def main():
    """重建知识库：数学 + 文学常识 + 诗文 + 写作素材。"""
    if not os.path.exists(BACKUP):
        data = read(CORPUS)
        io.open(BACKUP, 'w', encoding='utf-8').write(data)
        print('已备份数学语料')

    math = read(BACKUP)
    merged = math
    for fn, title in PARTS:
        body = read(os.path.join(APP, fn))
        if not body:
            continue
        merged += '\n\n' + ('=' * 40) + ' ' + title + ' ' + ('=' * 40) + '\n\n' + body
        print('  + %s %.1f KB' % (title, len(body.encode('utf-8')) / 1024))

    io.open(CORPUS, 'w', encoding='utf-8').write(merged)
    print('新语料 %.2f MB (%.1f 万字符)' % (len(merged.encode('utf-8')) / 1e6, len(merged) / 1e4))


if __name__ == '__main__':
    main()
