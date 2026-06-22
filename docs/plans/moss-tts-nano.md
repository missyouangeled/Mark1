# MOSS-TTS-Nano 本地部署方案

> 创建日期：2026-06-22
> 状态：待办（缺服务器）
> 决策等级：中

---

## 一、为什么是它

### 核心诉求
让贾维斯"说话"——本地 TTS，**不依赖云端 API**、不烧 token。

### 候选对比

| 方案 | 部署 | 声音克隆 | 语种 | 实时 | 资源 |
|------|------|---------|------|------|------|
| **MOSS-TTS-Nano** | 本地 CPU | ✅ 短片段零样本 | 20 | ✅ | 0.1B / 1GB |
| Noiz TTS（现有） | 云端付费 | ❌ | 多 | ✅ | 持续扣费 |
| ChatTTS（本地） | 本地 | ❌ | 中英 | 一次性 | 中等 |
| XTTS（本地） | 本地 GPU | ✅ 6 秒 | 多 | 慢 | **要 GPU** |
| Edge TTS | 云端免费 | ❌ | 多 | ✅ | 网络依赖 |

**MOSS-TTS-Nano 唯一同时满足**：本地 + CPU + 声音克隆 + 实时 + 多语种。

---

## 二、关键指标

```
参数量:        0.1B
分词器:        ~20M (CNN-free, causal Transformer)
音频规格:      48 kHz 立体声
Token 速率:    12.5 Hz
RVQ 层数:      16
比特率:        0.125-2 kbps（可配置）
语种:          20（中日英 + 韩/西/法/德/意/俄/阿拉伯/波斯/葡/波/捷/丹/瑞/希/土/匈）
声码:          Local Transformer + autoregressive
声音克隆:      短参考片段，零样本（无 finetune）
机构:          复旦 NLP 实验室 + MOSI.AI（上海创新院）
发布日期:      2026-04-10
License:       待确认
```

---

## 三、仓库与资源

| 类型 | 链接 |
|------|------|
| 主仓库 | https://github.com/OpenMOSS/MOSS-TTS-Nano |
| HF 模型 | https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano |
| HF Demo | https://huggingface.co/spaces/OpenMOSS-Team/MOSS-TTS-Nano |
| 论文 | https://arxiv.org/abs/2603.18090 |
| 桌面 Reader App | https://github.com/OpenMOSS/MOSS-TTS-Nano-Reader |
| 机构主页 | https://github.com/OpenMOSS（50+ 仓库） |

---

## 四、部署架构

```
┌─────────────────────────────────────────┐
│  OpenClaw TTS Skill                     │
│  ~/.openclaw/workspace/skills/.../tts   │
└───────────────┬─────────────────────────┘
                │ HTTP/本地 socket
                ▼
┌─────────────────────────────────────────┐
│  MOSS-TTS-Nano 推理服务                  │
│  - app.py (Gradio Web UI)               │
│  - app_onnx.py (ONNX 加速版)            │
│  - infer.py (CLI 推理)                  │
└───────────────┬─────────────────────────┘
                │ 加载模型
                ▼
┌─────────────────────────────────────────┐
│  模型权重                                 │
│  OpenMOSS-Team/MOSS-TTS-Nano            │
│  OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano│
└─────────────────────────────────────────┘
```

---

## 五、依赖与资源

### 硬件
- **CPU**：现代多核（4 核+）
- **内存**：~2GB（模型加载）
- **硬盘**：~1GB（模型权重）
- **GPU**：不需要

### 软件
- Python 3.10+
- PyTorch（CPU 版即可）
- Hugging Face transformers
- Gradio（web UI）

---

## 六、待办步骤

1. ⏸ 等待服务器到位
2. ⬜ 克隆仓库：`git clone https://github.com/OpenMOSS/MOSS-TTS-Nano`
3. ⬜ 下载模型权重到 `models/` 目录
4. ⬜ 启动 `app.py` 跑通 demo
5. ⬜ 检查 License，确认商业使用边界
6. ⬜ 写 OpenClaw Skill 包装（HTTP 调用 + 缓存 + 错误处理）
7. ⬜ 集成到 Control UI TTS 链路
8. ⬜ 跑 CPU 性能测试（首 token 延迟、长文本稳定性）
9. ⬜ 声音克隆测试（需要先和你确认参考音频来源）

---

## 七、风险与未决问题

### 法律/伦理
- **License 未确认**：开源协议可能限制商用
- **声音克隆授权**：用谁的参考音频？需要明确授权链路
- **隐私**：参考音频如果含个人信息，需考虑存储与传输

### 技术
- **CPU 实时性**：0.1B 跑 CPU 应该 OK，但需要实测
- **长文本稳定性**：可能需要 chunk
- **中文质量**：官网 demo 看起来不错，但需要长文本验证
- **多语种切换**：是否需要手动指定语种

### 集成
- **现有 TTS 替换**：noiz / ChatTTS / XTTS 三个 skill 怎么处理
- **降级路径**：本地失败时是否回退云端

---

## 八、参考实施记录

待开始实施时追加：
- 实施日期
- 实际部署的服务器信息
- 性能测试数据
- 与 OpenClaw 集成的具体方案
- 任何坑点

---

*本方案由 2026-06-22 联网搜索生成，状态为"待服务器到位"。*
