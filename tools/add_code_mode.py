# -*- coding: utf-8 -*-
"""加入"写代码"模式：识别编程意图，要求输出完整可运行代码，并注入编程素材。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# 1) 增加编程意图判定（放在写作判定之后）
old1 = '''            is_essay = any(k in text for k in essay_kw)  # 命中任一关键词即视为写作任务'''
new1 = '''            is_essay = any(k in text for k in essay_kw)  # 命中任一关键词即视为写作任务
            # 判断是不是编程任务：既要提到代码相关词，又要带动作，避免"什么是算法"这类纯概念问题被误判
            code_topic = ("代码", "函数", "程序", "算法", "脚本", "python", "Python", "c语言", "C语言",
                          "javascript", "JavaScript", "java", "sql", "SQL", "html", "排序", "递归",
                          "指针", "链表", "二叉树", "编译", "数组", "字典", "class", "def")
            code_action = ("写", "实现", "编", "生成", "改", "修", "优化", "调试", "报错", "错误", "不会")
            is_code = (any(k in text for k in code_topic) and any(k in text for k in code_action)) \\
                      or any(k in text for k in ("为什么报错", "报错了", "运行不了", "跑不起来", "语法错误"))'''
assert old1 in t, '未找到 essay 判定'
t = t.replace(old1, new1, 1)

# 2) 在写作分支之后、数学分支之前插入编程分支
old2 = '''            elif math_hits:  # 是数学题：注入相似题与标准解答'''
new2 = '''            elif is_code:  # 编程任务：要求完整可运行代码 + 简要说明
                ref = ""
                if hits:  # 有编程素材就带上，截短控制预填充
                    ref = "\\n\\n【可参考的知识点】\\n" + hits[0][:300]
                msgs = s["messages"][:-1] + [{
                    "role": "user",
                    "content": ("请完成下面的编程任务。\\n"
                                "要求：\\n"
                                "1. 给出**完整可运行**的代码，包含必要的 import 和入口；\\n"
                                "2. 用 ```语言 代码块包裹；\\n"
                                "3. 关键行写中文注释说明为什么这么做；\\n"
                                "4. 代码之后用几句话说明思路、复杂度、以及需要注意的边界情况；\\n"
                                "5. 如果用户是在问报错，先说明错误原因，再给修正后的完整代码。\\n\\n"
                                "任务：" + text + ref)}]
                req_max = 1800  # 代码通常比文字长，给足额度
            elif math_hits:  # 是数学题：注入相似题与标准解答'''
assert old2 in t, '未找到 math 分支'
t = t.replace(old2, new2, 1)

# 3) req_max 的条件要排除 is_code
old3 = '''            if not is_essay:  # 写作分支已自行设过额度，其余按题目类型给'''
new3 = '''            if not is_essay and not is_code:  # 写作与编程分支已自行设过额度，其余按题目类型给'''
assert old3 in t, '未找到 req_max 判定'
t = t.replace(old3, new3, 1)

ast.parse(t)  # 语法检查
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已加入编程模式')
