#!/bin/bash
# 阶段 2.5 纯观察脚本——不动业务代码、不改配置、不重启服务
# 只收集当前 WebChat 渲染层状态的证据
# 运行：bash /home/missyouangeled/.openclaw/workspace/docs/runtime-checks/2026-07-07-webchat-render/probe-render.sh

OUT=/home/missyouangeled/.openclaw/workspace/docs/runtime-checks/2026-07-07-webchat-render/13-phase2-status.txt
mkdir -p "$(dirname "$OUT")"

{
  echo "===== 阶段 2.5 状态采样  $(date '+%Y-%m-%d %H:%M:%S %Z') ====="
  echo

  echo "## A. 后端健康（不改任何东西）"
  echo "### A.1 Gateway 是否在跑"
  systemctl --user is-active openclaw-gateway.service 2>&1 | sed 's/^/  /'
  ps -p 12393 -o pid,etime,cmd 2>&1 | head -3 | sed 's/^/  /'
  echo
  echo "### A.2 最近 30 条 Gateway 日志（只看事件，不重启）"
  /home/missyouangeled/.npm-global/bin/openclaw logs --limit 30 --no-color 2>&1 | tail -30 | sed 's/^/  /'
  echo
  echo "### A.3 Dashboard 可达性（不改）"
  curl -s -o /dev/null -w "  http_code=%{http_code} time=%{time_total}s\n" http://127.0.0.1:18789/ 2>&1
  echo

  echo "## B. 渲染层静态资源快照（只读）"
  echo "### B.1 Control UI 关键 bundle 文件 mtime（看是否最近被动过）"
  find /home/missyouangeled/.npm-global/lib/node_modules/openclaw/dist -name 'client-*.js' -printf '  %TY-%Tm-%Td %TH:%TM  %p\n' 2>&1 | head -3
  find /home/missyouangeled/.npm-global/lib/node_modules/openclaw/dist -name 'index.html' -printf '  %TY-%Tm-%Td %TH:%TM  %p\n' 2>&1 | head -3
  echo

  echo "## C. 当前文件落盘清单（验证我们的文件都在）"
  ls -la /home/missyouangeled/.openclaw/workspace/docs/runtime-checks/2026-07-07-webchat-render/ 2>&1 | sed 's/^/  /'
  echo

  echo "## D. OpenClaw 安装版本（确认是否跟 16:18 一致）"
  /home/missyouangeled/.npm-global/bin/openclaw --version 2>&1 | sed 's/^/  /'
  echo

  echo "===== 采样完成 ====="
} > "$OUT" 2>&1

echo "WROTE: $OUT ($(wc -c < "$OUT") bytes)"
echo "请在 TTY 跑： cat $OUT"