#!/bin/bash
# embed-sidecar-wrapper.sh — systemd 兼容的 embed-sidecar 启动脚本
# Python 3.11 + systemd 组合有 selectors fd 问题，此 wrapper 直接启后台进程并写 PID

exec ~/.local/share/openclaw-embed-venv311/bin/python3 \
  /home/missyouangeled/.openclaw/workspace/scripts/embed-sidecar.py \
  --host 127.0.0.1 --port 18792
