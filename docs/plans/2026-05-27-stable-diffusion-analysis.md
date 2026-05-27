# Stable Diffusion 本地部署 — 完整分析与使用报告

> 整理日期：2026-05-27 | 适用机器：公司（Linux）/ 掌机（Windows）通用参考

---

## 一、Stable Diffusion 是什么

Stable Diffusion（SD）是 Stability AI 开源的 AI 图像生成模型，基于潜在扩散模型（Latent Diffusion Model）。通过文本描述（Prompt）即可生成高质量图像，也支持图生图、局部重绘、图像放大、风格迁移等功能。

相比 Midjourney / DALL·E 等闭源在线服务，SD 的核心优势：
- **完全开源免费**，离线运行，隐私无忧
- **模型生态极其丰富**：Civitai 上有数万个社区训练的 Checkpoint / LoRA / VAE
- **高度可控**：ControlNet 骨骼绑定、IP-Adapter 人脸迁移、AnimateDiff 动画等

---

## 二、三大主流 UI 对比

### 1. AUTOMATIC1111 Stable Diffusion WebUI（A1111）
| 项目 | 详情 |
|------|------|
| GitHub | `https://github.com/AUTOMATIC1111/stable-diffusion-webui` |
| 定位 | 最老牌、最普及的 SD 图形界面 |
| 核显/低显存 | 不友好，最低建议 6GB+ VRAM |
| 优点 | 插件生态最丰富，教程最多，社区最大 |
| 缺点 | 代码老旧，显存效率低，维护渐慢 |
| 适合谁 | 入门学习、需要大量教程参考的新手 |

### 2. Stable Diffusion WebUI Forge（⭐ 推荐）
| 项目 | 详情 |
|------|------|
| GitHub | `https://github.com/lllyasviel/stable-diffusion-webui-forge` |
| 定位 | A1111 的优化版，同一个人（lllyasviel = ControlNet 作者）开发 |
| 核显/低显存 | **非常友好**，4GB VRAM 即可跑，低显存下比 A1111 快 75% |
| 优点 | 继承 A1111 界面和插件兼容性 + ComfyUI 级别的显存优化 |
| 缺点 | 部分老旧插件可能不兼容 |
| 适合谁 | **绝大多数用户，尤其是低显存卡** |

### 3. ComfyUI
| 项目 | 详情 |
|------|------|
| GitHub | `https://github.com/comfyanonymous/ComfyUI` |
| 定位 | 节点式工作流，专业/进阶用户 |
| 核显/低显存 | 最好，节点化加载可按需分配显存 |
| 优点 | 工作流可复用分享，极低的显存占用，新模型支持最快 |
| 缺点 | 学习曲线陡峭，不适合想"点两下就出图"的用户 |
| 适合谁 | 追求极致控制和工作流自动化的进阶用户 |

---

## 三、硬件要求

| 需求层级 | GPU | VRAM | RAM | 磁盘 | 出图速度（512×512） |
|----------|-----|------|-----|------|---------------------|
| **最低（Forge --lowvram）** | NVIDIA GTX 1650 | 4GB | 8GB | 30GB SSD | 20-40 秒/张 |
| **推荐** | NVIDIA RTX 3060 | 12GB | 16GB | 60GB SSD | 3-6 秒/张 |
| **舒适** | NVIDIA RTX 4070+ | 12GB+ | 32GB | 100GB SSD | 1-2 秒/张 |
| **无 NVIDIA GPU（CPU 模式）** | 无 | 0 | 16GB+ | 60GB | 10-30 分钟/张 ❌ |

### 特殊说明
- **AMD GPU**（如你的 ROG 掌机）：Windows 下可用 DirectML 模式跑，性能约为同档 NVIDIA 的 40-60%
- **Intel Arc**：有 OpenVINO 加速方案，但生态不够成熟
- **Apple Silicon**：有 MPS 后端（Draw Things / Mochi Diffusion），Mac 用户友好

---

## 四、下载地址汇总

| 组件 | 地址 | 说明 |
|------|------|------|
| **A1111 WebUI** | `https://github.com/AUTOMATIC1111/stable-diffusion-webui` | Git clone 安装 |
| **WebUI Forge** ⭐ | `https://github.com/lllyasviel/stable-diffusion-webui-forge` | Git clone 安装 |
| **ComfyUI** | `https://github.com/comfyanonymous/ComfyUI` | Git clone 安装 |
| **基础模型 SD 1.5** | `https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5` | 入门用，文件约 4GB |
| **基础模型 SDXL 1.0** | `https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0` | 目前主流，文件约 7GB |
| **社区模型** | `https://civitai.com` | 最丰富的模型/ LoRA 下载站 |
| **模型镜像** | `https://huggingface.co` | 官方模型仓库 |

---

## 五、依赖清单

### 操作系统
- Windows 10/11（最主流）
- Linux（Ubuntu 22.04+ 推荐）
- macOS 12.6+（Apple Silicon）

### 必需基础依赖

| 依赖 | 版本要求 | 作用 | 安装方式 |
|------|---------|------|----------|
| **Python** | 3.10.6 - 3.11.x | 运行环境 | `python.org` 下载 / `apt install python3.10` |
| **Git** | 2.x+ | 克隆源码 | `git-scm.com` / `apt install git` |
| **CUDA Toolkit** | 11.8 或 12.1 | NVIDIA GPU 加速 | NVIDIA 官网 |
| **cuDNN** | 对应 CUDA 版本 | 深度学习 GPU 加速库 | NVIDIA 开发者中心 |
| **PyTorch** | 2.0+ with CUDA | 深度学习框架 | `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121` |

### Python pip 依赖（自动安装）
WebUI 首次启动时会自动安装以下核心依赖，无需手动操作：
```
gradio, transformers, diffusers, opencv-python, Pillow,
scikit-image, scipy, numpy, omegaconf, einops, kornia,
safetensors, accelerate, xformers
```

### 可选（但强烈建议）
| 组件 | 作用 |
|------|------|
| **xformers** | 大幅降低 VRAM 占用（NVIDIA 30%+ 优化） |
| **ControlNet 扩展** | 骨骼绑定、深度图、线稿控制 |
| **AnimateDiff** | 图生视频 |
| **Deforum** | AI 视频/动画生成 |
| **中文界面包** | `https://github.com/VinsonLaro/stable-diffusion-webui-chinese` |

---

## 六、安装步骤（以 Forge 为例）

### Linux
```bash
# 1. 安装系统依赖
sudo apt update && sudo apt install -y git python3.10 python3.10-venv python3-pip

# 2. 克隆 Forge
git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git
cd stable-diffusion-webui-forge

# 3. 启动（首次自动下载 PyTorch + 依赖）
./webui.sh --listen --port 7860
```

### Windows
```cmd
# 1. 安装 Python 3.10.6 + Git
# 2. 克隆 Forge
git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git
cd stable-diffusion-webui-forge

# 3. 编辑 webui-user.bat，根据需要添加：
#    set COMMANDLINE_ARGS=--xformers --listen --port 7860

# 4. 双击 webui-user.bat 启动
```

### 低显存优化参数（webui-user.bat / webui-user.sh 中添加）
```
--xformers               # 启用 xformers 优化
--medvram                # 4-6GB VRAM
--lowvram                # 2-4GB VRAM（会慢很多）
--no-half-vae            # 部分低端卡需要
--opt-split-attention    # 降低显存峰值
```

---

## 七、关键模型文件说明

| 文件类型 | 目录（Forge/A1111） | 说明 |
|----------|---------------------|------|
| Checkpoint（大模型） | `models/Stable-diffusion/` | .safetensors 或 .ckpt，2-7GB/个 |
| LoRA / LyCORIS | `models/Lora/` | 微调模型，10-200MB/个 |
| VAE | `models/VAE/` | 色彩/细节增强，约 300MB |
| ControlNet | `extensions/sd-webui-controlnet/models/` | 控制骨骼/线稿等，约 1.5GB/个 |
| Embedding | `embeddings/` | 文本嵌入，几 KB |

### 推荐入门模型
| 模型 | 来源 | 风格 |
|------|------|------|
| SD 1.5 基础模型 | HuggingFace | 通用 |
| SDXL 1.0 | HuggingFace | 高分辨率通用 |
| Realistic Vision v6 | Civitai | 真人写实 |
| DreamShaper | Civitai | 艺术/插画 |
| Anything v5 | Civitai | 二次元 |

---

## 八、本机适配结论

### 公司 Linux 机
| 项目 | 要求 | 本机 | 判定 |
|------|------|------|------|
| GPU CUDA | NVIDIA 4GB+ | VMware 虚拟显卡 | ❌ |
| RAM | 16GB+ | 7.7 GiB | ❌ |
| 磁盘 | 60GB+ | / 11G + /mnt/data 31G | ⚠️ |
| Python | 3.10+ | 3.12.3 | ✅ |
| DISPLAY | 有更好 | :0 | ✅ |

**结论：不能直接跑。缺少 NVIDIA GPU 是致命伤。**

### 掌机（ROG Ally / Windows）
| 项目 | 要求 | 预计 | 判定 |
|------|------|------|------|
| GPU | 4GB+ VRAM | AMD RDNA3 集成显卡 | ⚠️ |
| RAM | 8GB+ | 16GB | ✅ |
| DirectML | Windows SDK | 内置 | ✅ |

**结论：可以用 DirectML 后端跑 Forge，速度约为同档 NVIDIA 的 40-60%。虽不理想但确实能用。**

---

## 九、替代方案（不需要本地 GPU）

| 方案 | 费用 | 体验 |
|------|------|------|
| **Civitai 在线生成** | 免费（有限额） | 浏览器直接生成，无需安装 |
| **HuggingFace Spaces** | 免费 | 在线 Demo，速度一般 |
| **Replicate API** | 按量付费，约 $0.002/张 | API 调用，速度快 |
| **SeetaCloud GPU** | ~0.5-2 元/小时 | 完整 Linux 环境，自由度高 |
| **RunPod / Vast.ai** | ~$0.3-0.7/小时 | GPU 容器，按小时租 |

---

## 十、推荐行动路线

1. **先尝鲜**：上 Civitai.com 直接用浏览器在线生成，感受一下效果
2. **想在掌机上试**：装 Forge + DirectML，注册个 Civitai 账号下模型
3. **想正经玩**：租 SeetaCloud GPU 实例，完整 Linux 环境，一小时几毛钱
