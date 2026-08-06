#!/usr/bin/env python3
"""Unity 截图回传接收端。

适用机器：公司（Linux VM）
建立日期：2026-08-06

── 为什么需要这个 ──
Unity Editor 跑在 Windows 宿主机，截图存到
  C:/Users/<用户>/AppData/LocalLow/<公司>/<产品>/
而 AI 跑在 Linux VM，两者之间**没有共享挂载**（实测 /mnt/hgfs 不存在）。
所以 debug.screenshot 拍完，AI 只能拿到一个自己打不开的 Windows 路径。

── 解法 ──
VM 起本服务监听 28080，Unity 侧用 code execute 跑 C#：
    var wc = new System.Net.WebClient();
    wc.Headers.Add("X-Name", "shot.png");
    wc.UploadData("http://192.168.79.128:28080/", bytes);
实测 2.6MB / 2005x1102 一次传成。

── 用法 ──
    python3 scripts/unity-shot-receiver.py            # 前台
    nohup python3 scripts/unity-shot-receiver.py &    # 后台
    python3 scripts/unity-shot-receiver.py --port 28081 --dir /tmp/x

⚠️ 落盘目录默认直接放 workspace/media/unity/，因为 `image` 工具
   **只能读 workspace 下的路径**，放 /tmp 会被拒：
   "Local media path is not under an allowed directory"

⚠️ 仅监听内网 NAT 子网，无鉴权。不要暴露到公网。
"""
import argparse
import os
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_DIR = os.path.expanduser("~/.openclaw/workspace/media/unity")
DEFAULT_PORT = 28080
MAX_BYTES = 64 * 1024 * 1024  # 64MB 上限，防跑飞

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def safe_name(raw: str) -> str:
    """只保留基名并过滤危险字符，防目录穿越。"""
    base = os.path.basename((raw or "").replace("\\", "/"))
    base = _SAFE.sub("_", base).lstrip(".")
    if not base:
        base = "shot_%d.png" % int(time.time())
    return base[:120]


def make_handler(out_dir: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "UnityShotReceiver/1.0"

        def do_GET(self):  # noqa: N802 - 健康检查，便于确认服务活着
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"unity-shot-receiver ok\n")

        def do_POST(self):  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0:
                self.send_error(400, "missing Content-Length")
                return
            if length > MAX_BYTES:
                self.send_error(413, "payload too large")
                return

            data = self.rfile.read(length)
            name = safe_name(self.headers.get("X-Name", ""))
            path = os.path.join(out_dir, name)
            with open(path, "wb") as fh:
                fh.write(data)

            print("[%s] SAVED %s (%d bytes)" % (
                time.strftime("%H:%M:%S"), path, len(data)), flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(("saved %s\n" % path).encode())

        def log_message(self, *args):  # 静音默认访问日志，只留 SAVED 行
            pass

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description="Unity 截图回传接收端")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--dir", default=DEFAULT_DIR)
    ap.add_argument("--host", default="0.0.0.0",
                    help="必须绑 0.0.0.0，否则 Windows 侧 Unity 连不进来")
    args = ap.parse_args()

    os.makedirs(args.dir, exist_ok=True)
    httpd = HTTPServer((args.host, args.port), make_handler(args.dir))
    print("Unity 截图接收端启动 http://%s:%d  ->  %s"
          % (args.host, args.port, args.dir), flush=True)
    print("Unity 侧上传地址：http://192.168.79.128:%d/" % args.port, flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n收到中断，退出。", flush=True)
        httpd.server_close()


if __name__ == "__main__":
    main()
