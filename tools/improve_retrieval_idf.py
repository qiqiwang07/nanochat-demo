"""改进教材检索：加入 IDF 权重，解决"静夜思""红楼梦"这类短词检索不到的问题。

原来：只要共同二元组 >= 3 才算命中。
问题：「静夜思的作者是谁」的二元组是 静夜/夜思/思的/的作/作者/者是/是谁，
      含「静夜思」的片段只能重合 2 个 → 被判为不相关。
改法：用 IDF 给二元组加权，稀有词（静夜、夜思）权重高，常见词（的作、作者）权重低，
      只要命中的是稀有词就算相关。
"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# 1) 新增 df 表（每个二元组出现在多少个片段里）
old1 = '''chunks = []  # 教材切块后的文本片段，供检索使用
chunk_grams = []  # 与 chunks 一一对应的字符二元组集合，预先算好避免每次查询重复计算'''
new1 = '''chunks = []  # 教材切块后的文本片段，供检索使用
chunk_grams = []  # 与 chunks 一一对应的字符二元组集合，预先算好避免每次查询重复计算
gram_df = {}  # 每个二元组出现在多少个片段里（文档频率），用于算 IDF 权重
gram_idf = {}  # 预先算好的逆文档频率：越罕见的词权重越高'''
assert old1 in t
t = t.replace(old1, new1, 1)

# 2) 建索引时统计 df 并预计算 idf
old2 = '''    chunk_grams = [_grams(c) for c in raw]  # 一次性算完所有片段的二元组
    chunks = raw  # 替换模块级引用'''
new2 = '''    chunk_grams = [_grams(c) for c in raw]  # 一次性算完所有片段的二元组
    chunks = raw  # 替换模块级引用
    # 统计文档频率：一个二元组出现在越多片段里，说明它越普通（如"的作""作者"），检索时应该降权
    global gram_df, gram_idf
    gram_df = {}
    for gs in chunk_grams:  # 遍历每个片段
        for g in gs:  # 逐个二元组
            gram_df[g] = gram_df.get(g, 0) + 1  # 计数
    n = max(1, len(chunks))  # 片段总数
    gram_idf = {g: __import__("math").log(1.0 + n / df) for g, df in gram_df.items()}  # IDF = ln(1 + N/df)'''
assert old2 in t
t = t.replace(old2, new2, 1)

# 3) 重写 retrieve：按 IDF 加权打分，门槛从"3 个重合"改成"至少 2 个且总分够"
old3 = '''    scored = []  # 收集 (分数, 片段下标)
    for i, dg in enumerate(chunk_grams):  # 遍历所有片段
        if not dg:  # 空片段跳过
            continue  # 下一条
        inter = len(qg & dg)  # 共同二元组数量
        if inter >= 3:  # 门槛比题库低，因为教材是泛泛背景，不必精准
            scored.append((inter / (len(dg) ** 0.5), i))  # 只做单向归一化，长片段不会过度占优
    scored.sort(reverse=True)  # 分数高的在前'''
new3 = '''    scored = []  # 收集 (分数, 片段下标)
    for i, dg in enumerate(chunk_grams):  # 遍历所有片段
        if not dg:  # 空片段跳过
            continue  # 下一条
        common = qg & dg  # 共同出现的二元组
        if len(common) < 2:  # 少于 2 个共同二元组基本是巧合，直接跳过
            continue  # 下一条
        # IDF 加权求和：命中"静夜""夜思"这类稀有词得分高，命中"作者""是什么"这类常见词得分低
        s = 0.0
        for g in common:
            s += gram_idf.get(g, 1.0)  # 没见过的词给默认权重 1
        scored.append((s / (len(dg) ** 0.25), i))  # 只做很弱的长度归一化，长片段仍可胜出
    scored.sort(reverse=True)  # 分数高的在前'''
assert old3 in t
t = t.replace(old3, new3, 1)

ast.parse(t)  # 语法检查
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('检索算法已改为 IDF 加权')
