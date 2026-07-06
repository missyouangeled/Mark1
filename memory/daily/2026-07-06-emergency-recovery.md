# 2026-07-06 应急恢复机制（基于上午"上下文污染 + IO 失效"）

> 触发：点点 10:24 提到"上午开发时被污染，IO 都没了"——这与 7/2 那次症状**完全一致**。
> 本文档不是事后报告，是"下次再发生时的应急手册"。

---

## 一、问题不是孤例——是 OpenClaw 一个已知 bug 模式

### 联网 + 内部记忆查到的关键证据

#### 1) 社区/官方已知 bug
- **知乎《警惕！OpenClaw 隐藏的致命 Bug：网络超时误报上下文溢出》**：
  > "OpenClaw 机器人刷屏报错的时间间隔大约是固定的 75 分钟，报错内容是 Context overflow（上下文溢出）/ prompt too large...**网络超时会被误报为上下文溢出**"
  > 临时止血方案：把调用的模型从 OpenClaw/Gemini 切换为直连 SiliconFlow/DeepSeek
- **GitHub Issue #5771**：[Bug]: Context overflow error on fresh sessions
  > 新会话 2-3 消息后就触发 "Context overflow: prompt too large for the model. Try again with less input or a larger-context model."
- **GitHub Issue #100460**：[Bug]: Ollama "stream ended without a final response" errors are **not failover-eligible, causing dead-end failures with no fallback**
  > **这跟我们 ollama 节点不通的情况吻合**——之前的 ollama 配在 providers 里但实际不可达，相当于一个**埋着的地雷**
- **OpenClaw v2026.6.11 Release Notes** 专门做了：
  - "Provider and model recovery"
  - "Restart and readiness recovery"
  → **官方都意识到模型 fallback + 重启恢复 是这一版的重点**
- **lumadock《OpenClaw not working》**：
  > "the failure is rarely obvious, and the error message you get is often misleading or generic"
  > 故障很少明显，错误信息经常误导

#### 2) 我们自己的记忆里**已经踩过两次一模一样**
- **7/2 上午 08:30–09:05**：工具持续被卡，短命令 OK，复杂命令返回 `(see attached image)` 然后挂住；`GatewayDrainingError` 反复出现；最后**等了一会自动恢复**（8:34 → 8:44）
- **5/22 上午 11:34**：`session file locked (timeout 60000ms)` 僵尸锁——compaction 超时后锁没释放
- **5/26 上午 10:42**：`sessions.json` 死引用导致脚本挂
- **6/4–6/9**：文件在外挂盘被 sandbox 限制、读不到
- **5/13 上午**：Windows 宿主机温度读取（独立事故，已记 CASE-20260513-001）

#### 3) 上午 10:14 这次（点点说的"上午被污染"）
- 之前对话里**没有更早的具体日志**（daily 是 10:14 才有新内容），所以**根因现场已经过去了**
- 但症状**与 7/2 完全同型**："工具持续被一个未知 bug 卡住 / 短命令正常 / 复杂命令挂住"
- 现在系统是稳的——10:14 之后所有维护动作都成功了

---

## 二、根因总结（基于所有证据）

OpenClaw 工具/IO 失效的**常见根因排序**（按发生概率）：

| # | 根因 | 症状 | 检测方法 |
|---|---|---|---|
| 1 | **网络超时被误报为上下文溢出**（知乎 bug） | 模型报"prompt too large"但实际是网络 | 看 gateway 日志的时间戳；正常 context overflow 不会瞬时出现 |
| 2 | **主会话 jsonl/trajectory 过大**（7/2 教训） | compaction 超时 → 锁没释放 → 新消息写不进去 | `ls -la ~/.openclaw/agents/main/sessions/*.jsonl` |
| 3 | **sessions.json 死引用**（5/26 教训） | 重启后某些任务找不到 backing session | `openclaw tasks audit --json` |
| 4 | **GatewayDrainingError 残留**（7/2 教训） | gateway 重启后某些 task 一直处于 draining 状态 | `openclaw tasks list` 看 lost/failed 任务 |
| 5 | **Ollama 不可达但配在 providers**（GitHub #100460） | fallback 链里 ollama 挂了 → 主模型挂了直接 dead-end | `curl http://<ollama>:11434/api/tags` |
| 6 | **session file lock 卡住**（5/22 教训） | compaction 超时后没释放 | `fuser <session>.jsonl.lock` |
| 7 | **图片上传 stub 干扰**（7/2 教训） | exec 总是返回 `(see attached image)` | 看 chat transcript |

---

## 三、紧急恢复机制（4 级，按侵入度从小到大）

### 🚨 第 0 级：先冷静，看 1 分钟

> **不要立刻重启**。90% 的情况能自动恢复（7/2 经验：等 10-20 分钟就没事了）。

**1 分钟观察**：
1. 看一下主会话 jsonl 大小（决定走哪条路）
2. 看一下是不是只有当前 session 有问题（开新 session 试试）
3. 看一下 gateway 日志（找 `GatewayDrainingError` / `context overflow` / `stream ended`）

```bash
# 看主会话 jsonl 大小
ls -la ~/.openclaw/agents/main/sessions/*.jsonl | sort -k5 -rn | head -3

# 看 gateway 日志
ls -t /tmp/openclaw/openclaw-*.log 2>/dev/null | head -1 | xargs tail -50 2>/dev/null

# 看残留任务
openclaw tasks list 2>&1 | grep -E "lost|failed" | head -10
```

### 🔧 第 1 级：清缓存（不重启，最小代价）

**适用**：工具偶发卡、单个 session 出问题、Gateway 健康但子功能死。

```bash
# 1. 清理内核页缓存
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches 2>/dev/null || true

# 2. 清 journald 日志
journalctl --vacuum-size=50M

# 3. 清 Python __pycache__
find /home/missyouangeled/.openclaw/workspace -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null

# 4. 清 /tmp 旧文件（保留最近 7 天）
find /tmp -type f -mtime +7 -delete 2>/dev/null

# 5. 清 sessions.json 死引用（不会动还在用的 session）
openclaw tasks audit --json  # 先看一遍
# 手动清 14 条 lost/failed 历史残留
```

**7/2 那次实测效果**：清完 14 条残留任务后，`reply session initialization conflicted` 报错消失。

### 🛠️ 第 2 级：reset 当前 session（保留 gateway 进程）

**适用**：主 session jsonl 过大（>500KB）、compaction 卡了、单一 session 锁住。

**绝对不能从 main session 自己内部执行重启**（看 CASE-20260706-003）！需要：
- 选项 A：让点点从外部终端跑
- 选项 B：在 isolated subagent 里跑（不杀自己）
- 选项 C：用 cron job 触发（5 分钟后跑）

```bash
# 从外部终端跑（点点手动）
cd ~/.openclaw/workspace

# 1. 看哪些 session jsonl 太大
ls -la ~/.openclaw/agents/main/sessions/*.jsonl | sort -k5 -rn | head -3

# 2. 如果某个 jsonl > 1MB，备份后截断（保留最近 50 行）
SESSION_ID="<id>"  # 替换成过大的那个
LOCKFILE="$HOME/.openclaw/agents/main/sessions/$SESSION_ID.jsonl.lock"
FILE="$HOME/.openclaw/agents/main/sessions/$SESSION_ID.jsonl"

# 检查锁
fuser "$LOCKFILE" 2>/dev/null || echo "锁空闲"

# 备份 + 截断
cp "$FILE" "$FILE.bak.$(date +%Y%m%d-%H%M)"
tail -50 "$FILE" > /tmp/session-tail.jsonl
mv /tmp/session-tail.jsonl "$FILE"

# 3. 删 lock（只有 fuser 找不到持有者时）
rm -f "$LOCKFILE"
```

**⚠️ 重启 gateway 之前必读 CASE-20260706-003**！

### 💀 第 3 级：硬重启（最后手段）

**适用**：gateway 进程死、整个系统无响应、所有 session 都不可用。

```bash
# 1. 通知当前 session
echo "System going down for maintenance. Please save your work."

# 2. 优雅停 gateway
systemctl --user stop openclaw-gateway

# 3. 必要时清死锁
find ~/.openclaw/agents/main/sessions -name "*.lock" -mmin +5 -delete 2>/dev/null

# 4. 拉起
systemctl --user start openclaw-gateway
sleep 5

# 5. 验证
systemctl --user status openclaw-gateway
openclaw status --deep
```

---

## 四、预防机制（已经在跑的部分）

✅ **已经在跑**：
- Mark42 上下文铠甲（5 分钟一次检查）
- 循环引擎 `context-guard`（监控上下文健康）
- 循环引擎 `model-fallback`（健康检查 + 兜底）
- 循环引擎 `memory-index`（记忆索引）
- 循环引擎 `health-watch`（系统健康）
- 早安/午餐 cron 提醒
- 数据盘快照（每 30 分钟一次，336 份）

✅ **今天刚加的兜底**（10:14 那次维护）：
- cron timeout 90s → **180s**
- cron fallback → **`litellm/agnes-2.0-flash`**（真可达）
- 全局模型 fallback 链 → **3 段**（MiniMax-M3 → agnes-2.0-flash → M2.5）

⚠️ **还没补的隐患**（建议下次体检一并解决）：
1. ollama 节点 `192.168.18.13` 不可达但还配在 providers 里——`config get models.providers.ollama` 还显示。建议清掉或禁用，否则会成为"埋着的地雷"（GitHub #100460 同型 bug）
2. 7/2 那次症状的**真根因没找到**——只是等过去了。下次应该抓 gateway 日志里的 traceback，定位到具体是哪个 timeout 触发的。
3. 缺一个**自动检测 + 自动恢复**的 hook——比如检测到 exec 连续 3 次返回 `(see attached image)` 时自动清缓存、reset session、发告警。

---

## 五、给点点的"应急速查卡"

把这一段存手机里，下次出问题直接照做：

```
🚨 OpenClaw 工具/IO 失效应急卡

1️⃣ 等 1 分钟（90% 自动恢复）
   - 看主会话 jsonl: ls -la ~/.openclaw/agents/main/sessions/*.jsonl | sort -k5 -rn | head -3
   - 看残留任务: openclaw tasks list | grep -E "lost|failed"

2️⃣ 清缓存（不重启）
   - sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
   - find ~/.openclaw/workspace -name __pycache__ -type d -exec rm -rf {} +
   - 清 14 条历史残留任务

3️⃣ reset 当前 session（保留 gateway）
   ⚠️ 不要从 main session 内部跑！必须从外部终端
   - 备份大 jsonl
   - tail -50 截断
   - 删僵尸 lock

4️⃣ 硬重启（最后手段）
   - systemctl --user restart openclaw-gateway
   - 必先读 CASE-20260706-003（重启会打断主会话）
   - 重启后跑 openclaw status --deep 验证
```

---

## 六、记忆留档

- 落档：`memory/daily/2026-07-06-emergency-recovery.md`（本文）
- 案例库：今天的 7/2 同型 bug 没新写崩案例（**因为根因没新发现**），等下次再发生时抓日志定位
- TODO：开一个"应急工具包"skill，把这套流程固化成可调用的命令
