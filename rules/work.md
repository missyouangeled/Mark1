# 工作执行规则

> 适用机器：通用
> 系统 / OS：通用

---

## 1. 修改类任务默认流程

工程类修改/修补/打补丁/新建项目时，遵循五阶段流程，详见 `docs/methodology/superpowers-adapted.md`：

- 脑暴设计 → 任务拆解 → 分身执行 → 验证闭环 → 收尾清理

具体执行时按以下三步展开：

### 第一步：先查现有能力
- 检查当前仓库是否已有类似功能、脚本、补丁、配置、systemd/service/timer、文档入口
- 禁止一上来就另起一套平行实现

### 第二步：检查冲突与边界
- 检查本次改动与既有功能、旧逻辑、已有补丁链路、自动触发链路之间有无冲突或互相覆盖
- 发现冲突、边界不清、只能临时生效时必须先向用户短反馈，再给解决方案

### 第三步：改完接成正式可重复链路
- 结果不能只在当前会话临时有效
- 默认接入可重复应用或自动触发链路，保证刷新、换主会话、换模型、重启、更新后仍生效
- 若上游大版本结构变化可能导致补丁失效，明确记成维护边界，但仍需接好当前可重复应用方案
- 落点记入对应文档/记忆/learnings

---

## 2. 补丁与变更流水

每次实际改功能/补丁/脚本/自动链路/维护文档后，必须同步留痕，不要只散落在聊天里。

### 变更流水
- 追加到 `docs/通用-OpenClaw-补丁变更流水.md`
- 优先使用脚本：`python3 scripts/openclaw-change-log.py capture --title '...' --kind patch --scope ... --summary '...' --verify '...'`

### 正式补丁
- 还要同步更新：`docs/通用-OpenClaw-补丁注册表.md`、`docs/通用-OpenClaw-补丁重建清单.md`
- 必要时更新 `docs/通用-OpenClaw-升级后自检清单.md`

### 非正式但重要的修改
- 记入 `docs/通用-OpenClaw-非正式修改备忘录.md`
- 使用脚本：`python3 scripts/openclaw-change-log.py memo --title '...' --kind manual-fix ...`

---

## 3. Git / GitHub 管理

- 每次做完系统性修改后，及时 `git commit` 并 `git push` 到 GitHub
- "同步这台机器" / "更新这台机器" / "拉一下最新规则" = `git pull --ff-only`，必要时 `openclaw gateway restart`
- Git 工作区污染规则参见 `docs/通用-OpenClaw-Git工作区污染规则.md`：系统补丁提交、记忆/学习整理、运行态/临时文件分开处理

---

## 4. 方案、系统维护、日常记录三者分离

- **方案** → `PLANS.md`
- **系统配置 / 维护内容** → `docs/`、`TOOLS.md`、脚本说明
- **日常记录** → `memory/daily/`
- 三者绝对分开，不互相代替或互相干涉
- 机器相关文档须标注 `适用机器` 和 `系统/OS`

---

## 5. 项目索引

- 新项目登记到 `PROJECT_INDEX.md`
- 提到项目时先查 `PROJECT_INDEX.md`
- 项目改名/搬家/获得常用别名时更新 `PROJECT_INDEX.md`

---

## 6. 大批量操作

详细规则见 `docs/通用-大批量操作防上下文溢出规则.md`。

- 动手前先判断文件/条目总量
- ≤50 条：聊天里直接列全
- 50~200 条：精简展示，只给分类计数 + 代表性样本（每类 2-3 个）
- >200 条：必须分批，每批≤200，聊天只放摘要和计数，详细内容落地文件
- 长时间任务用 `sessions_spawn` 卸到后台分身

---

## 7. 上下文溢出自律规则（Layer 3）

> 配合 `scripts/openclaw-context-monitor.py`（Layer 2）使用。
> 监控阈值：WARN=70% / ALERT=85% / CRIT=95%。

### 工具循环中的 token 自律

当以下任一条件满足时，应主动收紧工具调用策略：

- 单轮工具循环已消耗超过 20K tokens
- 会话上下文使用率超过 80%（从 session_status 估算）
- 收到 context-monitor 的 ALERT 级别事件

**收紧措施**：
1. 停止读取大文件全文，改用 `offset/limit` 分段读取
2. 长工具输出做结构化摘要后再传递给下一步
3. 将中间结果落盘到 `tmp/`，后续步骤读文件而非把全文堆在上下文
4. 必要时主动建议用户 `/compact` 或 `/reset`

### 上下文健康度自检

当同一会话内累积多次操作后，主动检查：

1. 本轮对话是否已包含大量文件列表或预览输出？
2. 是否接近模型上下文上限？
3. 如果是 → 建议开 `/new` 新会话继续，所有成果已在文件中，新会话可无缝衔接

### 与大工程方案的关系

本规则为「每轮工具调用的 token 自律」层。
大工程的整体任务拆分、后台化、scratch 管理仍遵循 `docs/通用-OpenClaw-大工程稳定运行方案.md`。

---

## 9. 视频平台下载工作流

优先使用 `scripts/download-platform-video.py`。

- 已知公开视频页 URL → 直接用它下载并 ffprobe 校验
- 站内搜索被验证码/登录墙拦截 → 立即切外部搜索/公开页面定位候选
- 目标位不写死，使用 `--pick first|last|random|index:N|video:<id>`
- 作者主页作品流异常（如"服务异常，重新刷新拉取数据"）→ 明确报阻塞，不误选热点/推荐视频
- 拿不到稳定下载结果时先做候选整理：`python3 scripts/download-platform-video.py --list-only --pick=first --candidates-out ... --report-out ...`
- 下载前做容量预检，下载后做文件存在 + `ffprobe` 校验

---

## 10. 硬件适配审查

当被问"某个工具/方案能不能用/能不能装"时：

- 必须先查：CPU / GPU / VRAM / RAM / 磁盘 / 网络 / API key / 依赖链
- 结合已有运行规则与偏好，再给出结论
- 禁止不查就断言

---

## 11. 升级流程

- 准备升级前，先读 `docs/通用-OpenClaw-升级记录.md`（回顾历史问题和经验教训）
- 升级后首次启动，`BOOT.md` 配置为检测到版本变化时自动先读升级记录
- 升级后修复完成，追加新记录到 `docs/通用-OpenClaw-升级记录.md`
- 升级后自检入口：`docs/通用-OpenClaw-升级后自检清单.md`
- 自检脚本：`python3 scripts/openclaw-post-upgrade-self-check.py --print-human`

---

## 12. 收尾清理

每轮任务做完后默认做收尾清理：

- 关闭没有任务的分身
- 取消/维护卡死或陈旧后台任务
- 按保留规则清理无用旧会话
- 清理规则以稳为先：保留当前会话树（当前会话及其父 dashboard）+ 主会话，优先清陈旧 dashboard、已结束/失败/超时/僵尸 running 的 subagent、旧直聊会话
