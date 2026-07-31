#!/bin/bash
# mark42-bash-logger.sh — 【可插拔】交互 shell 命令记录器
# 
# 触发：~/.bashrc source
# 行为：把当前交互 shell 命令追加到日志文件
# 启用：export MARK42_BASH_LOG=1（在 ~/.bashrc 或 PROMPT_COMMAND 里）
# 关闭：export MARK42_BASH_LOG=0（默认）
# 卸载：删除 ~/.bashrc 里 source 这一行
#
# 【2026-07-31 设计原则】
# - 完全独立：不依赖 mark42、openclaw、任何 python 模块
# - 0 性能开销：只在 PROMPT_COMMAND 触发时写一次（每条命令一次）
# - 失败静默：2>/dev/null 吞错
# - 可清理：log 按日切分，30 天后自动清理（logrotate 或 find -mtime）

# 检查是否启用（默认关闭，防止误用）
[[ "${MARK42_BASH_LOG:-0}" != "1" ]] && return 0

# 防递归：如果正在写 log，不要再触发 PROMPT_COMMAND
[[ "${MARK42_BASH_LOGGING:-0}" == "1" ]] && return 0
export MARK42_BASH_LOGGING=1

# 日志路径
_log_dir="$HOME/.openclaw/workspace/logs"
_log_file="$_log_dir/bash-commands-$(date +%F).log"

# 确保目录存在（首次）
[[ -d "$_log_dir" ]] || mkdir -p "$_log_dir" 2>/dev/null

# 取最后一条命令（去掉行号前缀）
_cmd=$(history 1 2>/dev/null | sed 's/^[ ]*[0-9]*[ ]*//')
if [[ -n "$_cmd" ]]; then
  # 追加写（含时间戳）
  printf '[%s] %s\n' "$(date +%H:%M:%S)" "$_cmd" >> "$_log_file" 2>/dev/null
fi

# 清理标记
unset MARK42_BASH_LOGGING
