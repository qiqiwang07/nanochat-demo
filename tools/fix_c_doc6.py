# -*- coding: utf-8 -*-
"""允许注释和函数之间夹着 #define / #ifdef 这类预处理行（常见的分区注释写法）。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\gen_call_graph.py'
t = io.open(P, encoding='utf-8').read()

OLD = '''    i = pos - 1
    while i >= 0 and src[i] in ' \\t\\r\\n':      # 跳过空白
        i -= 1
    if i < 1 or src[i - 1:i + 1] != '*/':       # 前面不是注释结尾
        return ''
    j = src.rfind('/*', 0, i)                    # 找对应的注释开头
    if j < 0:
        return ''
    # 只认"独占一行"的注释；同一行前面还有代码的，是给上一句代码写的行尾注释
    line_start = src.rfind('\\n', 0, j) + 1
    if src[line_start:j].strip():
        return ''
    return src[j + 2:i - 1]                      # 去掉 /* 与 */'''

NEW = '''    # 从函数定义往前找最近的一段注释，允许中间隔着空白与预处理指令
    # （很多 C 文件写成：分区注释 → #define → 函数）
    j = src.rfind('/*', 0, max(0, pos - 4000))   # 先定位到更早的搜索起点
    j = src.rfind('/*', 0, pos - 1)              # 最近一个注释开头
    while j >= 0:                                # 逐个往前试
        end = src.find('*/', j + 2)              # 该注释的结尾
        if end < 0:                              # 注释没闭合，放弃
            return ''
        between = src[end + 2:pos]               # 注释与函数之间的内容
        # 只允许空白、空注释、预处理指令；一旦出现真正的代码就说明这段注释不是给本函数的
        ok = True
        for line in between.split('\\n'):
            s = line.strip()
            if not s:                            # 空行
                continue
            if s.startswith('#') or s.startswith('//'):   # 预处理指令或行注释
                continue
            ok = False                            # 出现代码
            break
        if ok:
            body = src[j + 2:end]                # 去掉 /* 与 */
            line_start = src.rfind('\\n', 0, j) + 1
            if not src[line_start:j].strip():    # 注释必须独占行首，排除行尾注释
                return body
            return ''                            # 行尾注释不算函数说明
        j = src.rfind('/*', 0, j)                # 再往前找
    return \'\''''

assert OLD in t, '未匹配 prev_comment 主体'
t = t.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已放宽注释匹配')
