# 🧹 Mark2 智能回收机制设计

> 版本：v2.0
> 创建：2026-06-15 | 修订：2026-06-15（审查后调整）
> 所属：Mark2 项目 / 架构设计
> 原则：先摸清结构，再分析判定，再动手回收。能预防的不等到要回收。

---

## 一、核心分层

```
┌─────────────────────────────────────────────────────┐
│                   第〇层：预防层                       │
│    部署时就把膨胀扼杀在源头——Docker 日志上限、         │
│    journald 大小封顶、Caddy 内置轮转、code-server 会话  │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│           🟢 强制回收（不分析，直接收）                 │
│    /tmp、APT 缓存、死会话轨迹、flat memory、语音音频     │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│           🔵 智能回收（七层四步法）                     │
│    每层独立 → ①发现 ②分析 ③判定 ④回收                │
└─────────────────────────────────────────────────────┘
```

---

## 二、第〇层——预防层（部署时就设好）

预防层的核心原则：**在装的时候就设上限，不让垃圾有机会积累**。

### P1 — Docker Daemon 日志轮转

Docker 默认的 `json-file` 日志驱动**没有大小限制**——单个容器的日志可以长到几十 GB。必须在 `/etc/docker/daemon.json` 里配好：

```json
{
  "log-driver": "local",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

选 `local` 而非 `json-file` 的理由：
- `local` 默认就是 20MB×5=100MB 上限
- `local` 自动压缩，比 json-file 省 50%+ 空间
- `local` 也支持 `docker logs` 命令

配完后 `sudo systemctl restart docker`，新容器自动继承。**这是部署步骤第 4 层（Docker）里的第 1 步**——装完 Docker 立刻配 daemon.json，再启容器。

> ⚠️ 来源：Docker 官方文档。默认 json-file 无限制是生产环境最常见的盘满根因。

### P2 — journald 大小封顶

Ubuntu 24.04 默认 journald 上限约 4GB（文件系统 10%）。对 Mark2 来说太小也太模糊。在 `/etc/systemd/journald.conf` 里加：

```ini
[Journal]
SystemMaxUse=500M
MaxRetentionSec=30day
MaxFileSec=7day
```

- `SystemMaxUse=500M`：总日志不超过 500MB
- `MaxRetentionSec=30day`：最长保留 30 天
- `MaxFileSec=7day`：单个日志文件最多 7 天就轮转

### P3 — Caddy 内置日志轮转

Caddy 有一个已知问题（GitHub issue #5316）：外部 `logrotate` 重命名日志文件后，Caddy 不会自动重新打开新文件。所以**只能用 Caddy 自己的轮转**：

```caddyfile
log {
    output file /var/log/caddy/access.log {
        roll_size    50mb
        roll_keep    10
        roll_keep_for 720h   # 30天
    }
}
```

- `roll_size 50mb`：单文件 50MB 就切（比默认 100MB 激进，8c32g 盘要省着用）
- `roll_keep 10`：最多保留 10 个轮转文件（=500MB 上限）
- `roll_keep_for 720h`：超过 30 天的自动清理

### P4 — code-server 会话限制

启动时加上资源限制参数，减少 session 数据堆积：

```bash
code-server \
  --user-data-dir ~/.local/share/code-server \
  --extensions-dir ~/.local/share/code-server/extensions \
  --max-heap 512 \
  --disable-update-check
```

此外在部署时就建立清理 cron，不等到膨胀再动手（见 L3 层）。

---

## 三、强制回收（不分析，直接收）

| # | 目标 | 命令/动作 | 阈值 | 风险等级 |
|---|------|----------|------|---------|
| F1 | `/tmp/*` | `find /tmp -type f -atime +1 -delete` | >1 天未访问 | 极低 |
| F2 | APT 缓存 | `apt-get clean` | 每次 apt 操作后 | 极低 |
| F3 | Docker build cache | `docker builder prune -f --filter until=24h` | >24h | 低 |
| F4 | 死会话 trajectory | 删除 >2h 无心跳会话的 trajectory + checkpoint | >2h 无心跳 | 低 |
| F5 | flat memory 残留 | `flush-memory-sync.sh` 合并 `memory/2026-*.md` | 立即 | 极低 |
| F6 | 语音/音频 | 删除 `tmp/voice-replies/` 中 >4h 文件 | >4h | 极低 |
| F7 | Docker 悬空镜像 | `docker image prune -f` | dangling | 低 |
| F8 | code-server `/tmp` 残留 | 删除 `/tmp/vscode-*` `/tmp/code-*` `/tmp/node-compile-cache*` | 立即 | 极低 |

> F3 原设计放到了 journald vacuum，v2.0 改由预防层 P2 的 journald.conf 替代——配好就不用 vacuum 了。

---

## 四、触发机制

| 触发方式 | 周期 | 动作 |
|----------|------|------|
| **事件驱动** | 每次收到用户消息 | 仅跑强制回收 F1-F8（60s 门控去重） |
| **定时轻量** | 每 15 分钟 | 强制回收 + L2 会话快照检查 |
| **定时深度** | 每 6 小时 | 全部 7 层走一遍四步法 |
| **每日全量** | 每天 04:00 | 全部 7 层深度回收 + 生成回收日报 |

---

## 五、七层智能回收

### L1 — 统一网关 (Caddy)

**① 发现**
```
组件：Caddy 进程
产出：/var/log/caddy/access.log, /var/log/caddy/error.log
      /var/lib/caddy/.local/share/caddy/ (证书/OCSP 缓存，Caddy 自管)
```

**② 分析**
- ⚠️ Caddy 不兼容外部 logrotate（Caddy reload 后不 reopen 已重命名的文件）
- 需依赖 Caddy 内置 `roll_size` / `roll_keep` / `roll_keep_for`
- 证书和 OCSP staple 由 Caddy 自动更新，几乎不积压

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| 轮转日志 | 由 Caddy 自动管理 | 回收脚本不介入 |
| Caddy 自身日志（非 access） | 检查 `roll_keep` 配置是否到位 | 若未配，告警 |
| 证书缓存 | 由 Caddy ACME 自动管理 | 不介入 |

**④ 回收**
```bash
# 仅兜底——Caddy 配置正确时不需要跑这条
# 若 Caddyfile 漏配 roll_keep：
find /var/log/caddy/ -name "*.log.*" -mtime +30 -delete
```

> 📌 v2.0 改动：不再用 logrotate。Caddy 轮转统一走 Caddyfile `log {}` 指令。

---

### L2 — 贾维斯核心 (Gateway + embed + infos-handle)

**① 发现**
```
组件：
  gateway        ~/.local/share/openclaw/sessions/
  broker         ~/.local/state/openclaw/broker/
  supervisor     ~/.local/state/openclaw/supervisor/
  frontstage     ~/.local/state/openclaw/frontstage-guardian/
  health-collector  ~/.local/state/openclaw/health-collector/
  task-scheduler ~/.local/state/openclaw/task-scheduler/
  lifecycle      ~/.local/state/openclaw/lifecycle-maintainer/
  voice          tmp/voice-replies/
  backup         /mnt/data/openclaw/session-backup/
  recycle         ~/.local/state/openclaw/recycle/
```

**② 分析结构**

| 子组件 | 产出物 | 文件类型 | 增长模式 |
|--------|--------|---------|---------|
| gateway | session JSON / checkpoint / trajectory | 多文件目录 | 每轮对话 +0.1-1MB |
| broker | events.jsonl / views/*.json | 单文件追加 + 多视图 | 每事件 +1 行 (~200B) |
| supervisor | status.json / notify-state.json | 单文件覆盖 | 固定 |
| frontstage | guardian.log / state.json | 单文件覆盖+追加 | 缓慢 |
| health-collector | collector.log | 单文件追加 | 缓慢 |
| task-scheduler | scheduler.log | 单文件追加 | 缓慢 |
| lifecycle | maintainer.log | 单文件追加 | 缓慢 |
| voice | *.mp3 / *.wav | 多文件 | 每次语音 +50-200KB |
| backup | context-summary.md / daily-*.md | 多文件 | 每 30min 更新 |
| recycle | reports/*.json | 多文件 | 每天 +1 |

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| 死会话 | session 最后活跃 >4h 且非当前主会话 | 删 checkpoint + trajectory，保留主 JSON |
| 当前会话肥大 | trajectory >5MB | 告警（gateway 内部处理，回收不越权） |
| 会话总目录 | >50 个死会话 | 批量清理 |
| broker events | 行数 >5000 **或** 最早事件 >7 天 | 截断到最近 2000 行 |
| broker views | 存在即可 | 不主动删（下次重建覆盖） |
| watcher logs | 各 .log >1MB | 截断到最近 1000 行 |
| voice audio | >4h | 删除（强制回收F6 已覆盖） |
| session backup | >7 天 | 删除 |
| usage-cost-cache | >1MB | 重置 |
| recycle reports | >30 天 | 删除 |

**④ 回收**
```bash
# broker event 截断
if [ $(wc -l < ~/.local/state/openclaw/broker/events.jsonl) -gt 5000 ]; then
    tail -n 2000 ~/.local/state/openclaw/broker/events.jsonl > /tmp/events-trunc.jsonl
    mv /tmp/events-trunc.jsonl ~/.local/state/openclaw/broker/events.jsonl
fi

# watcher 日志截断
for log in ~/.local/state/openclaw/*/collector.log \
           ~/.local/state/openclaw/*/scheduler.log \
           ~/.local/state/openclaw/*/maintainer.log \
           ~/.local/state/openclaw/*/guardian.log; do
    [ -f "$log" ] && [ $(stat -c%s "$log" 2>/dev/null || echo 0) -gt 1048576 ] && \
        tail -n 1000 "$log" > "${log}.tmp" && mv "${log}.tmp" "$log"
done

# 回收自身报告清理
find ~/.local/state/openclaw/recycle/reports/ -name "*.json" -mtime +30 -delete
```

> 📌 v2.0 改动：broker events 新增时间维度的 7 天判定（原来只看行数）。
> 📌 v2.0 新增：回收日报自身也会堆积，加了 30 天清理。

---

### L3 — 开发工作台 (code-server)

**① 发现**
```
组件：
  code-server      ~/.local/share/code-server/
  VS Code Server   ~/.vscode-server/（如果用 Remote SSH 的话；Mark2 本地部署走 code-server，这个路径可能不存在）
  /tmp 残留        /tmp/vscode-* /tmp/code-* /tmp/mcp-* /tmp/node-compile-cache*
```

**② 分析结构——按安全分区**

| 分区 | 路径 | 内容 | 清理安全性 |
|------|------|------|-----------|
| 🛑 保护区 | `User/settings.json` | 用户设置 | 绝不碰 |
| 🛑 保护区 | `extensions/` | 已安装扩展 | 绝不碰 |
| 🟡 谨慎区 | `User/workspaceStorage/` | 每个工作区的状态缓存 | 按工作区存活判定 |
| 🟢 安全区 | `Machine/` | 终端历史/日志 | 可清理 |
| 🟢 安全区 | `CachedData/` | 扩展下载缓存 | 可清理 |
| 🟢 安全区 | `Backups/` | 设置备份 | 可清理 |
| 🟢 安全区 | `logs/` | code-server 自身日志 | 可清理 |
| 🟢 安全区 | `/tmp/vscode-*`, `/tmp/code-*` | 远程连接残留 | 可清理 |

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| workspaceStorage | 对应工作区目录已不存在 | 删除该 workspaceStorage 文件夹 |
| workspaceStorage | 对应工作区存在但 >30 天未修改 | 保留（状态可能还有用） |
| Machine/ | 存在 | 定期清理日志文件 |
| CachedData/ | 存在 | 安全删除（扩展会重新下载） |
| Backups/ | >7 天 | 删除 |
| logs/ | >7 天 | 删除 |
| `/tmp/vscode-*` 等 | 存在 | 立即删除（强制回收 F8） |
| 全局 npm/pip 缓存 | >30 天未访问 | `npm cache clean --force` / `pip cache purge` |

**④ 回收**
```bash
# workspaceStorage 清理：检查每个工作区 ID 对应的目录是否还存在
WS_DIR="$HOME/.local/share/code-server/User/workspaceStorage"
if [ -d "$WS_DIR" ]; then
    for ws_id in "$WS_DIR"/*/; do
        ws_json="${ws_id}workspace.json"
        if [ -f "$ws_json" ]; then
            # 从 workspace.json 提取文件夹路径，检查是否存在
            folder=$(python3 -c "
import json, os
try:
    d = json.load(open('$ws_json'))
    fp = d.get('folder', '')
    if fp.startswith('vscode-remote://') or fp.startswith('file://'):
        fp = fp.split('://',1)[-1] if '://' in fp else fp
    print(fp)
except: pass" 2>/dev/null)
            if [ -n "$folder" ] && [ ! -d "$folder" ]; then
                echo "ORPHAN workspaceStorage: $ws_id (folder gone: $folder)"
                rm -rf "$ws_id"
            fi
        fi
    done
fi

# Machine/terminal logs
find "$HOME/.local/share/code-server/Machine/" -name "*.log" -mtime +7 -delete 2>/dev/null

# CachedData
rm -rf "$HOME/.local/share/code-server/CachedData/"* 2>/dev/null

# Backups older than 7 days
find "$HOME/.local/share/code-server/Backups/" -mtime +7 -delete 2>/dev/null

# code-server logs
find "$HOME/.local/share/code-server/logs/" -mtime +7 -delete 2>/dev/null

# /srv/projects git gc
for repo in /srv/projects/*/; do
    if [ -d "${repo}.git" ]; then
        git -C "$repo" gc --auto --quiet
    fi
done
```

> 📌 v2.0 改动：拆分为安全/谨慎/保护区。不再一刀切删 Machine/。新增 workspaceStorage 按工作区存活判定。新增 `/tmp` vscode 残留清理。npm/pip 缓存清理。

---

### L3-A — 开发工作台产出物（图片/视频/文档）

**① 发现**
```
组件:
  图片产出    /srv/projects/image/outputs/
  视频产出    /mnt/data/video-outputs/
  文档产出    /srv/projects/docs/outputs/
  标记保留    /srv/projects/archives/
```

**② 分析**

| 子组件 | 产出物 | 增长模式 |
|--------|--------|---------|
| image/outputs | *.png, *.webp, *.jpg | 每批 1-50MB |
| video-outputs | *.mp4 | 每批 50-500MB |
| docs/outputs | *.docx, *.xlsx, *.pptx, *.pdf | 每批 1-20MB |

**③ 判定规则（来自开发工作台设计 v2.1）**

| 目标 | 条件 | 动作 |
|------|------|------|
| 图片批次 | /srv/projects/image/outputs/ 总大小 >500MB | 删最旧批次直到 ≤500MB |
| 图片批次 | 未超 500MB 但批次 >7 天 | 删除该批次 |
| 视频批次 | /mnt/data/video-outputs/ 总大小 >2GB | 删最旧批次直到 ≤2GB |
| 视频批次 | 未超 2GB 但批次 >7 天 | 删除该批次 |
| 文档批次 | /srv/projects/docs/outputs/ 总大小 >200MB | 删最旧批次直到 ≤200MB |
| 文档批次 | 未超 200MB 但批次 >7 天 | 删除该批次 |
| 标记保留 | 用户说"保留这个文件/这批" | 移入 /srv/projects/archives/，不受清理 |

**④ 回收**
```bash
# 通用容量检查+清理函数
clean_by_age_and_size() {
  local DIR=$1 MAX_MB=$2 MAX_DAYS=$3
  # 按修改时间排序，从最旧开始删直到低于阈值
  while [ "$(du -sm "$DIR" 2>/dev/null | cut -f1)" -gt "$MAX_MB" ]; do
    OLDEST=$(find "$DIR" -mindepth 1 -maxdepth 1 -type d | sort | head -1)
    [ -z "$OLDEST" ] && break
    rm -rf "$OLDEST"
  done
  # 时间兜底：删除超过 MAX_DAYS 天的批次
  find "$DIR" -mindepth 1 -maxdepth 1 -type d -mtime +"$MAX_DAYS" -exec rm -rf {} \;
}

clean_by_age_and_size /srv/projects/image/outputs/ 500 7
clean_by_age_and_size /mnt/data/video-outputs/ 2048 7
clean_by_age_and_size /srv/projects/docs/outputs/ 200 7
```

---

### L4 — 自部署服务 (Docker + Portainer + 容器)

**① 发现**
```
组件：
  Docker daemon    /var/lib/docker/
  Portainer        portainer_data volume
  Nextcloud        nextcloud_* volumes
  Syncthing        syncthing_data volume
  Uptime Kuma      uptime-kuma_data volume
  Lsky Pro         lskypro_data volume
  微信查阅器         wechat-viewer_data volume
  图床             image-host_data volume
```

**② 分析——四类 Docker 垃圾分别处理**

```
悬空镜像（dangling）  →  无 tag、无容器引用            →  安全回收
未使用镜像（unused）  →  有 tag 但未被任何容器引用      →  谨慎回收（加 until 过滤）
停止容器             →  已退出、可能还需保留数据/日志    →  分时间窗口
未使用卷             →  匿名卷 vs 命名卷                →  分级处理
```

> ⚠️ **关键安全规则**：
> - `docker system prune` 不用于 Mark2。它一次性删四种东西，出了事分不清。
> - **命名卷（named volumes）只标记不自动删**。命名卷通常包含持久数据（Nextcloud、Portainer），误删不可逆。
> - 匿名卷（anonymous volumes）和悬空卷（dangling volumes）可自动回收。
> - **容器日志不再靠回收脚本截断**——由预防层 P1 的 daemon.json `local` 驱动 + `max-size=10m` 自动轮转。

**③ 判定规则**

| 目标 | 条件 | 动作 | 频率 |
|------|------|------|------|
| 悬空镜像 | `docker image ls -f dangling=true` | 立即 prune | 每次深度扫描 |
| 未使用镜像 | `-f dangling=false` 且未被容器引用 | prune --filter until=336h（2 周保护期） | 每周 |
| 停止容器 | stopped >7 天 | prune --filter until=168h | 每周 |
| 停止容器 | stopped ≤7 天 | 保留（可能还要看日志/数据） | - |
| 匿名/悬空卷 | 未被任何容器挂载 | prune -f（仅匿名） | 每日 |
| 命名卷 | 未被任何容器挂载 | **只报告不删除**——写入日报 `warnings` | 每周 |
| 构建缓存 | >24h | builder prune | 强制回收 F3 |
| 容器日志 | 由 daemon.json `local` 驱动自动管理 | 回收脚本不介入 | - |
| Portainer 数据 | 由 Portainer 自身管理 | 不介入 | - |
| Nextcloud 回收站/版本 | 由 Nextcloud 自身管理 | 不介入 | - |

**④ 回收**
```bash
# 悬空镜像——每次都收
docker image prune -f --filter "dangling=true"

# 未使用镜像——2 周保护期
docker image prune -a -f --filter "until=336h"

# 停止 >7 天的容器
docker container prune -f --filter "until=168h"

# 匿名/悬空卷（不含命名卷）
docker volume ls -qf "dangling=true" | while read vol; do
    [ -n "$vol" ] && docker volume rm "$vol"
done

# 命名卷检查——只报告
UNUSED_NAMED=$(docker volume ls -qf "dangling=true" --filter "name=" 2>/dev/null || true)
# 注：docker volume ls 不直接支持"列出所有未使用命名卷"的 filter
# 替代方案：对比所有命名卷和 docker volume ls -qf dangling=true
ALL_NAMED=$(docker volume ls -q | grep -v '^[a-f0-9]\{64\}$' || true)
for vol in $ALL_NAMED; do
    if ! docker ps -aq --filter "volume=$vol" | grep -q .; then
        echo "UNUSED_NAMED_VOLUME: $vol (NOT auto-deleted)"
    fi
done

# 未使用网络
docker network prune -f --filter "until=24h"
```

> 📌 v2.0 最大改动：从 "docker system prune" 一步出清 → 四项独立目标分别判定和回收。
> 📌 容器日志回收从「截断脚本」改为「预防层 P1——daemon.json 配好 log-driver 自动轮转」。

---

### L5 — 远程连接 (Tailscale)

**① 发现**
```
组件：
  tailscaled       journald 日志（由预防层 P2 管理）
  state            /var/lib/tailscale/tailscaled.state（核心状态，不碰）
  logs             /var/lib/tailscale/tailscaled.log*（Tailscale 自己的日志文件）
```

**② 分析**
- `tailscaled.state`：**绝不能动**——包含节点身份和密钥
- Tailscale 在 `/var/lib/tailscale/` 下会写自己的日志文件（独立于 journald）
- 部分版本会堆积 `tailscaled.log` 轮转文件

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| journald | 由预防层 P2 管理 | 不介入 |
| tailscaled.state | 始终保留 | 不介入 |
| tailscaled.log* | 轮转文件 >7 天 | 删除 |
| 其他 `/var/lib/tailscale/` 文件 | 非 .state / .key / .conf 且 >30 天 | 标记为可疑，报告不删除 |

**④ 回收**
```bash
# Tailscale 日志轮转文件
find /var/lib/tailscale/ -name "*.log.*" -mtime +7 -delete 2>/dev/null
find /var/lib/tailscale/ -name "*.log" -size +10M -exec truncate -s 0 {} \; 2>/dev/null
```

> 📌 v2.0 改动：发现 Tailscale 在 `/var/lib/tailscale/` 下有独立日志文件，新增回收路径。明确标记 tailscaled.state 为保护区。

---

### L6 — 数据备份

**① 发现**
```
组件：
  每日配置备份    /mnt/data/backups/configs/
  每日数据备份    /mnt/data/backups/data/
  audit 归档     /mnt/data/backups/audit/
  Git 镜像        /mnt/data/backups/git-mirrors/
  session backup  /mnt/data/openclaw/session-backup/
```

**② 分析结构（不变）**

| 子组件 | 产出物 | 增长模式 |
|--------|--------|---------|
| configs | daily .tar.gz | +5-20MB/天 |
| data | daily .tar.gz（docker volumes） | +100-500MB/天 |
| audit | 归档的 audit 日志 | 按需，压缩后很小 |
| git-mirrors | bare repos | git gc 定期跑 |
| session-backup | context-summary.md + daily-*.md | ~500KB/天 |

**③ 判定规则——分层保留（不变，确认合理）**

| 目标 | 条件 | 动作 |
|------|------|------|
| configs tar | 最近 7 天 | 保留每日 |
| configs tar | 8-30 天 | 保留每周一那份 |
| configs tar | >30 天 | 删除 |
| data tar | 最近 3 天 | 保留每日 |
| data tar | 4-14 天 | 保留每周日那份 |
| data tar | >14 天 | 删除 |
| git-mirrors | 每次深度扫描 | `git gc --auto` |
| session-backup | >7 天 | 删除 |

| 备份总容量预警 | 条件 | 动作 |
|--------------|------|------|
| /mnt/data/backups | >80% 分区容量 | 🔴 告警 + 日报高亮 |
| /mnt/data/backups | >50% 分区容量 | 🟡 日报提醒 |

**④ 回收**
```bash
# configs 分层保留——保留最近 7 天全部 + 8-30 天中每周一那份
find /mnt/data/backups/configs/ -name "*.tar.gz" -mtime +7 ! -name "*Mon*" ! -name "*Monday*" -delete 2>/dev/null
find /mnt/data/backups/configs/ -name "*.tar.gz" -mtime +30 -delete 2>/dev/null

# data 分层保留
find /mnt/data/backups/data/ -name "*.tar.gz" -mtime +3 ! -name "*Sun*" ! -name "*Sunday*" -delete 2>/dev/null
find /mnt/data/backups/data/ -name "*.tar.gz" -mtime +14 -delete 2>/dev/null

# audit 归档——由 L7 写入，这里只做过期清理
find /mnt/data/backups/audit/ -name "audit.log.*" -mtime +90 -delete 2>/dev/null

# git gc
find /mnt/data/backups/git-mirrors/ -mindepth 1 -maxdepth 1 -type d -exec git -C {} gc --auto --quiet \; 2>/dev/null

# 容量预检
USAGE=$(df /mnt/data/backups 2>/dev/null | awk 'NR==2{print $5}' | tr -d '%')
if [ -n "$USAGE" ] && [ "$USAGE" -gt 80 ]; then
    echo "CRITICAL: /srv/backups at ${USAGE}%"
fi
```

---

### L7 — 安全守护 (ufw / fail2ban / auditd / trivy)

**① 发现**
```
组件：
  ufw             /var/log/ufw.log
  fail2ban        /var/log/fail2ban.log
  auditd          /var/log/audit/audit.log
  trivy           ~/.cache/trivy/
```

**② 分析结构**

| 子组件 | 产出物 | 轮转方式 | 特殊性 |
|--------|--------|---------|--------|
| ufw | 防火墙日志 | logrotate (Ubuntu 自带) | 正常量小；被攻击时暴增，需告警 |
| fail2ban | 封禁日志 | logrotate (Ubuntu 自带) | ban 自动过期，日志保留即可 |
| auditd | 审计轨迹 | auditd 自身 `max_log_file_action=ROTATE` | **有合规保留要求** |
| trivy | 扫描缓存 | 手动 | 每次扫描前清缓存可避免版本混淆 |

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| ufw.log | 轮转文件 >30 天 | 删除 |
| ufw.log | >100MB（异常暴增） | 🔴 告警 + 保留最近 5000 行 |
| fail2ban.log | 轮转文件 >30 天 | 删除 |
| fail2ban 封禁数据库 | 由 fail2ban 自动过期管理 | 不介入 |
| auditd | 由 auditd.conf 管理 `num_logs=10` `max_log_file=50` | 不主动回收 |
| auditd | 磁盘占用 >1GB | 归档到 `/srv/backups/audit/` 后清理旧轮转 |
| trivy cache | 每次扫描后 | `trivy image --clear-cache` 或在扫描前 `rm -rf ~/.cache/trivy/` |

**④ 回收**
```bash
# ufw/fail2ban 依赖 Ubuntu 自带 logrotate（已在安全体系设计里配置）
# 回收脚本只做异常告警 + 攻击暴增时的紧急截断

# ufw 异常暴涨检测
UFW_SIZE=$(stat -c%s /var/log/ufw.log 2>/dev/null || echo 0)
if [ "$UFW_SIZE" -gt 104857600 ]; then
    echo "WARN: ufw.log = $((UFW_SIZE / 1048576))MB — possible brute force"
    tail -n 5000 /var/log/ufw.log > /tmp/ufw-trunc.log
    mv /tmp/ufw-trunc.log /var/log/ufw.log
fi

# auditd 归档
AUDIT_USAGE=$(du -sm /var/log/audit/ 2>/dev/null | cut -f1)
if [ -n "$AUDIT_USAGE" ] && [ "$AUDIT_USAGE" -gt 1024 ]; then
    mkdir -p /mnt/data/backups/audit/
    cp /var/log/audit/audit.log.* /mnt/data/backups/audit/ 2>/dev/null || true
    find /var/log/audit/ -name "audit.log.*" -mtime +30 -delete 2>/dev/null
fi

# trivy cache
rm -rf ~/.cache/trivy/ 2>/dev/null
```

> 📌 v2.0 改动：明确 auditd 自身有轮转机制（`/etc/audit/auditd.conf`），回收只做归档兜底。新增 ufw 暴涨检测和紧急截断。

---

## 六、执行脚本框架

```
mark2-recycle.py
├─ --mode force         只跑强制回收 F1-F8（事件驱动）
├─ --mode light         强制 + L2 快检（每 15min）
├─ --mode deep          全部 7 层四步法（每 6h）
├─ --mode daily         全部 7 层 + 日报（每天 04:00）
├─ --layer N            只跑某层（调试用）
├─ --dry-run            只分析不执行（发现 + 分析 + 判定，跳过回收）
└─ --report-out PATH    输出回收日报 JSON
```

### 日报格式

```json
{
  "time": "2026-06-16T04:00:00+08:00",
  "mode": "daily",
  "layers": {
    "L1_caddy":          { "discovered": {...}, "recycled": {...}, "issues": [] },
    "L2_core":           { "discovered": {...}, "recycled": {...}, "issues": [] },
    "L3_code_server":    { "discovered": {...}, "recycled": {...}, "issues": [] },
    "L4_docker":         { "discovered": {...}, "recycled": {...}, "issues": [] },
    "L5_tailscale":      { "discovered": {...}, "recycled": {...}, "issues": [] },
    "L6_backup":         { "discovered": {...}, "recycled": {...}, "issues": [] },
    "L7_security":       { "discovered": {...}, "recycled": {...}, "issues": [] }
  },
  "total_freed_mb": 1145,
  "warnings": [
    "UNUSED_NAMED_VOLUME: nextcloud_data (NOT auto-deleted)",
    "auditd /var/log/audit 已达 1.2GB，已自动归档到 /srv/backups/audit/",
    "/srv/backups 分区容量 82%，建议扩容或缩短 data 保留天数"
  ]
}
```

> 📌 v2.0 改动：报告从每层可选字段改为 7 层全部必出。warnings 加入命名卷保留通知和分区容量告警。

---

## 七、与 Mark1 和部署手册的关系

| Mark1 机制 | Mark2 去向 |
|-----------|-----------|
| lifecycle-maintainer (每 5min) | 迁移到 Mark2，纳入 L2 层智能回收 |
| session-size-watcher (事件 + 每 10min) | 迁移到 Mark2，纳入强制回收 F4 + L2 判定 |
| cleanup-temp.sh | 拆分进强制回收 F1/F6/F8 |
| cleanup-old-audio.sh | 合并到强制回收 F6 |
| scratch-cleanup.py | Mark2 无 /mnt/data/scratch，废弃 |
| memory flush sync | 保留，强制回收 F5 |
| session-backup clean (>7d) | 迁移到 L6 备份回收 |
| journald vacuum | 废弃——由预防层 P2 journald.conf 替代 |

| 部署手册关联 | 位置 |
|------------|------|
| Docker daemon.json 预防配置 | 部署手册步骤 4（装完 Docker 后立刻配） |
| journald.conf 预防配置 | 部署手册步骤 1（系统基础） |
| Caddy 内置日志轮转 | 部署手册步骤 5（Caddy Caddyfile 配置） |
| code-server 启动参数 | 部署手册步骤 8（code-server） |
| 回收机制部署 | 部署手册第 11 层 |
| 回收日报接入 Control UI | 通过 broker → infos-handle → 仪表板 |

---

## 八、部署位置

- **设计文档**：本文件 `docs/贾维斯中枢-Mark2-回收机制设计.md`
- **脚本入口**：`scripts/mark2-recycle.py`（待开发）
- **预防层配置**：随各层部署步骤写入（`/etc/docker/daemon.json`、`/etc/systemd/journald.conf`、Caddyfile 等）
- **日报输出**：`~/.local/state/openclaw/recycle/reports/`
- **产出物保留接入回收**: 开发工作台图片/视频/文档保留策略统一由 mark2-recycle.py L3-A 执行
- **触发注册**：
  - 事件驱动 hook → `ACTIVE_RULES.md` 事件钩子
  - 定时轻量 → systemd timer（`mark2-recycle-light.timer`，每 15min）
  - 定时深度 → systemd timer（`mark2-recycle-deep.timer`，每 6h）
  - 每日全量 → systemd timer（`mark2-recycle-daily.timer`，每天 04:00）

---

## 九、v2.0 修订日志

| 变更 | 原设计（v1.0） | 修订后（v2.0） | 依据 |
|------|--------------|--------------|------|
| + 新增预防层 | 无 | 部署时配 daemon.json / journald.conf / Caddy 内置轮转 | 治本优于治标 |
| L1 Caddy | logrotate 轮转 | Caddy 内置 roll_size/roll_keep/roll_keep_for | Caddy issue #5316：不兼容外部 logrotate reopen |
| L2 broker | 仅按行数 >5000 | 新增时间维度 >7 天双判定 | 低频事件也会堆积 |
| L2 recycle | 无 | 回收日报自身 >30 天自清 | 回收机制自己也会产垃圾 |
| L3 code-server | 一刀切清理 session/terminal | 拆分安全区/谨慎区/保护区，workspaceStorage 按工作区存活判定 | 避免误删扩展和设置 |
| L3 /tmp | 无 | 新增 vscode-*/code-*/mcp-* 残留清理 | VSCode 远程连接残留是常见积压源 |
| L4 Docker | `docker system prune` 一步出清 | 四项独立目标分别 prune，命名卷只报告不删 | `docker system prune` 对生产环境不安全（Docker 社区共识） |
| L4 容器日志 | 回收脚本截断 >100MB 日志 | daemon.json `local` 驱动 + max-size=10m 自动轮转 | 预防优于被动截断 |
| L5 Tailscale | 无独立回收 | 新增 `/var/lib/tailscale/*.log*` 清理 | Tailscale 有独立日志文件不在 journald 里 |
| L6 备份 | 无容量告警 | 新增 /srv/backups 分区 50%/80% 两级预警 | 备份盘满是最危险的故障之一 |
| L7 auditd | 手动清理 | 明确 auditd.conf 自带轮转，回收只做归档兜底 | auditd 自身有成熟的轮转机制 |
| L7 ufw | 仅正常轮转 | 新增 >100MB 暴涨检测 + 紧急截断 | 被 DDoS/爆破时 ufw.log 会瞬间暴涨 |
| F3 | `journalctl --vacuum-size=200M` | 废弃，改由预防层 P2 journald.conf | journald.conf 系统级配置比定时 vacuum 更可靠 |
