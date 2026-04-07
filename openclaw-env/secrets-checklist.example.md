# 新机器秘密项恢复清单

这份清单不存真实秘密，只存“你要补哪些东西”。

## 必补

- [ ] GitHub SSH key 已放到 `~/.ssh/`
- [ ] `ssh -T git@github.com` 可通过
- [ ] OpenClaw provider 登录态已恢复
- [ ] 如需继续沿用当前默认模型，已重新确认 / 登录对应 provider（当前机器默认模型锚点：`github-copilot/gpt-5.4`）
- [ ] `~/.openclaw/openclaw.json` 中私密字段已人工核对
- [ ] 如需设备控制/配对：相关 device pairing 已重新建立
- [ ] 如需使用 Tavily：在目标机补好 `TAVILY_API_KEY`（不要把真实 key 提交进 Git）

## 建议核对

- [ ] `openclaw gateway status` 正常
- [ ] `systemctl --user status pulsenest-preview.service` 正常
- [ ] `systemctl --user status openclaw-resume-watch.timer` 正常
- [ ] `openclaw hooks list` 中 `self-improvement` 为 ready
- [ ] `command -v cli-anything` 可用
- [ ] `~/.openclaw/skills/cli-anything/SKILL.md` 已存在
- [ ] `http://127.0.0.1:8093/` 可访问

## 注意

不要把真实 token、私钥、密码直接提交进 Git 仓库。
