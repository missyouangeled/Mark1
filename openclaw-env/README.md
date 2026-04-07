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
   - CLI-Anything 本地仓库 + OpenClaw skill + helper 命令

## 当前恢复包包含什么

- `scripts/pulsenest-preview.sh`
- `scripts/openclaw-resume-watch.sh`
- `openclaw-env/restore-openclaw-env.sh`
- `openclaw-env/restore-skills.sh`
- `openclaw-env/restore-tooling.sh`
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

### 2. 执行恢复脚本

```bash
bash openclaw-env/restore-openclaw-env.sh
```

### 3. 恢复 Skills

```bash
bash openclaw-env/restore-skills.sh
```

### 4. 恢复补充工具层（含 CLI-Anything）

```bash
bash openclaw-env/restore-tooling.sh
```

### 5. 执行恢复检查

```bash
bash openclaw-env/post-restore-check.sh
```

### 6. 手动补私密项

至少检查并补这些：

- GitHub SSH key
- OpenClaw provider 登录态 / token
- `~/.openclaw/openclaw.json` 里的私密字段
- 如需继续使用当前默认模型 / 认证路径：恢复或重新登录当前 provider（这台机器当前默认模型锚点为 `github-copilot/gpt-5.4`）

### 7. 启动 / 验证

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
- `openclaw-env/restore-skills.sh`
- `openclaw-env/restore-tooling.sh`

## openclaw.local.example.json 的用途

这是**不带敏感 token 的配置样板**，用于在新机器上快速对齐：

- 默认模型
- workspace 路径
- hooks/internal 开启项
- browser 配置
- gateway 非敏感偏好
- browser 插件启用状态

不要直接覆盖真实 `~/.openclaw/openclaw.json`，应该人工比对后合并。

## 目标

这套恢复包的目标不是“把旧机器的秘密整个复制过去”，而是：

**把项目、工作上下文、运行脚本和关键环境结构，尽可能稳定地带到新机器。**
