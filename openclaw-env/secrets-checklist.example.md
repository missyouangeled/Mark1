# 新机器秘密项恢复清单

这份清单不存真实秘密，只存“你要补哪些东西”。

## 必补

- [ ] GitHub SSH key 已放到 `~/.ssh/`
- [ ] `ssh -T git@github.com` 可通过
- [ ] OpenClaw provider 登录态已恢复
- [ ] `~/.openclaw/openclaw.json` 中私密字段已人工核对
- [ ] 如需设备控制/配对：相关 device pairing 已重新建立

## 建议核对

- [ ] `openclaw gateway status` 正常
- [ ] `systemctl --user status pulsenest-preview.service` 正常
- [ ] `systemctl --user status openclaw-resume-watch.timer` 正常
- [ ] `openclaw hooks list` 中 `self-improvement` 为 ready
- [ ] `http://127.0.0.1:8093/` 可访问

## 注意

不要把真实 token、私钥、密码直接提交进 Git 仓库。
