# PLANS.md - 方案存档

> 调研结论、技术方案、决策策略统一归档。
> 详细方案在 `docs/plans/` 下。

---

## 📌 待办方案（pending infrastructure）

### MOSS-TTS-Nano 本地部署（2026-06-22）

- **背景**：让贾维斯"说话"——本地 TTS 替代云端 Noiz TTS
- **方案**：[MOSS-TTS-Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano)
- **关键指标**：0.1B 参数 / CPU 实时 / 20 语种 / 声音克隆 / 48kHz 立体声
- **依赖**：无 GPU（CPU 即可）、Python、~1GB 模型权重
- **仓库**：
  - 主仓库：https://github.com/OpenMOSS/MOSS-TTS-Nano
  - HF 模型：https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano
  - HF Demo：https://huggingface.co/spaces/OpenMOSS-Team/MOSS-TTS-Nano
  - 论文：https://arxiv.org/abs/2603.18090
- **配套**：
  - MOSS-TTS-Nano-Reader（网页朗读 + 桌面 reader app）
- **机构**：复旦 NLP 实验室 + MOSI.AI
- **阻塞**：**待服务器到位**（当前无独立 TTS 服务器）
- **待确认**：License、商业使用边界、声音克隆授权

### 完整细节

详见 `docs/plans/moss-tts-nano.md`

---

## ✅ 已完成方案（2026-06-22）

### AI 模型路由终极修复
详见 `docs/通用-AI模型路由问题排查与修复手册.md`

