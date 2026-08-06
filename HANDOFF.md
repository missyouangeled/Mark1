# HANDOFF.md — 跨模型/跨会话接力地图

> 最后更新: 2026-08-06 09:18 CST
> 当前会话: 贾维斯主会话 (volcengine-agent/ark-code-latest)
> 状态: ✅ 早间全部任务闭环，无阻塞待办

---

## ⏳ 待接力的第一件事

**无阻塞项。** 上一轮的「gateway 需重启」已由点点于 09:10:50 执行完毕并验收通过。

下次开机后建议复查一件事（非阻塞）：
- `OnStartupSec` 方案目前只验证过 **restart** 场景，尚未验证**冷启动**（真正关机再开机）场景。
  开机后跑一次 `systemctl --user list-timers --all | grep -E "openclaw-|mark42-"`，确认 8 个 timer 的 NEXT 列都有值、没有 `-`。

---

## ✅ 本轮完成（2026-08-06 早间 07:35-09:18）

> 详细过程见 `memory/daily/2026-08-06.md`，变更留痕见 `docs/通用-OpenClaw-补丁变更流水.md`。

### 起因：点点问「有没有每天读启动项」

真问题不是漏读，是**启动链里的必读文件本身过期**：HANDOFF 停在 6-10、`docs/模型使用说明.md` 停在 6-15。实际配置 / MEMORY.md / 模型使用说明三方共 **5 处**不一致 —— 每天照着互相打脸的三套路由表走，还以为守了规矩。

### 1. 模型路由按实测校正

| 项 | 现状（已落地并重启生效） |
|---|---|
| 主会话 / 子 agent | `volcengine-agent/glm-5.2` |
| fallback | `litellm/agnes-2.5-flash`（走国内址 `api.agnes-ai.cn`） |
| **compaction / memoryFlush** | **`volcengine-agent/doubao-seed-2.0-pro`** |
| 图片识别 | `volcengine-agent/doubao-seed-2.0-pro` |
| 图生（工具配置） | `litellm/agnes-image-2.1-flash`（~50% 可用，备用） |
| 图生（实际路径） | `scripts/doubao-image-gen.py` HTTP 直调 seedream |

关键实测：老端点 `apihub.agnes-ai.com` 解析到 Teredo 保留段、**彻底不可路由**（HTTP 000 / 12s）；国内址 200 / 0.47s。

### 2. compaction 换豆包 —— 修静默丢数据隐患

agnes-2.0-flash HTTP 200 却 `content` 为空、token 全烧 reasoning。挂在 compaction 上意味着**压缩结果为空、上下文静默丢失且不报错**。

选型走实测，不按参数猜：**glm-5.2 在 ≤512 预算下四档全 `finish=length`、三档正文完全为空**，同一形态，不可用。豆包 128 起稳定 `stop`；用配置里**真实的 memoryFlush prompt** + 23478 token 上下文复测，正确输出 `edit`/`read` 工具调用。

### 3. 图生撞版本能力边界 → 回滚（CASE-20260806-016）

OpenClaw 图生按 provider **名字**查内置适配器表，只支持 openai/fal/google/minimax/xai/litellm/openrouter/deepinfra/comfy。`volcengine-agent` 不在表内，`config validate` 通过但工具 100% 不可用。已回滚（成功率从被我改坏的 0% 恢复到 ~50%）+ 建 HTTP 脚本兜底。

### 4. ⭐ 两个监控 timer 停摆 12 小时 → 根治（CASE-20260806-017）

`frontstage-guardian` / `health-collector` 显示 `enabled` + `active`，但 `list-timers` 的 NEXT 为 `-`，自 08-05 17:54 完全停摆。**前台假死检测 + CPU 过载响应两道防线空置。**

根因（`man systemd.timer` 证实）：user 级 timer 用了 `OnBootSec`（相对开机），而官方明确指出 user manager「通常在首次登录时才启动」。实测开机 +86s 起 manager、+94s 起 timer，而 `OnBootSec=90s` 的触发点 +90s 已过去 4 秒 → 触发被跳过 → `Persistent` 无 `OnCalendar` 故无效 → `OnUnitActiveSec` 永无锚点 → **永久卡死**。

**清点发现 9 个 timer 全部同一缺陷**，今天没死的只是余量 34-94 秒赶上了，**其中含 `mark42-watchdog`（自愈机制本身）**。已用三重保障（`OnStartupSec` + `OnUnitActiveSec` + `OnCalendar`）统一加固，脚本 `scripts/harden-user-timers.sh`（默认 dry-run）。

验收：两 service 各执行 **16 次**、稳定 60-70s 间隔；**8 个 timer 全绿 0 个无 NEXT**；点点 09:10 重启后复验仍全绿（这次重启顺带成了修复方案的真实压力测试）。

### 5. Mark42 巡检 + 清掉我 8-05 引入的债

巡检健康：1975 测试 0 失败 / ruff 全过 / mypy 0 issues / v2.8.2 / 5 Loop 全 registered / 铠甲 4.4%。

清掉自己昨天引入的 2 个 ruff 退化。其中 `F841` 死变量**盖着一个真 bug**：注释写着「构建时验证源文件真存在」但校验根本没写 —— 源码被移走会生成死链且不报错。已补上校验并反向验证（故意指向不存在目录 → 70 个模块全部报警）。

---

## 🔴 本轮方法论教训（四条同源 + 一条独立）

> 共性：**比较/验证的两端不同源、不同口径，或采样时机错。**

1. `stat` 文件字节数 vs Python `len()` 字符数 → 中文 UTF-8 占 3 字节，误判文件变小
2. `config get` 读磁盘 vs 进程内存 → 误判配置已生效
3. **`config validate` 校验格式 vs 运行时能力** → 误判功能可用（最隐蔽，每步都给绿灯）
4. 单点采样瞬时 `SubState` vs 连续观察执行次数 → 把正常中间态误判为故障（**我为此向点点报告过一次错结论**）

**独立一条**：`is-active` / `is-enabled` 全绿 **≠** 会工作。今日 08:03 心跳记的「11 timer 全 active」就是这样的假绿灯 —— 那两个死掉的 timer 当时就在这 11 个里面。

---

## 📌 新增硬规矩

> **但凡涉及系统工具 / provider / capability，动手前先确认当前版本支持不支持。**
> 顺序：官方文档 `docs/providers/` → 源码内置适配器表 → 才动配置。
> `config validate` 通过不算验收，**实际调用一次工具成功**才算。

已写入 `rules/agents-core.md` 修改类任务流程**第 1.5 步**（不只躺在案例库里等人想起来查）。

---

## 📋 仍待做

### 非阻塞
1. `mark42-pkg/docs/devportal/generate_fulltext.py` 剩 8 个 ruff 错误（F541/I001/UP032），`e214bd85` 入库时带进来的既有技术债，8 个均可 `--fix`。按「没坏别修」等指示
2. 下次**冷启动**后复查 8 个 timer 的 NEXT（见文首）
3. `openclaw-session-size-watcher` 自 7-27 起是 `disabled` 状态，需确认是有意停用还是遗漏
4. 根盘 75% 持续关注
5. 专项治理「grep 源码当契约」与「mock 掩盖签名」两类测试债（8-05 继承）

### 长期继承
- **配新机器（GTX 1070）**：需先确认系统/网络/OpenClaw 安装状态。可能用途：本地 TTS 推理，减轻主机 CPU 压力

---

## 📍 关键文件位置速查

| 用途 | 路径 |
|------|------|
| 配置备份（本轮两次） | `~/.openclaw/openclaw.json.bak-20260806-075354` / `-085830` |
| systemd 备份（本轮两次） | `tmp/systemd-backup-20260806-084530` / `-090608` |
| **timer 加固脚本** | `scripts/harden-user-timers.sh`（默认 dry-run，`--apply` 才写） |
| **图生实际入口** | `scripts/doubao-image-gen.py "提示词" [文件名]` |
| compaction 选型探针 | `tmp/probe-compaction-real.py` / `probe-compaction-edge.py` |
| 变更流水 | `docs/通用-OpenClaw-补丁变更流水.md` |
| 崩坏案例 | `docs/对系统操作必须要参考的崩坏案例.md`（今日新增 016 / 017） |
| 模型使用说明 | `docs/模型使用说明.md`（已重写，含改配置标准动作） |
| 安装注册表 | `docs/install-registry.md` |

---

## 🔎 本轮学到的排查姿势（省下猜的时间）

```bash
# 配置字段合法性（只解决格式，不解决能力）
openclaw config schema

# 某能力支持哪些 provider（源码最权威）
grep -rn "No image-generation provider registered" ~/.npm-global/lib/node_modules/openclaw/dist/

# 配置改动是否被热重载（看字段在不在 applied 列表）
journalctl --user -u openclaw-gateway | grep '\[reload\]'

# 周期任务健康：数执行次数，不看瞬时状态
journalctl --user -u <unit> --since "HH:MM" | grep -c Starting
systemctl --user list-timers --all   # NEXT 列为 - 即永不触发
```

provider models 数组合法字段（`additionalProperties: False`，多写即非法）：
`agentRuntime, api, baseUrl, compat, contextTokens, contextWindow, cost, headers, id, input, maxTokens, mediaInput, metadataSource, name, params, reasoning, thinkingLevelMap`
required：**仅 `id` + `name`**（`output` 不是合法字段）

