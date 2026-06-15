# 🧹 Mark2 智能回收机制设计

> 版本：v1.0-draft
> 创建：2026-06-15
> 所属：Mark2 项目 / 架构设计
> 原则：先摸清结构，再分析判定，再动手回收。不搞一刀切。

---

## 一、设计哲学

Mark1 的回收逻辑是「文件超过 X 天 → 删除」。这在单层架构下够用。
Mark2 是一栋七层楼，每层的垃圾产出机制完全不同——日志、镜像层、会话快照、审计轨迹、备份归档——这些东西的保留策略不能共用一套规则。

因此 Mark2 回收机制采用**四步法**：

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  ① 发现  │ → │  ② 分析  │ → │  ③ 判定  │ → │  ④ 回收  │
│ Discover │    │ Analyze  │    │ Decide   │    │ Recycle  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
 扫这层有什么    每项是什么结构     哪些要收        执行清理
```

| 步骤 | 含义 | 例子（L4 Docker） |
|------|------|------------------|
| ① 发现 | 扫描该层所有组件及其产出物 | 列出所有 image / container / volume / network |
| ② 分析 | 理解每项的结构和状态 | image 被哪个容器引用？container 是否停止？ |
| ③ 判定 | 根据规则决定是否回收 | 停止 >7 天 → 回收；被活跃容器引用的 image → 保留 |
| ④ 回收 | 执行清理并记录 | `docker image prune` + 写入回收日志 |

每一层独立走一遍这四步。层与层之间不互相假设、不共用阈值。

---

## 二、两级回收体系

```
🟢 强制回收                          🔵 智能回收
（不分析，直接收）                     （走四步法）
├─ /tmp/**           >1天             ┌─ L1 Caddy ───────────── 日志轮转
├─ APT 缓存          >7天             ├─ L2 贾维斯核心 ───────── 会话/事件/音频
├─ systemd journal   journald 管理    ├─ L3 code-server ──────── 会话/扩展缓存
├─ Docker build cache  prune         ├─ L4 Docker ───────────── 镜像/容器/卷/日志
├─ 会话死进程轨迹    >2h 无心跳        ├─ L5 Tailscale ─────────── 连接日志
├─ flat memory 残留  立即合并          ├─ L6 备份 ─────────────── 分层保留
└─ 语音音频          >4h              └─ L7 安全 ─────────────── 审计轨迹/扫描缓存
```

强制回收是「不管扫不扫描，这些肯定要收」的东西——Mark1 已验证安全、零误删。
智能回收是 Mark2 新增的逐层体系——每层有独立的规则和阈值。

---

## 三、触发机制

复用 Mark1 的双重触发，只改周期和范围：

| 触发方式 | 周期 | 动作 |
|----------|------|------|
| **事件驱动** | 每次收到用户消息 | 仅跑强制回收（60s 门控去重） |
| **定时轻量** | 每 15 分钟 | 强制回收 + L2 会话快照检查 + L4 容器日志截断检查 |
| **定时深度** | 每 6 小时 | 全部 7 层走一遍四步法 |
| **每日全量** | 每天 04:00 | 全部 7 层深度回收 + 生成回收日报 |

---

## 四、强制回收清单（无脑收）

这些是 Mark1 已验证过的东西——无论哪一层、无论什么状态，到点就收，不分析：

| # | 目标 | 命令/动作 | 阈值 |
|---|------|----------|------|
| F1 | `/tmp/*` | `find /tmp -type f -atime +1 -delete` | >1 天未访问 |
| F2 | APT 缓存 | `apt-get clean` | >7 天 |
| F3 | systemd journal | `journalctl --vacuum-size=200M` | >200MB |
| F4 | Docker build cache | `docker builder prune -f --filter until=24h` | >24h |
| F5 | session trajectory (死会话) | 删除 >2h 无心跳会话的 trajectory + checkpoint | >2h 无心跳 |
| F6 | flat memory 残留 | `flush-memory-sync.sh` 合并 `memory/2026-*.md` | 立即 |
| F7 | 语音/音频 | 删除 `tmp/voice-replies/` 中 >4h 文件 | >4h |
| F8 | Docker 悬空镜像 | `docker image prune -f` | dangling |

---

## 五、七层智能回收

### L1 — 统一网关 (Caddy)

**① 发现**
```
组件：Caddy 进程
产出：/var/log/caddy/access.log, /var/log/caddy/error.log
结构：纯文本访问日志，按天轮转
```

**② 分析**
- Caddy 自带日志轮转（`log` 指令配置）
- 每行 = 一条 HTTP 请求记录
- 若启用 JSON 结构化日志，体积增长更快

**③ 判定规则**

| 条件 | 动作 |
|------|------|
| access.log >100MB | 触发轮转 |
| 轮转文件 >7 天 | 压缩为 .gz |
| 压缩文件 >30 天 | 删除 |
| error.log >50MB | 触发轮转并告警（异常） |

**④ 回收命令**
```bash
# Caddy 日志轮转由 Caddy 自身或 logrotate 处理
# Mark2 统一在 Caddyfile 里配：
# log {
#     output file /var/log/caddy/access.log {
#         roll_size 100mb
#         roll_keep 30
#         roll_keep_for 720h
#     }
# }
# 回收脚本只做兜底：
find /var/log/caddy/ -name "*.log.*.gz" -mtime +30 -delete
```

---

### L2 — 贾维斯核心 (Gateway + embed + infos-handle)

**① 发现**
```
组件：
  gateway        ~/.local/share/openclaw/sessions/
  broker         ~/.local/state/openclaw/broker/
  supervisor     ~/.local/state/openclaw/supervisor/
  frontstage     ~/.local/state/openclaw/frontstage/
  health-collector  ~/.local/state/openclaw/health-collector/
  task-scheduler ~/.local/state/openclaw/task-scheduler/
  lifecycle      ~/.local/state/openclaw/lifecycle-maintainer/
  voice          tmp/voice-replies/
  backup         /mnt/data/openclaw/session-backup/
```

**② 分析结构**

| 子组件 | 产出物 | 文件类型 | 增长模式 |
|--------|--------|---------|---------|
| gateway | session JSON / checkpoint / trajectory | 多文件目录 | 每轮对话 +0.1-1MB |
| broker | events.jsonl / views/*.json | 单文件追加 + 多视图 | 每事件 +1行 (~200B) |
| supervisor | status.json / notify-state.json | 单文件覆盖 | 固定大小 |
| frontstage | guardian state | 单文件覆盖 | 固定大小 |
| health-collector | collector.log / state.json | 单文件追加 | 缓慢增长 |
| task-scheduler | scheduler.log | 单文件追加 | 缓慢增长 |
| lifecycle | maintainer.log | 单文件追加 | 缓慢增长 |
| voice | *.mp3 / *.wav | 多文件 | 每次语音 +50-200KB |
| backup | context-summary.md / daily-*.md | 多文件 | 每 30min 更新 |

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| 死会话 | session 最后活跃 >4h 且非当前主会话 | 删 checkpoint + trajectory，保留主 JSON |
| 当前会话肥大 | trajectory >5MB | 建议压缩（gateway 内部处理，回收只告警） |
| 会话总目录 | >50 个死会话 | 批量清理 |
| broker events | events.jsonl 行数 >5000 或 >7 天 | 截断到最近 2000 行 |
| broker views | 视图文件存在 | 不主动删（下次重建覆盖） |
| watcher logs | 各 watcher .log >1MB | 截断到最近 1000 行 |
| voice audio | >4h | 删除 |
| session backup | >7 天 | 删除 |
| usage-cost-cache | >1MB | 重置 |

**④ 回收**
```bash
# 核心：继承 Mark1 session-size-watcher + lifecycle-maintainer
# 新增：broker event 截断
tail -n 2000 ~/.local/state/openclaw/broker/events.jsonl > /tmp/events-trunc.jsonl
mv /tmp/events-trunc.jsonl ~/.local/state/openclaw/broker/events.jsonl

# watcher 日志截断
for log in ~/.local/state/openclaw/*/collector.log \
           ~/.local/state/openclaw/*/scheduler.log \
           ~/.local/state/openclaw/*/maintainer.log \
           ~/.local/state/openclaw/*/guardian.log; do
    [ -f "$log" ] && [ $(stat -c%s "$log") -gt 1048576 ] && \
        tail -n 1000 "$log" > "${log}.tmp" && mv "${log}.tmp" "$log"
done
```

---

### L3 — 开发工作台 (code-server)

**① 发现**
```
组件：
  code-server      ~/.local/share/code-server/
  VS Code 扩展      ~/.local/share/code-server/extensions/
  工作区存储         ~/.vscode-server/
  终端日志           ~/.local/share/code-server/Machine/
  最近打开           ~/.local/share/code-server/User/globalStorage/
```

**② 分析结构**

| 子组件 | 产出物 | 风险 |
|--------|--------|------|
| code-server session | 每次打开窗口产生 session 数据 | 长期不关的窗口会堆积 |
| extensions cache | 扩展下载缓存、已卸载扩展的残留 | 容易膨胀 |
| workspace storage | 各项目的工作区状态 | 小文件但数量多 |
| terminal logs | 终端输出缓冲 | 长时间运行的终端可能很大 |
| git objects | /srv/projects 下各 repo 的 .git | git gc 需要定期跑 |

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| code-server session | 非活跃 >24h | 清理 session 数据 |
| 废弃扩展缓存 | 扩展已卸载但缓存仍在 | 删除 |
| terminal output | >10MB 且终端已关闭 | 截断 |
| git 松散对象 | `git count-objects -v` >1000 | `git gc --auto` |
| node_modules | npm/pip 缓存（全局） | 清理 >30 天未访问的缓存 |

**④ 回收**
```bash
# code-server session 清理
find ~/.local/share/code-server/ -name "*.log" -mtime +7 -delete
find ~/.local/share/code-server/Machine/ -type f -mtime +14 -delete

# git gc 各项目
for repo in /srv/projects/*/; do
    if [ -d "${repo}.git" ]; then
        git -C "$repo" gc --auto --quiet
    fi
done
```

---

### L4 — 自部署服务 (Docker + Portainer + 容器)

**① 发现**
```
组件：
  Docker daemon    /var/lib/docker/
  Portainer        portainer_data volume
  Nextcloud        nextcloud_data volume
  Syncthing        syncthing_data volume
  Uptime Kuma      uptime-kuma_data volume
  Lsky Pro         lskypro_data volume
  微信查阅器         wechat-viewer_data volume
  图床             image-host_data volume
```

**② 分析结构**

| 子组件 | 产出物 | 类型 | 分析方式 |
|--------|--------|------|---------|
| Docker | dangling images | disk | `docker image ls -f dangling=true` |
| Docker | stopped containers | process | `docker ps -a -f status=exited` |
| Docker | unused volumes | disk | `docker volume ls -f dangling=true` |
| Docker | unused networks | network | `docker network ls -f dangling=true` |
| Docker | build cache | disk | `docker system df` |
| 各容器 | 容器内日志 | disk | `docker inspect --format '{{.LogPath}}' <name>` |
| Portainer | session/statistics | volume | portainer_data volume 内 |

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| dangling images | 悬空（无 tag 无引用） | 立即删除 |
| stopped containers | 停止 >7 天 | 删除 |
| unused volumes | 未被任何容器挂载 | 标记 30 天后删除（安全缓冲） |
| unused networks | 未被任何容器连接 | 删除 |
| build cache | >24h | prune |
| 容器日志 | >100MB | 截断到最近 500KB |
| Portainer | 无特殊处理 | 依靠 Portainer 自身数据管理 |
| Nextcloud | 回收站/版本 | 由 Nextcloud 自身管理（不在回收体系内） |

**④ 回收**
```bash
# 每周全量清理
docker system prune -f --filter "until=168h"   # 停止>7天的容器
docker image prune -f --filter "dangling=true"  # 悬空镜像
docker volume prune -f                          # 未使用卷（需确认后再开）
docker builder prune -f --filter "until=24h"     # 构建缓存

# 容器日志截断（>100MB 的截到 500KB）
for cid in $(docker ps -q); do
    logpath=$(docker inspect --format='{{.LogPath}}' "$cid")
    [ -f "$logpath" ] && [ $(stat -c%s "$logpath") -gt 104857600 ] && \
        truncate -s 0 "$logpath"
done
```

---

### L5 — 远程连接 (Tailscale)

**① 发现**
```
组件：
  tailscaled       journald 日志
  state            /var/lib/tailscale/
```

**② 分析**

Tailscale 本身很轻量——状态文件固定大小，日志走 journald。
主要积压点在 journald，已由强制回收 F3 覆盖。

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| journald | >200MB | vacuum（强制回收） |
| Tailscale 状态 | N/A | 由 tailscaled 自己管理，不介入 |

**④ 回收**
```bash
# 无额外动作——journald vacuum 已覆盖
# 保留此层作为扩展点：未来如增加 Headscale 自部署，日志策略在此追加
```

---

### L6 — 数据备份

**① 发现**
```
组件：
  每日配置备份    /srv/backups/configs/
  每日数据备份    /srv/backups/data/
  Git 镜像        /srv/backups/git-mirrors/
  session backup  /mnt/data/openclaw/session-backup/
```

**② 分析结构**

| 子组件 | 产出物 | 增长模式 |
|--------|--------|---------|
| configs | daily .tar.gz | +5-20MB/天 |
| data | daily .tar.gz（docker volumes） | +100-500MB/天（取决于容器数据量） |
| git-mirrors | bare repos | git gc 需定期跑 |
| session-backup | context-summary.md + daily-*.md | ~500KB/天 |

**③ 判定规则——分层保留**

| 目标 | 条件 | 动作 |
|------|------|------|
| configs tar | 最近 7 天 | 保留每日 |
| configs tar | 8-30 天 | 保留每周一的那份 |
| configs tar | >30 天 | 删除 |
| data tar | 最近 3 天 | 保留每日 |
| data tar | 4-14 天 | 保留每周日那份 |
| data tar | >14 天 | 删除 |
| git-mirrors | 每月 1 号 | `git gc --aggressive` |
| session-backup | >7 天 | 删除 |

**④ 回收**
```bash
# configs 分层保留
find /srv/backups/configs/ -name "*.tar.gz" -mtime +7 ! -name "*Monday*" ! -name "*Mon*" -delete
find /srv/backups/configs/ -name "*.tar.gz" -mtime +30 -delete

# data 分层保留
find /srv/backups/data/ -name "*.tar.gz" -mtime +3 ! -name "*Sunday*" ! -name "*Sun*" -delete
find /srv/backups/data/ -name "*.tar.gz" -mtime +14 -delete

# git gc
find /srv/backups/git-mirrors/ -name "*.git" -type d -exec git -C {} gc --auto --quiet \;
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

| 子组件 | 产出物 | 特殊性 |
|--------|--------|--------|
| ufw | 防火墙日志 | 正常量小，被攻击时暴增 |
| fail2ban | 封禁日志 | 自动过期（bantime），但日志保留 |
| auditd | 审计轨迹 | **有合规要求，不能随便删** |
| trivy | 扫描缓存 | 每次扫描重新生成，旧缓存可清 |

**③ 判定规则**

| 目标 | 条件 | 动作 |
|------|------|------|
| ufw.log | 轮转文件 >30 天 | 删除 |
| ufw.log | >100MB（异常） | 告警 + 截断到最近 5000 行 |
| fail2ban.log | 轮转文件 >30 天 | 删除 |
| auditd | >30 天 | 归档到 /srv/backups/audit/，然后清理 |
| auditd | 磁盘占用 >1GB | 告警 + 强制归档 |
| trivy cache | 每次扫描后 | 清理（`trivy --clear-cache`） |

**④ 回收**
```bash
# ufw/fail2ban 日志轮转——依赖 logrotate
# /etc/logrotate.d/ufw 和 /etc/logrotate.d/fail2ban 配置：
#   rotate 4
#   weekly
#   compress
#   missingok

# auditd 归档 + 清理
if [ $(du -sm /var/log/audit/ 2>/dev/null | cut -f1) -gt 1024 ]; then
    mkdir -p /srv/backups/audit/
    cp /var/log/audit/audit.log.* /srv/backups/audit/
    # 保留最近 30 天
    find /var/log/audit/ -name "audit.log.*" -mtime +30 -delete
fi

# trivy cache
trivy --clear-cache 2>/dev/null || rm -rf ~/.cache/trivy/
```

---

## 六、执行脚本框架

所有回收逻辑收敛到一个入口脚本 `scripts/mark2-recycle.py`，按层调用：

```
mark2-recycle.py
├─ --mode force         只跑强制回收（事件驱动）
├─ --mode light         强制 + L2/L4 快检（每 15min）
├─ --mode deep          全部 7 层四步法（每 6h）
├─ --mode daily         全部 7 层 + 日报（每天 04:00）
├─ --layer N            只跑某层（调试用）
├─ --dry-run            只分析不执行
└─ --report-out PATH    输出回收日报
```

### 日报格式

```json
{
  "time": "2026-06-16T04:00:00+08:00",
  "mode": "daily",
  "layers": {
    "L1_caddy": {
      "discovered": { "log_files": 12, "total_mb": 340 },
      "recycled": { "deleted_gz": 3, "freed_mb": 210 },
      "issues": []
    },
    "L2_core": {
      "discovered": { "sessions": 45, "dead_sessions": 8, "broker_events": 3200 },
      "recycled": { "deleted_checkpoints": 8, "truncated_broker": 1, "freed_mb": 45 },
      "issues": ["session abc123 trajectory=6.2MB >5MB 阈值"]
    },
    "L4_docker": {
      "discovered": { "images": 18, "dangling": 3, "stopped_containers": 2 },
      "recycled": { "pruned_images": 3, "pruned_containers": 2, "freed_mb": 890 },
      "issues": []
    }
  },
  "total_freed_mb": 1145,
  "warnings": ["auditd /var/log/audit 已达 1.2GB，已自动归档"]
}
```

---

## 七、与现有 Mark1 回收的关系

| Mark1 机制 | Mark2 去向 |
|-----------|-----------|
| lifecycle-maintainer (每 5min) | 迁移到 Mark2，纳入 L2 层智能回收 |
| session-size-watcher (事件 + 每 10min) | 迁移到 Mark2，纳入强制回收 F5 + L2 判定 |
| cleanup-temp.sh | 迁移到 Mark2，纳入强制回收 F1/F7 |
| cleanup-old-audio.sh | 合并到强制回收 F7 |
| scratch-cleanup.py | Mark2 无 /mnt/data/scratch，废弃 |
| memory flush sync | 保留，纳入强制回收 F6 |
| session-backup clean (>7d) | 迁移到 L6 备份回收 |
| journald vacuum | 保留，纳入强制回收 F3 |

---

## 八、部署位置

- **设计文档**：本文件 `docs/贾维斯中枢-Mark2-回收机制设计.md`
- **脚本入口**：`scripts/mark2-recycle.py`（待开发）
- **配置文件**：`config/mark2/recycle.yaml`（各层阈值可调）
- **日报输出**：`~/.local/state/openclaw/recycle/reports/`
- **触发注册**：
  - 事件驱动 hook → `ACTIVE_RULES.md` 事件钩子（收到消息时）
  - 定时深度 → systemd timer（`mark2-recycle-deep.timer`）
  - 每日全量 → systemd timer（`mark2-recycle-daily.timer`）
