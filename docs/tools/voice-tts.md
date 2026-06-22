# Voice replies / TTS

> 语音回复 / TTS / Kokoro / ChatTTS / XTTS


- Local voice-reply helpers live in: `tools/voice-reply/`
- **Simple local fallback** uses `msedge-tts` in user space (no root required)
  - Script: `tools/voice-reply/tts.mjs`
  - Default Chinese voice: `zh-CN-XiaoxiaoNeural`
  - **Current default voice-reply version**: `中文混合模板版本`
    - definition: 以更自然的中文音色为底,再吸收用户最终确认的更真实语气与语速;当前采用的成品模板为"第一条合体版提速 20%"
    - user-selected reference sample: `tmp/voice-replies/zh-hybrid-default-template.mp3`
    - usage rule: for future Chinese voice replies, use this as the default template across voice-reply surfaces unless the user explicitly asks for another voice/template
    - target feel: "第一条的声音 + 第二条的语气和语速",最终确认版为 `zh-hybrid-noiz-natural-plus20-20260508-1225.mp3`
  - Named fallback preset: **基础女声版本**
    - definition: local `msedge-tts` baseline using `zh-CN-XiaoxiaoNeural`
    - purpose: safety fallback when later experiments sound worse, stiffer, or less natural
    - restore rule: if the user says "恢复到基础女声版本", revert to this preset directly
    - reference sample chosen by user: `tmp/voice-replies/natural-baseline-xiaoxiao-20260422-164306.mp3`
  - 当前正式默认:`voice-reply-hard-default` 已挂进运行配置,并在当前公司 Linux 机的 gateway 中启用
  - 当前 OpenClaw / Control UI 主线默认:优先 `wav` / 尽量少损,不再把 `mp3` 当主默认
  - Example:
    - `node tools/voice-reply/tts.mjs --text '你好,我是贾维斯。' --out /tmp/jarvis-voice.mp3`
- **Noiz-based helper** for stronger timbre continuity:
  - Script: `tools/voice-reply/noiz-reply.sh`
  - Private default reference clip path: `~/.local/share/openclaw-voice-reply/default-ref.mp3`
  - Presets: `natural`, `gentle`, `bright`, `late-night`
  - Current preferred Chinese template chain:
    - timbre-direction sample: `tmp/voice-replies/zh-msedge-closer-to-nvidia-20260508-1222.mp3`
    - user-final chosen template result: `tmp/voice-replies/zh-hybrid-noiz-natural-plus20-20260508-1225.mp3`
    - stable alias for future reuse: `tmp/voice-replies/zh-hybrid-default-template.mp3`
  - Supports pitch correction after synthesis with formant preservation:
    - `--pitch-semitones -1.5` → lower register slightly while keeping the speaking feel mostly intact
    - implemented with ffmpeg `rubberband` filter and `formant=preserved`
  - Example:
    - `bash tools/voice-reply/noiz-reply.sh --style natural --pitch-semitones -1.5 --text '你好,我在。' --out /tmp/noiz-reply.mp3`
- **Local free XTTS helper** for on-device voice cloning:
  - Script: `tools/voice-reply/local-xtts-reply.sh`
  - Uses local env: `~/.local/share/openclaw-voice-venv311`
  - Default private reference clip path: `~/.local/share/openclaw-voice-reply/default-ref.mp3`
  - Default output path: `tmp/voice-replies/local-xtts-YYYYmmdd-HHMMSS.mp3`
  - Example:
    - `bash tools/voice-reply/local-xtts-reply.sh --text '你好,我在。' --out /tmp/local-xtts.mp3`
- **Chunked voice reply delivery (首句先出,当前会话一次性交付)**:
  - 核心约定:**主会话 ≡ 当前会话**,一次回复送所有分块音频到当前会话
  - Script: `tools/voice-reply/voice-reply-chunked-deliver.sh`
  - 调用现有分块管线,自动把所有分块音频放到一条消息中返回
  - 输出 JSON 的 `agentReply` 字段包含可直接返回当前会话的文本,格式为:
    - `分块文字拼接` + `\n\n[[audio_as_voice]]\nMEDIA:块1\nMEDIA:块2(如有)\n...`
  - Example(agent exec 调用):
    - `result=$(bash tools/voice-reply/voice-reply-chunked-deliver.sh "回复文本内容")`
    - `agentReply=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['agentReply'])")`
    - 然后将 `$agentReply` 作为当前会话返回内容
  - Output fields:
    - `ok`: true/false
    - `agentReply`: 当前会话可直接返回的文本(含 `[[audio_as_voice]]` + 所有 `MEDIA:`)
    - `chunkCount`: 分块数
    - `mediaPaths[]`: 所有音频路径
    - `audioAsVoice`: 始终为 true(有音频时)
  - 失败时自动回退纯文本(`ok: false`,`agentReply` 为原始文本)
  - 向后兼容:`voice-reply.sh` 仍然是稳定的单块默认入口
- If a helper is used manually, send with:
  - `[[audio_as_voice]]`
  - `MEDIA:/path/to/file.mp3`
- If a helper is used manually, send with:
  - `[[audio_as_voice]]`
  - `MEDIA:/path/to/file.mp3`

### Local audio trimming / reference-voice prep

- User-space ffmpeg helper installed at:
  - `~/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg`
- Reason: this machine has no system `ffmpeg` / `ffprobe`, but Noiz voice cloning rejects reference audio longer than 30s, so local trimming may be needed before upload.
- Example trim command:
  - `~/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg -y -ss 40 -t 10 -i '/path/input.mp3' -vn -acodec libmp3lame -b:a 96k '/path/output.mp3'`

### Kokoro TTS 离线中文语音(2026-05-08 已验证通过)

- 适用机器:公司(Linux)
- 系统 / OS:Linux
- 模型文件位置:`tmp/kokoro-offline/`
  - `kokoro-v1.0.int8.onnx`(92MB,官方 int8 量化)
  - `voices-v1.0.bin`(28MB,54 个声音全部含中文)
- Python 运行环境:`/tmp/kokoro-test-venv`(Python 3.11,已安装 `kokoro-onnx`, `misaki`, `scipy`, `soundfile`)
- **完全离线**,无网络依赖、无播放设备依赖(纯推理→wav)
- 可用中文声音:`zf_xiaobei` `zf_xiaoni` `zf_xiaoxiao` `zf_xiaoyi`(女声)、`zm_yunjian` `zm_yunxi` `zm_yunxia` `zm_yunyang`(男声)
- 用法(直接 Python):
  ```python
  from kokoro_onnx import Kokoro
  kokoro = Kokoro(
      model_path='tmp/kokoro-offline/kokoro-v1.0.int8.onnx',
      voices_path='tmp/kokoro-offline/voices-v1.0.bin'
  )
  audio, sr = kokoro.create('你好', voice='zf_xiaoxiao', speed=1.0, lang='cmn')
  ```
- 包装脚本:`tools/kokoro-tts/kokoro-tts.sh`
  - `bash tools/kokoro-tts/kokoro-tts.sh --text '你好' --voice zf_xiaoxiao --out /tmp/out.mp3`
- 试听样本:`tmp/voice-replies/kokoro-zh-official-int8-demo.mp3`
- **默认使用路由**:由主会话决定是否替换当前 Noiz/Edge TTS 管线

### ChatTTS hybrid 中文语音(2026-05-09 起已有正式 stable 入口)

- 适用机器:公司(Linux)
- 系统 / OS:Linux
- 当前定位:**用户已明确认可这条 ChatTTS hybrid stable 主线,可作为正式的 ChatTTS 本地入口使用;`Noiz` 继续保留为保底版本。**
- 运行环境:`~/.local/share/openclaw-voice-venv311/bin/python3`
- 正式入口(Skill 脚本):`skills/chattts-stable/scripts/chattts_stable.py`
- 本地便捷包装器:`tools/voice-reply/chattts-stable.sh`
- preset 配置:`skills/chattts-stable/assets/presets.json`
- preset embedding 文件:`skills/chattts-stable/assets/presets/*.spk.txt`
- 当前默认规则:
  - `default` = 当前主线默认音色(model-default)
  - `preset-1` / `preset-2` / `preset-3` = 已保存的可切换候选音色
  - **默认语速 / 节奏**:`tempo=1.10`(2026-05-12 的 A/B 后,用户确认这档整体感觉最好)
  - **当前清晰度优先导出方向**:优先 `wav` / 尽量少损的导出;同一文本下,用户明确觉得无损版清晰度最好
- 推荐运行方式:
  - `python3 skills/chattts-stable/scripts/chattts_stable.py --list-presets`
  - `python3 skills/chattts-stable/scripts/chattts_stable.py --preset default --text '你好,我在。' --out tmp/voice-replies/chattts-stable-default.mp3`
  - `bash tools/voice-reply/chattts-stable.sh --preset preset-2 --text '我给你换一条音色。' --out tmp/voice-replies/chattts-stable-preset2.mp3`
- 历史原型脚本(保留作研发记录,不再作为正式入口):
  - `tmp/voice-replies/chattts-run-hybrid.py`
  - `tmp/voice-replies/chattts-run-hybrid-stable.py`
  - `tmp/voice-replies/chattts-hybrid-sample-speakers.py`
- hybrid 资产目录:`tmp/voice-replies/chattts-hybrid/asset/`
  - `DVAE_full.pt` / `Vocos.pt` / `Decoder.pt`:来自 `chattts-v011/`
  - `Embed.safetensors` + tokenizer:来自 v3 资产
  - GPT:由 v011 `GPT.pt` 转成 HuggingFace `config.json + model.safetensors`
- 当前关键补丁点(已内置在正式入口里):
  - 绕过官方 sha256 校验(自组装资产不会匹配原始哈希)
  - `DVAE/DVAEDecoder load_state_dict(..., strict=False)`,容忍缺失 encoder 键
  - tokenizer 从已失效的 `encode_plus()` 改走 `__call__()`,兼容当前 transformers
- 已知限制:
  - **无 encoder**:只能稳定走 decoder 推理路径,不适合参考音频克隆
  - **纯 CPU**:短句可用,但不适合追求实时流式
  - **版本脆弱**:对依赖版本和素材结构敏感,后续升级时要防回归
- 判断规则:
  - 若用户明确要走 `ChatTTS stable` / 本地 ChatTTS / preset 音色切换,优先使用这条正式入口
  - 若要"任意参考音频克隆"或更强 timbre continuity,仍优先评估 `Noiz` / 其他方案,不要误把当前 stable 路线当成通用克隆器

### Local free voice-cloning stack

- `uv` installed in user space at:
  - `~/.local/bin/uv`
- Reason: system Python lacks `pip` / `ensurepip`, so normal `venv` bootstrap is broken on this machine.
- Working local Coqui/XTTS environment path:
  - `~/.local/share/openclaw-voice-venv311`
  - actual storage is moved to the second disk and symlinked at:
    - `/mnt/data/openclaw/openclaw-voice-venv311`
- XTTS model cache path:
  - `~/.local/share/tts`
  - actual storage is moved to the second disk and symlinked at:
    - `/mnt/data/openclaw/tts`
- uv cache path:
  - `~/.cache/uv`
  - actual storage is moved to the second disk and symlinked at:
    - `/mnt/data/openclaw/uv-cache`
- Important compatibility notes:
  - Coqui TTS `0.22.0` does **not** support Python 3.12 on this machine; use Python 3.11 via `uv`.
  - XTTS with current PyTorch/TTS stack needed local compatibility fixes on this machine:
    - pin `transformers==4.41.2` (newer 5.x / late 4.x removed `BeamSearchScorer` expected by XTTS)