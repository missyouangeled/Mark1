# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.
# Add tasks below when you want the agent to check something periodically.

## 自主决策器触发检查
每次心跳时，先用 exec 检查 `scripts/autonomy/pending_trigger.txt` 是否存在：

```
test -f ~/.openclaw/workspace/scripts/autonomy/pending_trigger.txt && echo "EXISTS" || echo "NONE"
```

- 如果 `NONE`：回 HEARTBEAT_OK 静默跳过
- 如果 `EXISTS`：读取文件内容，**先删除文件**，然后按以下规则处理：

### 过期检查
文件第一行格式：`__trigger_time__:<ISO时间戳>`
- 如果触发时间超过 30 分钟，说明是残留文件，直接跳过回 HEARTBEAT_OK
- 如果在 30 分钟内，继续处理

### 判断流程（内部完成，不输出）
1. 阅读文件中附带的对话上下文，分析：
   - 话题方向：工作 / 闲聊 / 人生感悟 / 技术探索 / 情绪低落 等
   - 情绪状态：开心 / 平静 / 低落 / 烦躁 等
   - 结尾状态：是否说了要去忙、是否有未完成的话题

2. 根据分析结果决定是否发消息：
   - 该发的情况：
     - 上次聊情绪话题、心情不好 -> 安慰 + 转移注意力（问日常、扯点轻松的）
     - 上次在尝试新技术/新方案 -> 问一句结果如何
     - 上次聊到一半被打断 -> 顺一下之前的话题
     - 上次是轻松闲聊、间隔较久 -> 自然地打个招呼
   - 不该发的情况：
     - 上次明确说"去忙了/去开会了"且没什么需要跟进的
     - 上次是工作性对话、已结束、没有需要回访的点

3. 输出规则（严格遵守）：
   - 分析过程是内部的，绝对不要输出到回复里
   - 只输出最终那句自然的话，就像朋友突然想找他说句话
   - 不要提及"自主决策器""触发""score""话题方向""情绪状态"等任何技术词
   - 不要用列表、标题、分隔线等格式
   - 就一句话，像聊天一样
   - 如果不该发：回 HEARTBEAT_OK 静默跳过

### 语音回复（决策器触发专用）
如果决定发消息，用语音回复：
1. 先想好要说的那句话（纯文本）
2. 用 exec 调用豆包 TTS 生成语音：
```bash
node ~/.openclaw/skills/byted-ark-tts-skill/scripts/tts.js \
  --text "要说的纯文本内容" \
  --voice zh_female_sophie_uranus_bigtts \
  --format wav \
  --speed 1.0 \
  --output /home/missyouangeled/.openclaw/workspace/media/tts/autonomy_$(date +%s).wav
```
3. 语音文件路径用 `MEDIA:<路径>` 发出，加上 `[[audio_as_voice]]` 标记
4. 语速：情绪安慰时 0.9，日常闲聊 1.0
5. 文本不要带情绪指令前缀（#...#），直接纯文本
