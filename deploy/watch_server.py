"""持续监听云端中转服务日志（断线自动重连）。"""
import time

import paramiko

HOST, USER, PWD = '1.117.113.68', 'qiqiwang', 'wzw0702'
LOG = '/home/qiqiwang/airelay/server.log'
DURATION = 3600

nline = None
poll_count = 0
t0 = time.time()


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PWD, timeout=20, banner_timeout=20, auth_timeout=20)
    return c


def run(c, cmd, t=30):
    i, o, e = c.exec_command(cmd, timeout=t)
    return (o.read().decode('utf-8', 'ignore') + e.read().decode('utf-8', 'ignore')).strip()


c = None
while time.time() - t0 < DURATION:
    try:
        if c is None:
            c = connect()
            if nline is None:
                nline = int(run(c, 'wc -l %s' % LOG).split()[0])
                print('监听开始，已有日志 %d 行' % nline, flush=True)
            else:
                print('已重新连接', flush=True)
        chunk = run(c, 'tail -n +%d %s' % (nline + 1, LOG))
        if chunk:
            lines = [l for l in chunk.split('\n') if l.strip()]
            nline += len(lines)
            for ln in lines:
                ts = ln[1:9] if ln.startswith('[') else ''
                if '/dl/' in ln:
                    print('[%s] 下载  %s' % (ts, ln[:90]), flush=True)
                elif '/chat' in ln:
                    print('[%s] ★ 有人提问  %s' % (ts, ln[:90]), flush=True)
                elif '/worker/poll' in ln:
                    poll_count += 1
                    if poll_count % 40 == 1:
                        print('[%s] worker 在线等待任务（累计 %d 次）' % (ts, poll_count), flush=True)
                elif '/worker/chunk' in ln or '/worker/done' in ln:
                    print('[%s] ↑ 回答回传  %s' % (ts, ln[:80]), flush=True)
                elif '/health' in ln or 'GET / ' in ln:
                    print('[%s] %s' % (ts, ln[:90]), flush=True)
        time.sleep(12)
    except Exception as ex:
        print('连接中断（%s），5 秒后重连' % str(ex)[:60], flush=True)
        try:
            if c:
                c.close()
        except Exception:
            pass
        c = None
        time.sleep(5)

print('监听结束', flush=True)
