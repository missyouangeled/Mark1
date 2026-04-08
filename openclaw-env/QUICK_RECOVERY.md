# 星云初始03 · 快速恢复小抄

## 一句话恢复口令（推荐）

升级 OpenClaw、换机器、或恢复环境后，直接对贾维斯说：

**按星云初始03环境全量恢复包，把我恢复到升级前这台机器的状态。**

如果你想把“项目代码 + 工作日志 + 环境”都说得更明确，可以用加长版：

**恢复星云初始03全量工作备份，并应用环境全量恢复包，把我恢复到升级前这台机器的状态。**

---

## 这句话默认要恢复什么

- 纳达尔星项目代码（`pulsenest-php/`）
- `PROJECT_VERSIONS.md`
- `HANDOFF.md`
- `memory/*.md`
- `.learnings/*.md`
- OpenClaw 环境脚本与模板
- Skills 恢复清单
- `self-improving-agent` 的本仓 overlay + proactive self-improvement hook
- CLI-Anything 本地仓库 / OpenClaw skill / helper 命令
- 当前环境锚点信息（含默认模型参考：`github-copilot/gpt-5.4`）

---

## 恢复后检查指令（手动跑）

```bash
bash openclaw-env/post-restore-check.sh
bash openclaw-env/qmd-agent-status.sh main
openclaw status --json
systemctl --user status openclaw-gateway.service --no-pager
command -v cli-anything
```

---

## 如果恢复后只想确认“我现在是不是接回来了”

直接检查这几项：

- `~/.openclaw/workspace/pulsenest-php`
- `~/.openclaw/workspace/openclaw-env`
- `~/.openclaw/workspace/HANDOFF.md`
- `~/.openclaw/workspace/PROJECT_VERSIONS.md`
- `~/.openclaw/skills/cli-anything/SKILL.md`
- `~/.openclaw/hooks/self-improvement/handler.js`
- `openclaw status --json` 里当前版本 / 当前模型 / gateway 状态
- `bash openclaw-env/qmd-agent-status.sh main` 能看到 agent-scoped QMD 索引与 gateway QMD env

---

## 仍需手动补的东西

这些不属于 Git 自动恢复范围：

- GitHub SSH key
- OpenClaw provider 登录态 / token
- 某些 OAuth / 浏览器登录态
- 已配对设备信息
- 本机安装的软件本体

如果默认模型需要继续沿用，恢复后记得重新确认对应 provider 是否仍已登录。

QMD 高级能力默认仍建议保持关闭；如要准备 embedding / rerank，先用：

```bash
bash openclaw-env/qmd-prefetch-models-via-mirror.sh check all
```
