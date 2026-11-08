"""修复 stream_llama：Qwen 不是思考模型，不需要等待思考标记。"""
import ast
import os

INST = os.path.join(os.environ['USERPROFILE'], 'AI助手')
TOOLS = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'

OLD = '''            if not started:
                pre += delta
                for mk in ("</think>", "<｜end▁of▁thinking｜>"):
                    if mk in pre:
                        pre = pre.split(mk, 1)[1]
                        started = True
                        break
                if not started and len(pre) > 200:
                    started = True
                if started:
                    pre = pre.lstrip("\\n")
                    if pre:
                        yield pre
                    pre = ""
            else:
                yield delta'''

NEW = '''            if not started:
                pre += delta
                # 只有 DeepSeek-R1 这类推理模型才需要剥掉思考过程；Qwen 直接输出
                if "\\uff5cend\\u2581of\\u2581thinking\\uff5c" in pre or "</think>" in pre:
                    for mk in ("</think>", "\\uff5cend\\u2581of\\u2581thinking\\uff5c"):
                        if mk in pre:
                            pre = pre.split(mk, 1)[1]
                            break
                pre = pre.lstrip("\\n")
                if pre:
                    started = True
                    yield pre
                    pre = ""
            else:
                yield delta'''


def patch(path, label):
    s = open(path, encoding='utf-8').read()
    if 'Qwen 直接输出' in s:
        print('  %s: 已是新版' % label)
        return
    if OLD in s:
        s = s.replace(OLD, NEW, 1)
        ast.parse(s)
        open(path, 'w', encoding='utf-8').write(s)
        print('  %s: 已修复' % label)
    else:
        print('  %s: 未匹配，检查原文' % label)


patch(TOOLS, 'tools')
patch(os.path.join(INST, 'serve_r1.py'), '安装目录')
