# -*- coding: utf-8 -*-
"""把"分区标题"里的实质内容提取出来（如 ---- 矩阵乘法（累加语义） ---- → 矩阵乘法（累加语义））。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\gen_call_graph.py'
t = io.open(P, encoding='utf-8').read()

# 1) first_sentence 里先去掉装饰用的横线
OLD = '''    text = text.strip()
    text = re.sub(r'^[\\s\\*#/]+', '', text)          # 去掉注释符号'''
NEW = '''    text = text.strip()
    text = re.sub(r'^[\\s\\*#/]+', '', text)          # 去掉注释符号
    text = re.sub(r'[-=*_]{4,}', ' ', text)          # 去掉装饰性横线，只留标题文字'''
assert OLD in t, '未匹配 first_sentence'
t = t.replace(OLD, NEW, 1)

# 2) 不再整段丢弃分区标题，交给上面的清洗处理
OLD2 = '''        if doc and (set(doc) <= set('-= ') or doc.startswith('---')):
            doc = ''      # 纯横线的分区标题，不算说明'''
NEW2 = '''        # 清洗后只剩空白的（纯横线）才丢弃，有文字的保留（如"矩阵乘法（累加语义）"）
        if doc and not doc.strip(' -=*'):
            doc = \'\''''
assert OLD2 in t, '未匹配过滤段'
t = t.replace(OLD2, NEW2, 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已改进分区标题提取')
