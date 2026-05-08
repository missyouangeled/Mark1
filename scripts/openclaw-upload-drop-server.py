#!/usr/bin/env python3
# 适用机器：公司（Linux）（脚本本身可复用）
# 系统 / OS：Linux
# 用途：在当前机器上起一个临时浏览器上传页，方便宿主机或同网段设备把文件直接传到这台机器。
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import cgi
import html
import os
import secrets
import sys

UPLOAD_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
TOKEN = sys.argv[2] if len(sys.argv) > 2 else secrets.token_hex(8)
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8771
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

HTML = f'''<!doctype html>
<html><head><meta charset="utf-8"><title>OpenClaw 临时上传</title></head>
<body style="font-family:sans-serif;max-width:720px;margin:40px auto;line-height:1.5;">
<h2>临时上传</h2>
<p>把文件拖进来或点下面按钮选择文件，然后上传。</p>
<form method="post" enctype="multipart/form-data" action="/{TOKEN}">
  <input type="file" name="file" multiple required>
  <button type="submit">上传</button>
</form>
<p style="color:#666">上传目录：{html.escape(str(UPLOAD_DIR))}</p>
</body></html>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip('/') != f'/{TOKEN}':
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
            return
        body = HTML.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.rstrip('/') != f'/{TOKEN}':
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
            return
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers.get('Content-Type', '')},
        )
        items = form['file'] if 'file' in form else []
        if not isinstance(items, list):
            items = [items]
        saved = []
        for item in items:
            if not getattr(item, 'filename', None):
                continue
            name = os.path.basename(item.filename)
            dest = UPLOAD_DIR / name
            base = dest.stem
            suf = dest.suffix
            i = 1
            while dest.exists():
                dest = UPLOAD_DIR / f"{base}-{i}{suf}"
                i += 1
            with open(dest, 'wb') as f:
                f.write(item.file.read())
            saved.append(dest.name)
        msg = '<br>'.join(html.escape(x) for x in saved) or '没有收到文件'
        body = f'''<!doctype html><html><head><meta charset="utf-8"><title>上传完成</title></head>
<body style="font-family:sans-serif;max-width:720px;margin:40px auto;line-height:1.5;">
<h2>上传完成</h2>
<p>{msg}</p>
<p><a href="/{TOKEN}">继续上传</a></p>
</body></html>'''.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)

print(f'TOKEN={TOKEN}', flush=True)
print(f'UPLOAD_DIR={UPLOAD_DIR}', flush=True)
print(f'PORT={PORT}', flush=True)
HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
