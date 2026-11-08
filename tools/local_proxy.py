"""本机代理：把 127.0.0.1:8095 的请求转发到云端服务器（绕过域名解析问题）。

算力仍然是服务器在出，这个进程只做转发。
"""
import argparse
import http.client
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM_HOST = '1.117.113.68'
UPSTREAM_PORT = 80
UPSTREAM_HOST_HEADER = 'c-learning.oprfin.com'


class Proxy(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass

    def _proxy(self, method):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else None

        # 转发连接
        conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=1800)
        headers = {}
        for k, v in self.headers.items():
            if k.lower() in ('host', 'connection', 'content-length'):
                continue
            headers[k] = v
        headers['Host'] = UPSTREAM_HOST_HEADER

        conn.request(method, self.path, body=body, headers=headers)
        resp = conn.getresponse()

        # 流式回传
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in ('transfer-encoding', 'connection', 'content-length'):
                continue
            self.send_header(k, v)
        self.send_header('Connection', 'close')
        self.end_headers()
        try:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception:
            pass
        finally:
            conn.close()
            self.close_connection = True

    def do_GET(self):
        self._proxy('GET')

    def do_POST(self):
        self._proxy('POST')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8095)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(('127.0.0.1', args.port), Proxy)
    print('本机代理已启动: http://127.0.0.1:%d  →  服务器 %s/%s' % (
        args.port, UPSTREAM_HOST, UPSTREAM_HOST_HEADER), flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
