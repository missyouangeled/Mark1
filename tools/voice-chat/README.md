# Voice Chat MVP（公司 Linux）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 文档类型：本机专用运行说明

## 目标

把这条链先搭成可用 MVP：

1. 浏览器录音
2. 送到本机 NVIDIA audio bridge 做 ASR
3. 把识别文本交给 OpenClaw agent
4. 用 `chattts-stable` 返回中文语音
5. 浏览器自动播放回复

当前这版是 **半双工**：说完一句再回一句。
它不是 full duplex 实时打断式语音通话，但已经把“即时可回复语音对话”的主链路接起来了。

> 当前定位补充（2026-05-09）：
> - 这套 `tools/voice-chat/` 仍保留为 **公司 Linux 机上的验证/原型工具**
> - 当前正式主线已经转向“主会话打字 → 后台生成语音 → 直接回主会话音频”
> - 所以后续默认优先维护主会话直回音频这条线，而不是继续把独立 voice-chat 页面当成主入口

## 目录

- 服务主脚本：`tools/voice-chat/voice_chat_app.py`
- 浏览器页面：`tools/voice-chat/index.html`
- 启动脚本：`tools/voice-chat/run-voice-chat.sh`
- 运行期状态：`tmp/voice-chat/voice-session.json`
- 输出音频：`tmp/voice-chat/outputs/`

## 依赖前提

### 1. NVIDIA audio bridge 已可用

默认地址：`http://127.0.0.1:18890`

至少要满足：

- `tools/nvidia-audio-bridge/bridge.py` 能正常跑
- `GET /health` 返回 `ok: true`
- `/v1/audio/transcriptions` 可正常识别中文音频

### 2. ChatTTS stable 已可用

默认调用：

- `tools/voice-reply/chattts-stable.sh`
- 实际底层：`skills/chattts-stable/scripts/chattts_stable.py`

### 3. 本机 `openclaw` CLI 可用

服务内部会调用：

- `openclaw gateway call sessions.create`
- `openclaw agent --session-id ... --message ... --json`

## 启动

```bash
bash tools/voice-chat/run-voice-chat.sh
```

默认监听：

- `http://127.0.0.1:18891/`

如果要改地址：

```bash
OPENCLAW_VOICE_CHAT_HOST=0.0.0.0 OPENCLAW_VOICE_CHAT_PORT=18891 bash tools/voice-chat/run-voice-chat.sh
```

## 页面功能

- **开始录音 / 停止并发送**：浏览器麦克风输入一轮语音
- **文本直测**：不录音，直接测试 `agent -> ChatTTS` 这半条链
- **重建 voice session**：重置独立语音会话

## 关键设计说明

### 1. 默认使用独立 voice session

默认 key：`agent:main:voice-chat`

原因：

- 不把当前文字主会话刷满语音测试消息
- 语音连续对话仍然保留上下文
- 后面如果确认要和当前主会话完全合并，再把 backend 改成主会话即可

### 2. 先做半双工，不先做实时打断

这次先追求：

- 链路打通
- 语音听感稳定
- 失败点可定位

而不是一上来就上复杂的 realtime relay / interruption / barge-in。

## 当前已知边界

- 依赖浏览器 `MediaRecorder`；极老浏览器可能不支持
- ASR 速度受 NVIDIA bridge / 网络影响
- 回复速度受 OpenClaw 当前模型与 ChatTTS CPU 推理速度影响
- 这版不会边听边说，也不支持说话中途打断回复
- `openclaw agent --json` 的输出结构如果以后变更，可能需要微调 `voice_chat_app.py` 里的提取逻辑

## 下一步建议

如果这版主链路稳定，下一阶段按这个顺序推进更稳：

1. 把 `agent` 调用改成更直接的 gateway RPC，减少 CLI 解析脆弱性
2. 加 VAD / 自动停录，而不是手动点“停止并发送”
3. 接 `talk.realtime.*`，做更低延迟的实时音频流
4. 再考虑打断、回声消除、热词唤醒这些更难的部分
