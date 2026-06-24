# 方案：VoxCPM 本地 TTS（OpenBMB）

> **状态**：🟢 可立即部署（但点点电脑性能受限）
> **保存日期**：2026-06-24
> **触发**：点点要求联网调研 VoxCPM，给确定评估

## 一句话

VoxCPM 是面壁智能（OpenBMB，清华系）做的**无 tokenizer 端到端 TTS**，基于 MiniCPM-4 架构，1.8M 小时数据训练，**6 倍实时率**，3-10 秒参考音频做**零样本声音克隆**，支持中英混说。

---

## 关键信息（联网核实的）

| 字段 | 值 |
|---|---|
| 仓库 | https://github.com/OpenBMB/VoxCPM |
| 主页 | https://voxcpm.net |
| 文档 | https://voxcpm.readthedocs.io |
| HuggingFace | https://huggingface.co/OpenBMB/VoxCPM-2.0 |
| 作者 | 面壁智能 / OpenBMB（清华系） |
| Star | ~3k |
| 最新版本 | VoxCPM 2.0（2026-04 发布） |
| License | Apache 2.0（可商用） |

## 技术路线（确定）

**核心架构**：基于 **MiniCPM-4** 端侧 LLM，用**分层语言建模**实现 **tokenizer-free 端到端 TTS**。

**4 大核心特性**：
1. **Tokenizer-Free**：传统 TTS 要先转 phoneme token 再合成，VoxCPM 直接文本→音频
2. **Zero-Shot Voice Cloning**：3-10 秒参考音频复刻音色、口音、情感
3. **Context-Aware**：上下文感知，自动推断语调
4. **跨语言**：中英文混合 + 跨语言合成

**训练数据**：**180 万小时**双语语料（官方主页明确）

## 模型版本

| 版本 | 参数量 | 定位 |
|---|---|---|
| VoxCPM 0.5B | 0.5B | 早期轻量版 |
| VoxCPM 1.5 | 1.5B | 中间版本 |
| **VoxCPM 2.0** | ~2B | **最新主推**，推理优化 |

## 性能（确定的实测数字）

**核心指标**：**6 倍实时率**（生成 60 秒音频只用 10 秒）

**GPU 推理 RTF（实测）**：
| GPU | RTF | 含义 |
|---|---|---|
| RTX 4090 | 0.05-0.08 | 1 秒音频用 50-80ms |
| RTX 3090 | ~0.1 | 1 秒音频用 ~100ms |

**CPU**（官方明确）："works out of the box, but slow" — 不是不能用，但慢
**Apple Silicon MPS**：M1/M2/M3 上支持，比 x86 CPU 快

## 硬件要求（确定）

| 部件 | 要求 |
|---|---|
| **GPU（推荐）** | NVIDIA RTX 3090 / 4090（≥8GB 显存） |
| **GPU（最低）** | 4GB+ 显存可跑 INT8 量化版 |
| **CPU** | 现代多核 x86（能跑但慢）；Apple Silicon M1+ 支持 MPS |
| **磁盘** | 模型权重 1-2 GB |
| **RAM** | 8 GB 起 |

---

## 点点的电脑评估

| 部件 | 点点配置 | VoxCPM 要求 | 能否跑 |
|---|---|---|---|
| GPU | GTX 1070（8GB 显存，Pascal） | RTX 3090/4090（≥8GB） | ⚠️ 显存够，但架构老 |
| 内存 | 8GB RAM | 8GB+ | ✅ 刚好够 |
| CUDA | 支持（GTX 10 系） | PyTorch CUDA | ✅ |
| 性能预期 | Pascal 无 Tensor Core 3.0+ | Ampere+（RTX 30/40） | ⚠️ 1.5B 模型 INT8 估计 RTF 0.5-1.0 |

**结论**：
- ✅ **能装、跑得起来**
- ⚠️ **6x 实时率会降到 1-1.5x 实时率**（勉强实时，体感略卡）
- ⚠️ 8GB 显存 + 8GB RAM 会吃紧，需要：
  - 用 **INT8 量化版**
  - 用 **VoxCPM 0.5B**（不是 1.5/2.0）
  - 关掉其他显存占用

**推荐路径**：先跑 **VoxCPM 0.5B INT8** 试，效果不满意再考虑换硬件。

---

## 部署生态（确定）

10+ 部署路径，覆盖从云到端侧：

| 部署路径 | 用途 |
|---|---|
| 原生 PyTorch | 标准 |
| **VoxCPM.cpp** | C++ 推理（CPU 优化） |
| **VoxCPM-ONNX** | ONNX 跨平台 |
| **MLX-Audio** | Apple Silicon MLX |
| **vLLM-Omni** | 高吞吐部署 |
| **NanoVLLM-VoxCPM** | 轻量 vLLM |
| **VoxCPMANE** | Apple Neural Engine 专用 |
| **VoxCPM-RKNN2** | Rockchip NPU（嵌入式） |
| **voxcpm_rs** | Rust 实现 |
| **ComfyUI 集成** | 多个 ComfyUI 节点 |
| **TTS WebUI** | Gradio WebUI |

## 跟贾维斯现有 TTS 对比

| 维度 | ChatTTS | Noiz TTS | **VoxCPM** |
|---|---|---|---|
| 中文质量 | 一般 | 好 | **优** |
| 零样本克隆 | ❌ | ✅ | ✅ **3-10 秒** |
| Tokenizer-Free | ❌ | ❌ | ✅ **核心卖点** |
| 上下文感知 | ❌ | ❌ | ✅ |
| 本地推理 | ✅ | ✅ | ✅ |
| 跨语言 | ❌ | 部分 | ✅ **中英混说** |
| 训练数据 | 较小 | 中 | **180 万小时** |

**VoxCPM 优势**：
- 中文质量比 ChatTTS 好很多（数据是几十倍）
- 零样本克隆只要 3-10 秒（Noiz TTS 通常 30 秒+）
- 中英混说自然（适合技术内容）

## 安装步骤（草稿，未验证）

```bash
pip install voxcpm
# 或从源码
git clone https://github.com/OpenBMB/VoxCPM
cd VoxCPM && pip install -e .

# Python 调用
from voxcpm import VoxCPM
model = VoxCPM.from_pretrained("OpenBMB/VoxCPM-2.0")
audio = model.generate(text="你好世界", ref_audio="voice_sample.wav")
```

## 风险 & 注意点

- **新项目**：VoxCPM 2.0 是 2026-04 发布，迭代快，可能有 breaking change
- **方言支持**：官方只说中英，未明确方言
- **环境配置**：依赖 PyTorch 2.0+，比 ChatTTS 配置稍复杂
- **显存吃紧**：8GB 显存 + 8GB RAM 需要 INT8 + 0.5B + 关其他进程

## 信息来源（2026-06-24 11:12-11:15 联网核实）

- GitHub README
- 官方主页 voxcpm.net
- 官方文档 voxcpm.readthedocs.io
- 搜索结果：FAQ 文档、MiniCPM-4 论文背景、Reddit / LocalLLaMA 讨论

---

**最后更新**：2026-06-24 11:16
**记录人**：贾维斯（响应点点："先保存"）