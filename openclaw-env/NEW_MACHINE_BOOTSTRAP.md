# 新机器恢复 SOP

目标：在一台新机器上，把 **纳达尔星项目 / 星云初始03** 的项目代码、工作日志、版本锚点，以及可恢复的 OpenClaw 环境结构尽量完整接回来。

## 你对贾维斯说的话

在新机器的主会话里，直接说：

**恢复 星云初始03全量工作备份，并应用环境全量恢复包**

## 人工前置条件

以下几样还需要你自己准备：

- GitHub SSH key 或 HTTPS 凭据
- OpenClaw provider 登录态 / token
- 新机器已经安装：
  - `git`
  - `node`
  - `npm`
  - `php`
  - `systemd --user`
- 你自己的 OpenClaw 已初始化过一次

## 建议执行顺序

### 1. 拉取仓库

```bash
mkdir -p ~/.openclaw
cd ~/.openclaw
git clone git@github.com:missyouangeled/test-git.git workspace
cd ~/.openclaw/workspace
```

### 2. 执行环境恢复脚本

```bash
bash openclaw-env/restore-openclaw-env.sh
```

### 3. 恢复 Skills

```bash
bash openclaw-env/restore-skills.sh
```

### 4. 恢复补充工具层（含 CLI-Anything / QMD）

```bash
bash openclaw-env/restore-tooling.sh
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
```

### 5. 检查依赖、路径、QMD 运行态

```bash
bash openclaw-env/post-restore-check.sh
bash openclaw-env/qmd-agent-status.sh main
```

### 6. 合并 OpenClaw 配置样板

参考：

- `openclaw-env/openclaw.local.example.json`

把里面的非敏感配置手动合并进：

- `~/.openclaw/openclaw.json`

注意：
不要直接覆盖真实配置，尤其是：
- token
- paired devices
- identity
- private auth fields

### 7. 恢复 hooks / 服务

```bash
systemctl --user daemon-reload
systemctl --user enable --now pulsenest-preview.service
systemctl --user enable --now openclaw-resume-watch.timer
openclaw hooks enable self-improvement
```

### 8. 验证

```bash
systemctl --user status pulsenest-preview.service
systemctl --user status openclaw-resume-watch.timer
openclaw gateway status
```

然后打开：

- `http://127.0.0.1:8093/`

如果本机允许局域网访问，再看你的本机 IP 对应地址。

## 恢复后你应该看到什么

- `pulsenest-php/` 项目代码存在
- `PROJECT_VERSIONS.md` 里 `星云初始03` 指向当前成熟版
- `memory/*.md` 和 `.learnings/*.md` 在仓库中可见
- `pulsenest-preview.service` 已可启动
- `openclaw-resume-watch.timer` 已可启动
- `restore-skills.sh` 可以按清单恢复 Skills
- `restore-tooling.sh` 可以恢复 CLI-Anything 本地仓库、OpenClaw skill、`cli-anything` helper 命令，以及 gateway 的 QMD CPU-only / hf-mirror drop-in
- `qmd-agent-status.sh` 可以看到 agent-scoped QMD 索引和 gateway QMD env 是否真正生效

## 仍然需要手动处理的内容

- SSH key / `ssh-agent`
- GitHub provider 登录态
- OpenClaw credentials
- 设备配对信息
- 浏览器 profile / 本机软件安装路径差异
- 当前默认模型 / provider 登录态（本机当前锚点：`github-copilot/gpt-5.4`）

## 一句话理解

这套 SOP 的目标是：

**把“项目 + 工作记忆 + 可跟仓库走的环境结构”一口气接回来。**

补充说明：QMD 默认仍应保持 search-only 稳态；如果以后要恢复 embedding / rerank，先运行：

```bash
bash openclaw-env/qmd-prefetch-models-via-mirror.sh check all
```
