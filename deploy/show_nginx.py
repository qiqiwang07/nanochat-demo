import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('1.117.113.68', 22, 'qiqiwang', 'wzw0702', timeout=25)


def run(cmd, t=40):
    i, o, e = c.exec_command(cmd, timeout=t)
    return (o.read().decode('utf-8', 'ignore') + e.read().decode('utf-8', 'ignore')).strip()


print('=== sites-enabled 目录 ===')
print(run('ls -la /etc/nginx/sites-enabled/ 2>&1'))
for name in ('c_learning', 'accounting', 'finai', 'pms', 'clickhouse'):
    print('=== %s ===' % name)
    print(run('cat /etc/nginx/sites-enabled/%s 2>&1 | head -40' % name))
c.close()
