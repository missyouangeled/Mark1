# Local-only credential pointers

> 本地凭据 / SSH / API key 指针


- OpenCode Zen 备用 API key:
  - 用途:紧急备用的 OpenCode Zen / opencode.ai 模型网关 key,默认不接入 OpenClaw,不设为主模型,只在用户明确要求时再手动启用/测试
  - 本地保存:`credentials/api/opencode-zen.env`
  - 当前状态:已验证可访问 `https://opencode.ai/zen/v1/models` 与免费模型最小连通性;默认仅作备用,不用于长期主会话/隐私敏感上下文
  - 安全边界:优先仅用于公开/低敏测试;如后续正式接入,应继续保持"备用 provider、不改默认模型"原则
- SeetaCloud 租用 ChatTTS GPU(westd):
  - 用途:远端 GPU 环境,准备给 ChatTTS / 更逼真的主会话语音回复使用
  - 非敏感连接标识:`root@connect.westd.seetacloud.com:18786`
  - 敏感凭据本地保存:`credentials/ssh/seetacloud-chattts-westd.md`
  - 安全规则:该文件位于 `credentials/`(gitignored),只在本机保存,不写进 Git 历史
  - 若后续再次卡住需要重连,先从这里定位到本地凭据文件,再 SSH 上去看 `/root/autodl-tmp/voice-lab/install_chattts_gpu.log`

## Why Separate?
## 火山方舟 Agent Plan
- 用途: Mark42 advisor + OpenClaw fallback 模型（GLM-5.2）
- endpoint: https://ark.cn-beijing.volces.com/api/plan/v3
- key 本地保存: ~/.openclaw/credentials/.volcengine-agent.key（chmod 600）
- openclaw.json 里也有: models.providers.volcengine-agent.apiKey
- 备注: Agent Plan 允许 OpenClaw 接入（官方文档确认）；Coding Plan key 不允许通用 API 调用
