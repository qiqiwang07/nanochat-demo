"""让服务端识别"写作文"意图：注入写作素材，并要求写完整长文。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# 1) 在检索之后插入"作文意图"判定
old1 = '''            math_hits = retrieve_olympiad(text, 1)  # 先判断是不是数学题，数学题才检索题库
            hits = retrieve(text, 1)  # 只取 1 段：片段越多预填充越慢，首字延迟越高'''
new1 = '''            # 判断是不是写作任务：作文要的是成篇的文字，和"问知识点"完全不同，需要单独处理
            essay_kw = ("作文", "议论文", "记叙文", "说明文", "散文", "写一篇", "写段", "写一封",
                        "帮我写", "演讲稿", "读后感", "观后感")
            is_essay = any(k in text for k in essay_kw)  # 命中任一关键词即视为写作任务
            math_hits = retrieve_olympiad(text, 1)  # 先判断是不是数学题，数学题才检索题库
            hits = retrieve(text, 1)  # 只取 1 段：片段越多预填充越慢，首字延迟越高
            style_hits = retrieve("好词好句 优美句子 名言警句 开头 结尾 排比 描写", 1) if is_essay else []  # 写作任务额外取一段素材'''
assert old1 in t
t = t.replace(old1, new1, 1)

# 2) 把写作分支插到数学分支之前（写作优先，避免"写一篇关于数学的作文"被当成解题）
old2 = '''            if math_hits:  # 是数学题：注入相似题与标准解答'''
new2 = '''            if is_essay:  # 写作任务：要求成篇、有结构、有文采
                ref = ("\\n\\n【可参考的好词好句】\\n" + style_hits[0][:300]) if style_hits else ""  # 素材截短，控制预填充
                msgs = s["messages"][:-1] + [{
                    "role": "user",
                    "content": ("请写一篇完整的作文。\\n"
                                "要求：\\n"
                                "1. 结构完整：开头点题，中间分 3-4 段展开，结尾升华；\\n"
                                "2. 内容具体：多用具体事例、细节描写，不要空喊口号；\\n"
                                "3. 语言有文采：适当使用成语、排比、比喻，可引用诗词或名言；\\n"
                                "4. 篇幅 700-900 字；\\n"
                                "5. 直接给正文，不要解释你的写作思路。\\n\\n"
                                "题目：" + text + ref)}]
                req_max = 2200  # 800 字中文大约要 700-900 token，留足余量防止被截断
            elif math_hits:  # 是数学题：注入相似题与标准解答'''
assert old2 in t
t = t.replace(old2, new2, 1)

# 3) 原来 req_max 是三元表达式，写作分支已经自己赋值，这里改成 else 分支
old3 = '''            req_max = max(MAX_NEW, 3000) if math_hits else MAX_NEW  # 数学题解答长，给更大额度'''
new3 = '''            if not is_essay:  # 写作分支已自行设过额度，其余按题目类型给
                req_max = max(MAX_NEW, 3000) if math_hits else MAX_NEW  # 数学题解答长，给更大额度'''
assert old3 in t
t = t.replace(old3, new3, 1)

# 4) 引用数统计加上写作素材
old4 = '''            ref_count = len(math_hits) + (0 if math_hits else len(hits))  # 统计参考了多少条，前端可展示'''
new4 = '''            ref_count = len(math_hits) + (0 if math_hits else len(hits)) + len(style_hits)  # 统计参考了多少条，前端可展示'''
assert old4 in t
t = t.replace(old4, new4, 1)

ast.parse(t)  # 语法检查
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已加入写作意图识别')
