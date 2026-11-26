# -*- coding: utf-8 -*-
"""自研生成模块：不调用任何外部模型，用算法和模板补齐四项能力。

  1. 摘要        抽取式：句子打分（关键词覆盖 + 位置 + 长度），挑最关键的几句按原序拼
  2. 作文        模板式：起承转合骨架 + 从诗词/名句库检索相关引用填空
  3. 代码        片段库：按关键词匹配常见任务，做参数替换后输出
  4. 概念解释    结构化：定义句 + 要点句 + 补充句，全部取自本地语料原文

设计原则：宁可产出朴素，也不编造事实。所有句子都能追溯到语料或模板。
"""
import math
import re


# ---------------------------------------------------------------- 基础工具

def split_sentences(text):
    """把文字切成句子。中文按句末标点切，英文按 . ! ? 切。"""
    if not text:
        return []
    parts = re.split(r"(?<=[。！？；!?;])\s*|\n+", text)
    return [p.strip() for p in parts if p and len(p.strip()) >= 6]


def _terms(text):
    """粗粒度词频：中文按二字片段，英文按单词。用于给句子打分。"""
    text = text.lower()
    grams = {}
    for i in range(len(text) - 1):
        g = text[i:i + 2]
        if g.strip() and not re.match(r"^[\s\W]+$", g):
            grams[g] = grams.get(g, 0) + 1
    for w in re.findall(r"[a-z]{3,}", text):
        grams[w] = grams.get(w, 0) + 1
    return grams


# ---------------------------------------------------------------- 1. 摘要

def summarize(text, query="", max_sent=5, max_chars=600):
    """抽取式摘要：挑最能代表原文的几句话，按原顺序拼成一段。

    打分依据三条：
      · 与问题的关键词重合度（有 query 时权重最高）
      · 句子自身的信息量（词频累加，归一化）
      · 位置（越靠前越可能是主题句）
    """
    sents = split_sentences(text)
    if not sents:
        return ""
    if len(sents) <= max_sent and len(text) <= max_chars:
        return " ".join(sents)

    freq = _terms(text)
    total = sum(freq.values()) or 1
    q_terms = set(_terms(query).keys()) if query else set()

    scored = []
    for idx, s in enumerate(sents):
        st = _terms(s)
        info = sum(freq.get(g, 0) for g in st) / total      # 信息量
        info = info / (len(s) ** 0.5 + 1)                    # 长句惩罚
        rel = sum(1 for g in st if g in q_terms) / (len(q_terms) ** 0.5 + 1) if q_terms else 0
        pos = 1.0 / (1 + idx) * 0.4                          # 位置分
        scored.append((rel * 2.0 + info + pos, idx, s))

    scored.sort(key=lambda x: -x[0])
    picked = sorted(scored[:max_sent], key=lambda x: x[1])   # 选完按原文顺序排
    out, used = [], 0
    for _, _, s in picked:
        if used + len(s) > max_chars and out:
            break
        out.append(s)
        used += len(s)
    return " ".join(out)


# ---------------------------------------------------------------- 2. 作文

# 起承转合的骨架。{q} 是引用的诗句/名言，{t} 是题目。
ESSAY_TEMPLATE = """# {t}

{q1}

{t}，这个题目看上去平常，细想却并不简单。它不是一个可以一句话说完的道理，而是一种需要反复掂量的选择。

先说一个最基本的事实：{t}从来不是天赋，而是日复一日的积累。古人讲"水滴石穿"，说的就是这个意思——真正起作用的，往往不是某一刻的爆发，而是那些看不出效果的重复。

{q2}

再说一层：{t}之所以难，是因为它要求人在看不到结果的时候依然坚持。很多事情不是做不到，而是做到一半就放弃了。能把一件小事做十年的人，最后往往比聪明却三心二意的人走得远。

{q3}

当然，{t}不等于蛮干。方向错了，坚持只是加速失败。真正的坚持里包含判断：该调整的时候调整，该守住的时候守住。这份分寸感，比毅力本身更难得。

写到这里，可以回到开头那句：{t}不是一句口号，而是一种日常。它藏在每天早起的那半小时里，藏在别人休息时你还在改的那一版稿子里，藏在一次次想放弃又没放弃的瞬间里。

所以，与其问怎样才能做到{t}，不如问：今天，我能不能把手上这件事，再认真做一遍。
"""

# 引用库：按主题分组，写作文时按题目关键词挑
QUOTES = {
    "坚持": ["锲而不舍，金石可镂。——《荀子》",
             "宝剑锋从磨砺出，梅花香自苦寒来。",
             "不积跬步，无以至千里；不积小流，无以成江海。——《荀子》"],
    "勤奋": ["业精于勤，荒于嬉；行成于思，毁于随。——韩愈",
             "书山有路勤为径，学海无涯苦作舟。",
             "三更灯火五更鸡，正是男儿读书时。——颜真卿"],
    "读书": ["腹有诗书气自华。——苏轼",
             "读书破万卷，下笔如有神。——杜甫",
             "问渠那得清如许？为有源头活水来。——朱熹"],
    "时间": ["盛年不重来，一日难再晨。——陶渊明",
             "逝者如斯夫，不舍昼夜。——《论语》",
             "劝君莫惜金缕衣，劝君惜取少年时。——杜秋娘"],
    "理想": ["长风破浪会有时，直挂云帆济沧海。——李白",
             "路漫漫其修远兮，吾将上下而求索。——屈原",
             "会当凌绝顶，一览众山小。——杜甫"],
    "家国": ["先天下之忧而忧，后天下之乐而乐。——范仲淹",
             "人生自古谁无死？留取丹心照汗青。——文天祥",
             "位卑未敢忘忧国。——陆游"],
    "自然": ["采菊东篱下，悠然见南山。——陶渊明",
             "明月松间照，清泉石上流。——王维",
             "落霞与孤鹜齐飞，秋水共长天一色。——王勃"],
    "困难": ["山重水复疑无路，柳暗花明又一村。——陆游",
             "千磨万击还坚劲，任尔东西南北风。——郑燮",
             "天将降大任于是人也，必先苦其心志。——《孟子》"],
    "友情": ["海内存知己，天涯若比邻。——王勃",
             "桃花潭水深千尺，不及汪伦送我情。——李白",
             "君子之交淡如水。——《庄子》"],
}


def _pick_quotes(topic, n=3):
    """按题目关键词挑引用；没命中就挑通用的。"""
    keys = [k for k in QUOTES if k in topic]
    if not keys:                                  # 题目没命中主题词：按字的相似度挑
        keys = sorted(QUOTES.keys(),
                      key=lambda k: -sum(1 for ch in k if ch in topic))[:2]
        keys = [k for k in keys if k] or ["坚持"]
    pool = []
    for k in keys[:2]:
        pool.extend(QUOTES[k])
    if not pool:
        pool = QUOTES["坚持"]
    # 取三条，循环取以保证不重复
    return [pool[i % len(pool)] for i in range(n)]


def write_essay(topic, min_len=600):
    """按题目生成一篇议论文。题目先做清洗（去掉"写一篇关于…"这类外壳）。"""
    # 优先取主题是X/题目是X里明确给出的题目
    m = re.search(r"(主题|题目|标题)(是|为)?[：:]?\s*([^，。；]+)", topic)
    t = m.group(3).strip() if m else topic.strip()
    t = re.sub(r"^(请|帮我|麻烦)?(写|作)?(一篇|一段|个)?", "", t)   # 去掉 请/帮我/写/一篇
    t = re.sub(r"^关于", "", t)                                  # 去掉开头的 关于
    t = re.sub(r"^(以|就)", "", t)                               # 去掉 以/就
    t = re.sub(r"为题.*$", "", t)                                # 以X为题写… → X
    t = re.sub(r"(谈谈|说说)", "", t)
    t = re.sub(r"(短|长)?(的)?(议论文|记叙文|散文|作文|文章|小论文).*$", "", t)  # 去掉体裁及其后
    t = re.sub(r"(字左右|左右|\d+\s*字).*$", "", t)              # 去掉字数要求
    t = re.sub(r"[，。！？、\s]+", "", t)
    t = t.rstrip("的")
    t = t[:20] or "这件事"
    q1, q2, q3 = _pick_quotes(t, 3)
    body = ESSAY_TEMPLATE.format(t=t, q1="> " + q1, q2="> " + q2, q3="> " + q3)
    return body


# ---------------------------------------------------------------- 3. 代码

CODE_LIB = [
    (("冒泡", "bubble"), "Python", "冒泡排序", """def bubble_sort(a):
    \"\"\"冒泡排序：相邻两两比较，大的往后冒。时间 O(n^2)，空间 O(1)。\"\"\"
    n = len(a)
    for i in range(n - 1):
        swapped = False                      # 记录本轮有没有交换
        for j in range(n - 1 - i):           # 每轮把最大的送到末尾
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swapped = True
        if not swapped:                      # 已经有序，提前结束
            break
    return a


print(bubble_sort([5, 2, 9, 1, 7]))
"""),
    (("快排", "快速", "quick"), "Python", "快速排序", """def quick_sort(a):
    \"\"\"快速排序：选基准，小的放左、大的放右，再递归。平均 O(n log n)。\"\"\"
    if len(a) <= 1:
        return a
    pivot = a[len(a) // 2]
    left = [x for x in a if x < pivot]
    mid = [x for x in a if x == pivot]
    right = [x for x in a if x > pivot]
    return quick_sort(left) + mid + quick_sort(right)


print(quick_sort([5, 2, 9, 1, 7]))
"""),
    (("二分", "查找", "binary"), "Python", "二分查找", """def binary_search(a, target):
    \"\"\"二分查找：前提是数组有序。时间 O(log n)。\"\"\"
    lo, hi = 0, len(a) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if a[mid] == target:
            return mid
        if a[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


print(binary_search([1, 3, 5, 7, 9], 7))   # 3
"""),
    (("斐波那契", "fib"), "Python", "斐波那契数列", """def fib(n):
    \"\"\"斐波那契：用迭代，避免递归的指数级重复计算。时间 O(n)。\"\"\"
    if n < 2:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b


print([fib(i) for i in range(10)])
"""),
    (("最大公约", "gcd", "公约数"), "Python", "最大公约数", """def gcd(a, b):
    \"\"\"辗转相除法求最大公约数。时间 O(log min(a, b))。\"\"\"
    while b:
        a, b = b, a % b
    return a


print(gcd(48, 18))   # 6
"""),
    (("质数", "素数", "prime"), "Python", "判断质数", """def is_prime(n):
    \"\"\"判断质数：只需试到 sqrt(n)。时间 O(sqrt(n))。\"\"\"
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


print([x for x in range(2, 30) if is_prime(x)])
"""),
    (("反转", "reverse"), "Python", "字符串反转", """def reverse_str(s):
    \"\"\"反转字符串：切片最简洁，也可以用双指针原地交换。\"\"\"
    return s[::-1]


print(reverse_str("hello"))   # olleh
"""),
    (("文件", "读取", "file"), "Python", "文件读写", """def read_lines(path):
    \"\"\"按行读文件：用 with 保证句柄一定关闭。\"\"\"
    with open(path, "r", encoding="utf-8") as f:
        return [line.rstrip("\\n") for line in f]


def write_lines(path, lines):
    \"\"\"按行写文件：一次写完，避免频繁 IO。\"\"\"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\\n".join(lines))


if __name__ == "__main__":
    write_lines("demo.txt", ["第一行", "第二行"])
    print(read_lines("demo.txt"))
"""),
    (("http", "请求", "爬虫", "接口"), "Python", "HTTP 请求", """import json
import urllib.request


def get_json(url):
    \"\"\"用标准库发 GET 请求并解析 JSON，不依赖第三方包。\"\"\"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


# print(get_json("https://example.com/api"))
"""),
    (("c语言", "c 语言", "指针"), "C", "C 语言求数组最大值", """#include <stdio.h>

/* 返回数组最大值；n 是元素个数 */
int max_of(const int *a, int n) {
    int m = a[0];                     /* 假设第一个最大 */
    for (int i = 1; i < n; i++) {
        if (a[i] > m) m = a[i];       /* 遇到更大就更新 */
    }
    return m;
}

int main(void) {
    int a[] = {3, 9, 2, 7};
    printf("%d\\n", max_of(a, 4));     /* 9 */
    return 0;
}
"""),
]


def write_code(task):
    """按任务描述匹配代码库，返回 (语言, 标题, 代码)；没有匹配返回 None。"""
    low = task.lower()
    best, best_score = None, 0
    for keys, lang, title, code in CODE_LIB:
        score = sum(1 for k in keys if k in low)
        if score > best_score:
            best, best_score = (lang, title, code), score
    return best


CODE_NOTE = """
**说明**

- 代码只依赖标准库，可以直接复制运行。
- 排序/查找类算法的复杂度写在注释里，方便判断能不能用在你的数据规模上。
- 如果需要改成别的语言或加上输入校验，告诉我具体要求，我再改。
"""


# ---------------------------------------------------------------- 4. 概念解释

def explain_concept(question, chunks):
    """用本地语料拼一个结构化解释：定义句 + 要点句 + 补充句。"""
    if not chunks:
        return ""
    text = "\n".join(chunks)
    sents = split_sentences(text)
    if not sents:
        return ""

    # 校验一：问题里的实词必须真的出现在材料里
    subject = re.sub(r"(什么是|什么叫|是什么|为什么|怎么样|如何|的|吗|呢|？|\?|，|,|。)", " ", question)
    keys = [w for w in subject.split() if len(w) >= 2]
    if not keys:
        return ""
    main = max(keys, key=len)                 # 最长的实词就是问题的主体
    if main not in text:
        return ""

    # 判断是不是定义句：含"是""指""称为"这类词
    def is_def(s):
        return any(k in s for k in ("是指", "是", "指", "称为", "叫做", "定义为")) and len(s) >= 10

    defs = [s for s in sents if is_def(s)]
    if not defs:                              # 没有定义句就不算解释，交给抽取路径
        return ""
    body = summarize(text, question, max_sent=6, max_chars=500)

    lines = []
    if defs:
        lines.append("**定义**：" + defs[0])
        lines.append("")
    lines.append("**要点**：")
    for s in split_sentences(body)[:5]:
        lines.append("- " + s)
    lines.append("")
    lines.append("（以上内容取自本地资料原文，未做改写。）")
    return "\n".join(lines)


# -*- coding: utf-8 -*-
"""自研生成器 v2：从"查库"升级为"组装"。

  代码：程序合成器——把任务拆成若干操作，按顺序拼成可运行的函数
  作文：多套骨架 + 语料论据 + 引用，按题目确定性地组合（同题稳定、异题不同）

仍然不依赖任何外部模型，全部是规则 + 语料。
"""


# ============================================================ 代码合成器

# 每个操作：关键词、生成的语句、注释
OPS = [
    (("去掉重复", "重复项", "去重", "不重复", "唯一"), "result = list(dict.fromkeys(result))", "去重并保持原顺序"),
    (("偶数", "双数"), "result = [x for x in result if x % 2 == 0]", "只保留偶数"),
    (("奇数", "单数"), "result = [x for x in result if x % 2 == 1]", "只保留奇数"),
    (("平方", "平方数"), "result = [x * x for x in result]", "每个元素取平方"),
    (("升序", "从小到大", "排序", "排一下"), "result = sorted(result)", "升序排序"),
    (("降序", "从大到小", "倒序排"), "result = sorted(result, reverse=True)", "降序排序"),
    (("反转", "倒序", "反过来"), "result = result[::-1]", "反转顺序"),
    (("转大写", "大写"), "result = [x.upper() for x in result]", "转成大写"),
    (("转小写", "小写"), "result = [x.lower() for x in result]", "转成小写"),
    (("求和", "总和", "加起来", "累加"), "result = sum(result)", "求和"),
    (("平均", "均值"), "result = sum(result) / len(result)", "求平均值"),
    (("最大值", "最大", "最高"), "result = max(result)", "取最大值"),
    (("最小值", "最小", "最低"), "result = min(result)", "取最小值"),
    (("元素个数", "数量", "长度"), "result = len(result)", "统计个数"),
    (("出现次数", "计数", "统计次数"), "result = {v: result.count(v) for v in dict.fromkeys(result)}", "统计每个元素出现次数"),
]


def write_program(task):
    """把任务描述拆成操作序列，合成一个可运行的 Python 函数。

    返回 (标题, 代码) 或 None。
    例："写一个函数，去掉列表里的重复项，只留偶数，再从小到大排序"
        → 去重 + 过滤偶数 + 升序，三句按序拼接
    """
    low = task.lower()
    hits = []
    claimed = []                                   # 已被更长关键词占用的位置区间
    # 长关键词先匹配，避免"每个数"里的"个数"被当成统计个数
    for keys, stmt, note in OPS:
        cand = [(low.find(k), -len(k), k) for k in keys if k in low]
        if not cand:
            continue
        pos, _neglen, k = min(cand)
        if any(s <= pos < e for s, e in claimed):
            continue
        claimed.append((pos, pos + len(k)))
        hits.append((pos, stmt, note))
    if not hits:
        return None

    hits.sort(key=lambda x: x[0])          # 按任务里提到的先后顺序执行
    # 去重（同一语句可能被多个关键词命中）
    seen, steps = set(), []
    for _, stmt, note in hits:
        if stmt not in seen:
            seen.add(stmt)
            steps.append((stmt, note))

    # 判断结果是不是标量（求和/求最大值之后就不能再过滤了）
    scalar_after = ("sum(", "max(", "min(", "len(", "/ len(")
    lines = ["def solve(items):",
             '    """%s"""' % task.replace('"""', "'''"),
             "    result = list(items)                  # 复制一份，不改动调用方的数据"]
    for i, (stmt, note) in enumerate(steps):
        lines.append("    %s" % stmt.ljust(52) + "# " + note)
        if any(k in stmt for k in scalar_after):
            # 变成标量之后，后面的集合类操作就没意义了，截断
            if i + 1 < len(steps):
                lines.append("    # 到这里 result 已经是单个值，后面不再做集合操作")
            break

    lines += ["    return result", "", "",
              'if __name__ == "__main__":',
              "    data = [3, 1, 2, 3, 4, 2, 5]",
              "    print(solve(data))"]

    title = "、".join(n for _, n in steps)
    return title, "\n".join(lines)


PROGRAM_NOTE = """
**说明**

- 上面这段是按你描述的操作顺序**现场合成**的，不是从模板库里抄的。
- 每一步都写了它干什么；如果顺序不对（比如先去重再过滤），告诉我，我调整。
- 数据是示例，把 `data` 换成你的输入即可。
"""


# ============================================================ 作文合成器

# 三套开头 × 三套中段 × 三套结尾，按题目哈希选一套，保证同题稳定、异题不同
OPENINGS = [
    """{q1}

{t}，这个题目看上去平常，细想却并不简单。它不是一个可以一句话说完的道理，而是一种需要反复掂量的选择。""",
    """{q1}

谈到{t}，很多人第一反应是"这有什么难的"。可真要把它落到每天的生活里，才发现难的不是理解，而是做到。""",
    """{q1}

{t}这两个字，说起来轻巧。它既不是天赋，也不是运气，而是一种需要在漫长的时间里反复确认的态度。""",
]

MIDDLES = [
    """先说一个最基本的事实：{t}从来不是天赋，而是日复一日的积累。古人讲"水滴石穿"，说的就是这个意思——真正起作用的，往往不是某一刻的爆发，而是那些看不出效果的重复。

{q2}

再说一层：{t}之所以难，是因为它要求人在看不到结果的时候依然坚持。很多事情不是做不到，而是做到一半就放弃了。能把一件小事做十年的人，最后往往比聪明却三心二意的人走得远。""",
    """{t}的第一层含义，是"重复"。任何一件值得做的事，拆开来看都是大量枯燥的重复：练琴是重复，写作是重复，做题也是重复。区别只在于，有人在重复里看见进步，有人在重复里失去了耐心。

{q2}

第二层含义，是"选择"。{t}意味着在无数个可以放松的时刻选择继续，在别人放弃的时候选择留下。这种选择做一次不难，做一百次就拉开了人和人之间的距离。""",
    """要想说清{t}，不妨先看它反面的样子：三分钟热度、半途而废、开头热闹结尾冷清。这些我们都见过，甚至都经历过。{t}之所以可贵，正因为它稀少。

{q2}

而从另一个角度看，{t}并不神秘。它只是一种把"想做"变成"在做"的能力——不靠情绪驱动，靠的是把大目标切成今天能完成的一小块。""",
]

ENDINGS = [
    """当然，{t}不等于蛮干。方向错了，坚持只是加速失败。真正的坚持里包含判断：该调整的时候调整，该守住的时候守住。这份分寸感，比毅力本身更难得。

写到这里，可以回到开头那句：{t}不是一句口号，而是一种日常。它藏在每天早起的那半小时里，藏在别人休息时你还在改的那一版稿子里，藏在一次次想放弃又没放弃的瞬间里。

所以，与其问怎样才能做到{t}，不如问：今天，我能不能把手上这件事，再认真做一遍。""",
    """需要说明的是，{t}并不意味着一条路走到黑。会坚持的人，往往也最懂得什么时候该转向。他们守的是目标，变的是方法。

{q3}

说到底，{t}是一种把时间当作朋友的能力。它不喧哗，也不立刻兑现，但时间会把答案给出来。""",
    """{q3}

最后想说，{t}这件事，评价它的标准从来不在别人的眼光里，而在你自己心里那杆秤上：今天做的事，对不对得起今天的时间。

愿我们都能在漫长而安静的重复里，等到那个水到渠成的时刻。""",
]


# -*- coding: utf-8 -*-
"""多骨架作文：同题稳定、异题不同（追加到 selfgen.py 末尾）。"""


def clean_topic(topic):
    """把"写一篇关于X的短议论文"这类外壳剥掉，只留 X。"""
    t = topic.strip()
    t = re.sub(r"^(请|帮我|麻烦)?(写|作)?(一篇|一段|个)?", "", t)
    t = re.sub(r"^关于", "", t)
    t = re.sub(r"^(以|就)", "", t)
    t = re.sub(r"为题.*$", "", t)
    t = re.sub(r"(谈谈|说说)", "", t)
    t = re.sub(r"(短|长)?(的)?(议论文|记叙文|散文|作文|文章|小论文).*$", "", t)
    t = re.sub(r"(字左右|左右|\d+\s*字).*$", "", t)
    t = re.sub(r"[，。！？、\s]+", "", t)
    return t.rstrip("的") or "这件事"


def write_essay2(topic, evidence=None):
    """按题目哈希挑开头/中段/结尾，保证同题稳定、不同题目结构不同。

    evidence：可传入本地语料里找到的相关句子，作为论据插入。
    """
    m = re.search(r"(主题|题目|标题)(是|为)?[：:]?\s*([^，。；]+)", topic)
    t = m.group(3).strip() if m else topic
    t = clean_topic(t)

    q1, q2, q3 = _pick_quotes(t, 3)
    h = sum(ord(c) for c in t)                        # 题目字码和作种子
    opening = OPENINGS[h % len(OPENINGS)].format(t=t, q1="> " + q1)
    middle = MIDDLES[(h // 3) % len(MIDDLES)].format(t=t, q2="> " + q2)
    ending = ENDINGS[(h // 7) % len(ENDINGS)].format(t=t, q3="> " + q3)

    parts = ["# " + t, "", opening, "", middle]
    if evidence:
        parts += ["", "材料里还有这样一句可以佐证：" + evidence, ""]
    parts += ["", ending]
    return "\n".join(parts)
