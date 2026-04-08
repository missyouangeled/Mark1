# OpenClaw 环境全量恢复包

这套恢复包用于把**当前纳达尔星项目 + 关键 OpenClaw 环境约定**带到另一台新机器。

## 一句话恢复口令

在另一台新装好的 OpenClaw 上，你可以对贾维斯说：

**恢复 星云初始03全量工作备份，并应用环境全量恢复包**

如果你这次是“升级 OpenClaw 以后恢复”，也可以直接说：

**按星云初始03环境全量恢复包恢复到我现在这台机器的状态**

这句话的目标语义是：

1. 拉取当前 GitHub 仓库最新代码
2. 以 `星云初始03` 为主锚点恢复项目和工作日志
3. 应用仓库内可恢复的环境层：
   - OpenClaw 工作区文件
   - 预览服务脚本
   - 休眠恢复脚本
   - user systemd 单元模板
   - OpenClaw 配置样板
   - Skills 恢复清单
   - `self-improving-agent` 的本仓 overlay（避免只在本机热改后丢失）
   - CLI-Anything 本地仓库 + OpenClaw skill + helper 命令
   - QMD 安装与 OpenClaw QMD memory backend 配置
   - gateway 的 QMD CPU-only / hf-mirror service drop-in
   - QMD 运行态检查脚本与镜像预热脚本

## 当前恢复包包含什么

- `scripts/pulsenest-preview.sh`
- `scripts/openclaw-resume-watch.sh`
- `openclaw-env/restore-openclaw-env.sh`
- `openclaw-env/restore-skills.sh`
- `openclaw-env/skill-overlays/self-improving-agent/`
- `openclaw-env/restore-tooling.sh`
- QMD（`@tobilu/qmd`）全局安装与 OpenClaw memory backend 样板配置
- gateway QMD service drop-in：
  - `openclaw-env/templates/openclaw-gateway.qmd-cpu.conf`
  - `openclaw-env/templates/openclaw-gateway.qmd-hf-mirror.conf`
- `openclaw-env/qmd-agent-status.sh`
- `openclaw-env/qmd-prefetch-models-via-mirror.sh`
- `openclaw-env/templates/*.service`
- `openclaw-env/templates/*.timer`
- `openclaw-env/templates/cli-anything-helper.sh`
- `openclaw-env/openclaw.local.example.json`
- Git 仓库中的：
  - `pulsenest-php/`
  - `PROJECT_VERSIONS.md`
  - `HANDOFF.md`
  - `memory/*.md`
  - `.learnings/*.md`
  - `skills/`（已进仓的部分）

## 当前恢复包不包含什么

这些不会自动随 GitHub 恢复，需要新机器单独补：

- `~/.ssh/` 私钥、GitHub SSH key、ssh-agent 状态
- `~/.openclaw/credentials/` 下的 provider token
- `~/.openclaw/openclaw.json` 中的真实网关 token / 私密字段
- 已配对设备信息
- 本机安装的软件本身（如 php、node、git、chrome）
- 本机 systemd 当前运行态

## 推荐恢复流程

### 1. 拉仓库

```bash
git clone <你的仓库地址> ~/.openclaw/workspace
cd ~/.openclaw/workspace
```

### 2. 恢复 Skills（先把 workspace skill 本体和 overlay 补齐）

```bash
bash openclaw-env/restore-skills.sh
```

### 3. 执行恢复脚本（会安装 self-improvement hook、tool-error plugin，并补齐 `.learnings/`）

```bash
bash openclaw-env/restore-openclaw-env.sh
```

### 4. 恢复补充工具层（含 CLI-Anything 与 QMD）

```bash
bash openclaw-env/restore-tooling.sh
```

说明：当前恢复样板会优先把 QMD 配成**本地稳定模式**——`searchMode=search`、`embedInterval=0`，并同步写入 gateway 的两个 service drop-in：

- `QMD_LLAMA_GPU=false`（固定 CPU-only）
- `HF_ENDPOINT=https://hf-mirror.com`

### 5. 让 gateway 重新吃到新环境

```bash
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
```

### 6. 执行恢复检查

```bash
bash openclaw-env/post-restore-check.sh
bash openclaw-env/qmd-agent-status.sh main
```

### 7. 手动补私密项

至少检查并补这些：

- GitHub SSH key
- OpenClaw provider 登录态 / token
- `~/.openclaw/openclaw.json` 里的私密字段
- 如需继续使用当前默认模型 / 认证路径：恢复或重新登录当前 provider（这台机器当前默认模型锚点为 `github-copilot/gpt-5.4`）

### 8. 启动 / 验证

```bash
systemctl --user daemon-reload
systemctl --user enable --now pulsenest-preview.service
systemctl --user enable --now openclaw-resume-watch.timer
systemctl --user status pulsenest-preview.service
systemctl --user status openclaw-resume-watch.timer
openclaw gateway status
```

另见：
- `openclaw-env/QUICK_RECOVERY.md`
- `openclaw-env/NEW_MACHINE_BOOTSTRAP.md`
- `openclaw-env/secrets-checklist.example.md`
- `openclaw-env/skills-manifest.json`
- `openclaw-env/skill-overlays/self-improving-agent/`
- `openclaw-env/restore-skills.sh`
- `openclaw-env/restore-tooling.sh`
- `openclaw-env/qmd-agent-status.sh`
- `openclaw-env/qmd-prefetch-models-via-mirror.sh`

## openclaw.local.example.json 的用途

这是**不带敏感 token 的配置样板**，用于在新机器上快速对齐：

- 默认模型
- workspace 路径
- hooks/internal 开启项
- memory / QMD 后端样板配置（默认按本地稳定模式：search-only + no scheduled embed）
- browser 配置
- gateway 非敏感偏好
- browser 插件启用状态

不要直接覆盖真实 `~/.openclaw/openclaw.json`，应该人工比对后合并。

## 当前 QMD 收口结论（2026-04-08）

### 1) 稳定默认

当前默认建议继续保持：

- `memory.backend = qmd`
- `memory.qmd.searchMode = search`
- `memory.qmd.update.embedInterval = 0`
- gateway service env：
  - `QMD_LLAMA_GPU=false`
  - `HF_ENDPOINT=https://hf-mirror.com`

这套组合的目标不是追求向量能力，而是先把 **本地 BM25 / 关键词检索稳定跑通**。

### 2) 现在已经验证到哪一步

已经验证：

- OpenClaw 配置层已切到 `backend=qmd`
- gateway 运行态确实带上了 `QMD_LLAMA_GPU=false` 与 `HF_ENDPOINT=https://hf-mirror.com`
- agent-scoped QMD 索引已经存在，并能直接用 `qmd search` 命中工作区里的记忆 / 说明文档
- 由于 QMD scope 配置只允许 `chatType=direct`，**主会话直聊**应该使用 QMD；而 **subagent / 非 direct 场景** 看到 `qmd search denied by scope` 属于设计内行为，不算故障

### 3) 为什么暂时不恢复 embedding / rerank

当前不建议直接恢复 embedding / rerank，原因不是 CPU-only 本身，而是：

- QMD 2.1.0 的部分下载路径仍写死 `https://huggingface.co/...`
- 也就是说，哪怕 gateway service 已经带上 `HF_ENDPOINT=https://hf-mirror.com`，**这也不足以保证 QMD 默认模型下载自动改走镜像**
- 实测 `hf-mirror.com` 本身可达，默认三类模型 URL 也可直取，但 QMD 默认下载逻辑并未完全跟随这个变量
- 因此，当前最稳的策略仍是：**search-only 默认不动；高级模型单独预热；确认缓存就位后再谨慎开启**

### 4) 如果以后想谨慎恢复高级能力

先做这条路线，而不是直接改默认模式：

```bash
bash openclaw-env/qmd-prefetch-models-via-mirror.sh check all
bash openclaw-env/qmd-prefetch-models-via-mirror.sh download embed
# 如需更进一步，再考虑 rerank / expand
bash openclaw-env/qmd-agent-status.sh main
```

等 `~/.cache/qmd/models/` 里对应 GGUF 文件齐了，再评估是否临时恢复：

- `vsearch`（先只测 embedding）
- `query --no-rerank`（再测扩展链路）
- 完整 rerank（最后再开）

不要把高级模式直接设成默认启动项。

## 目标

这套恢复包的目标不是“把旧机器的秘密整个复制过去”，而是：

**把项目、工作上下文、运行脚本和关键环境结构，尽可能稳定地带到新机器。**
