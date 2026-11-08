import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('1.117.113.68', 22, 'qiqiwang', 'wzw0702', timeout=25)


def run(cmd, t=40):
    i, o, e = c.exec_command(cmd, timeout=t)
    return (o.read().decode('utf-8', 'ignore') + e.read().decode('utf-8', 'ignore')).strip()


print('=== 80/443 监听 ===')
print(run("ss -lnt | grep -E ':(80|443) ' || echo none"))
print('=== nginx/apache 进程 ===')
print(run("ps aux | grep -E 'nginx|apache|httpd' | grep -v grep | head -5 || echo none"))
print('=== sudo ===')
print(run("sudo -n true 2>&1 && echo SUDO_OK || echo NO_SUDO"))
print('=== nginx 配置目录 ===')
print(run("ls /etc/nginx/sites-enabled/ 2>/dev/null || ls /etc/nginx/conf.d/ 2>/dev/null || echo no_nginx"))
print('=== 用户目录 ===')
print(run("whoami; echo HOME=$HOME"))
c.close()
