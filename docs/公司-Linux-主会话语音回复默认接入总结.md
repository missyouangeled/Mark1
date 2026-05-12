# 公司 Linux 主会话语音回复默认接入总结

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 更新时间：2026-05-12

## 本轮目标

把当前主会话的中文语音回复从“可手动测试的能力”推进到“正式挂进运行配置的默认能力”，同时保持以下边界不变：

1. **主会话 = 当前会话**，不能误绑到内部基础会话（如 `agent:main:main`）
2. 默认标准固定为：**默认音色 / preset + `tempo 1.10` + 优先 `wav` / 尽量少损**
3. **只在主会话生效**，不要扩到其他会话或别的直聊面
4. 不为了语音效果冒 OpenClaw 主体稳定性的风险

## 已完成内容

### 1. 默认音频标准已收口

当前默认标准已经统一到以下口径：

- 默认音色：`default`
- 默认节奏：`tempo 1.10`
- 默认导出方向：优先 `wav` / 尽量少损
- 长句结构完整时正常语速；短句仅轻微降速
- 能一条就一条；太长不稳再退两条

相关文件：

- `skills/chattts-stable/assets/presets.json`
- `skills/chattts-stable/SKILL.md`
- `tools/voice-reply/chattts_voice_reply.py`
- `tools/voice-reply/chunked_voice_reply.py`
- `TOOLS.md`
- `MEMORY.md`
- `memory/daily/2026-05-12.md`

### 2. 主会话默认接入已落地为插件

已落地插件：

- `plugins/voice-reply-hard-default/package.json`
- `plugins/voice-reply-hard-default/openclaw.plugin.json`
- `plugins/voice-reply-hard-default/voice-reply-hook.js`

当前实际实现不是走旧分析稿里的 `before_agent_reply`，而是：

1. `before_agent_finalize` 暂存本轮最终 assistant 文本
2. `reply_dispatch` 阶段调用：
   - `tools/voice-reply/voice-reply-chunked-deliver.sh`
3. 成功后发送主会话可直接消费的 `agentReply`
4. 若语音生成失败，则回退到正常文字回复

这条实现保留了现有分块语音管线，不额外复制 TTS 逻辑。

### 3. 作用范围已收紧为“仅当前主会话”

本轮先把插件从“webchat/direct 默认接管”继续收紧为：

- **仅对白名单中的当前主会话 sessionKey 生效**
- 其他会话默认不自动走语音

当前本机配置中的白名单 sessionKey：

- `agent:main:dashboard:0f8c81b3-cf9f-4ed2-a6f1-d1772fed8395`

这层白名单写在本机：

- `~/.openclaw/openclaw.json`

对应配置项：

- `plugins.entries.voice-reply-hard-default.config.allowedSessionKeys`

## 验证结果

本轮已经确认：

1. Gateway 已加载 `voice-reply-hard-default`
2. 配置热重载已生效
3. Gateway 重启后恢复正常运行
4. 当前主会话 sessionKey 与白名单一致

已见到的关键日志口径包括：

- `http server listening (3 plugins: browser, memory-core, voice-reply-hard-default)`
- `config hot reload applied (plugins.entries.voice-reply-hard-default.config)`

## GitHub 记录

与本轮语音默认接入直接相关、已推送到 GitHub 的提交：

- `4a2cb13` — `Enable hard-default voice replies for webchat direct`
- `9d10d51` — `Restrict hard-default voice replies to main session`

## 当前边界与后续注意事项

1. **GitHub 里保存的是代码与文档，不是本机 live 配置本身**
   - 插件代码、文档、默认参数已在仓库中
   - 但真正启用与当前主会话白名单，仍依赖本机 `~/.openclaw/openclaw.json`

2. **如果未来切到新的主会话窗口**
   - 需要同步更新：
     - `plugins.entries.voice-reply-hard-default.config.allowedSessionKeys`
   - 然后执行：
     - `openclaw gateway restart`

3. **其他机器拉取仓库后不会自动继承当前主会话白名单**
   - 因为 sessionKey 与本机运行时相关
   - 其他机器若要启用，必须在本机重新绑定对应当前主会话

4. **不要把 `voice-reply-hard-default-hooks/` 里的旧分析稿当成当前实现说明**
   - 那份分析稿记录的是早期思路
   - 当前实际落地逻辑应以 `plugins/voice-reply-hard-default/` 目录内代码为准
