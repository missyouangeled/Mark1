# 🧩 贾维斯中枢 Mark2 — 小模型清单 v1.0

> 定位：Mark2 中枢服务器上计划部署的本地小模型目录。每个模型标注安装方式、硬件需求、能干什么、推荐度。
> 创建：2026-06-15
> 适用范围：中枢服务器（Ubuntu 24.04，基线 8核16G+）
> 原则：优先轻量 → 优先免费 → 优先 ONNX 可脱离框架 → 有用才装

---

## 零、总览

| # | 模型 | 参数量 | 用途 | 推荐度 | 状态 |
|---|------|--------|------|--------|------|
| 1 | **PP-OCRv6** | 1.5M~34.5M | 文字检测+识别（OCR） | ⭐⭐⭐⭐⭐ | 待部署 |
| — | （待扩充） | — | — | — | — |

---

## 一、PP-OCRv6

### 1.1 基本信息

| 项目 | 内容 |
|------|------|
| **全称** | PP-OCRv6 |
| **出品** | 百度 PaddlePaddle 团队 |
| **发布时间** | 2026-06-12 |
| **许可证** | Apache 2.0（完全免费，可商用） |
| **论文** | arXiv:2606.13108（2026-06-11） |
| **官网** | https://www.paddleocr.com |
| **源码** | https://github.com/PaddlePaddle/PaddleOCR |
| **模型下载** | https://huggingface.co/collections/PaddlePaddle/pp-ocrv6 |
| **CVPR 2026** | PP-OCRv5 + PaddleOCR-VL 已被 CVPR 2026 Demo Track 接收 |

### 1.2 模型规格

| 规格 | 参数量 | 模型大小（约） | 适用场景 |
|------|--------|---------------|---------|
| **tiny** | 1.5M | ~6 MB（ONNX） | 浏览器、超轻边缘设备 |
| **small** | 7.7M | ~30 MB（ONNX） | 树莓派、低配 VPS |
| **medium** | 34.5M | ~140 MB（ONNX） | 服务器、高精度需求 |

> 三档共享同一架构（LCNetV4 骨干 + RepLKFPN + EncoderWithLightSVTR），只是 block 数量不同。

### 1.3 精度表现

| 指标 | PP-OCRv6_medium | 对比 PP-OCRv5_server | 对比百亿级 VLM |
|------|-----------------|---------------------|---------------|
| 文字检测 Hmean | **86.2%** | +4.6% | 超越 Qwen3-VL-235B / GPT-5.5 / Gemini-3.1-Pro |
| 文字识别准确率 | **83.2%** | +5.1% | 同上 |
| CPU 推理速度 | 5.2× faster（OpenVINO） | — | 几个数量级的优势 |

核心卖点：**34.5M 参数干掉了 235B 参数的通用 VLM**，参数量差了近 7000 倍。

### 1.4 支持的场景

- 🌍 **50 种语言**统一模型（中文、英文、日文 + 46 种拉丁语系），无需切换模型
- 🏭 **PCB 电路板**文字识别
- ✏️ **CAD 图纸**文字提取
- 🔢 **数码管**数字识别
- 🟩 **点阵文字**识别
- 📄 **通用文档**：发票、合同、身份证、营业执照、表单
- 🖼️ **自然场景**：招牌、车牌、菜单、屏幕截图

### 1.5 硬件需求

| 规格 | 最低 CPU | 最低 RAM | 推荐 RAM | 磁盘（模型+框架） | GPU 需求 |
|------|----------|---------|----------|-------------------|---------|
| **tiny** | 1 核 | 256 MB | 512 MB | ~6 MB | ❌ 不需要 |
| **small** | 1 核 | 512 MB | 1 GB | ~30 MB | ❌ 不需要 |
| **medium** | 2 核 | 1 GB | 2 GB | ~140 MB | ❌ 不需要 |

> 三档全部纯 CPU 可跑。Mark2 基线 8核16G 足以跑 medium。GPU 可选，装了更快但不是必须。

推理速度参考（Xeon CPU，单张图片端到端）：

| 规格 | 耗时（约） |
|------|-----------|
| tiny | ~80ms |
| small | ~150ms |
| medium | ~300ms |

### 1.6 安装方式

#### 方案 A：完整版（推荐，功能全）

```bash
# 1. 安装 PaddlePaddle CPU 版
#    ⚠️ 重要：必须指定 ==3.2.2！3.3.x 有 CPU OneDNN bug（GitHub #77340）
python3 -m pip install paddlepaddle==3.2.2

# 2. 安装 PaddleOCR
python3 -m pip install paddleocr

# 3. 一行代码测试
python3 -c "
from paddleocr import PaddleOCR
ocr = PaddleOCR(lang='ch')
result = ocr.ocr('test.jpg')
print(result)
"
```

**优点**：完整的检测→方向分类→识别 pipeline，自动下载模型，API 最简洁。
**缺点**：需装 PaddlePaddle 框架（~400MB），总安装体积约 1.5GB。

> 🐛 **PaddlePaddle 3.3.x CPU OneDNN 回归**：3.3.0 / 3.3.1 在 CPU 推理时抛出
> `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]`
> 根因是新版 PIR 属性转换不兼容 OneDNN 后端。降级到 3.2.2 即可绕过。
> 已验证：Mark1（Ubuntu 24.04, CPython 3.12.3, PaddlePaddle 3.2.2 + PaddleOCR 3.7.0）工作正常。

#### 方案 B：ONNX 轻量版（零框架依赖）

```bash
# 1. 只装 ONNX Runtime（~30MB）
python3 -m pip install onnxruntime

# 2. 从 HuggingFace 下载 ONNX 模型
#    检测模型：PaddlePaddle/PP-OCRv6_tiny_det_onnx
#    识别模型：PaddlePaddle/PP-OCRv6_tiny_rec_onnx
#    字典文件：从 PaddleOCR 仓库下载 ppocr_keys_v1.txt

# 3. 手动拼 pipeline（检测→裁剪→识别），约 50 行代码
```

**优点**：不依赖 PaddlePaddle，总安装体积 ~200MB。可以脱离框架运行。
**缺点**：需要自己拼 pipeline，没有开箱即用的 `ocr.ocr()` 一行搞定。

#### 方案 C：Docker 版（隔离最干净）

```bash
docker run -it --rm \
  -v $(pwd):/data \
  paddlepaddle/paddleocr:latest \
  paddleocr --image_dir /data/test.jpg --lang ch
```

**优点**：完全隔离，不污染宿主机 Python 环境。
**缺点**：Docker 镜像较大（~3GB），首次启动慢。

#### Mark2 推荐

**首选方案 A**。Mark2 中枢服务器本身就是完整开发环境，Python 多版本隔离已有约定（uv/venv），不需要为了怕污染而绕 Docker。装 PaddleOCR 完整版后可以直接被贾维斯通过 exec 调用，也方便后续接其他 Paddle 模型。

### 1.7 在 Mark2 上的集成方式

```
贾维斯（OpenClaw Gateway）
  │
  ├── 用户发图片/PDF → WebChat
  │
  ├── 贾维斯调用 OCR
  │     ├── 方式1: bash tools/jarvis-ocr.sh --input xxx.jpg
  │     │         或 ./scripts/jarvis-ocr.py --input xxx.jpg
  │     └── 方式2: HTTP API（后续可封装为 sidecar 服务）
  │
  ├── 拿到结构化文本
  │     ├── 直接回复用户（识别结果）
  │     ├── 存到 tmp/ 供后续处理
  │     └── 喂给 LLM 做进一步理解
  │
  └── 典型场景
        ├── 截图报错 → OCR 提文字 → 我直接分析
        ├── 合同/发票照片 → OCR 结构化 → 填充表单
        ├── PDF 文档 → OCR 提取全文 → RAG 入库
        └── 网页截图表格 → OCR 识别行列 → Markdown 表格输出
```

**已落地的便捷入口**：
- `scripts/jarvis-ocr.py` — Python 脚本（shebang 直指 venv Python）
- `tools/jarvis-ocr.sh` — bash 包装器（自动找 venv，防 import 路径错误）
- 常用命令：`bash tools/jarvis-ocr.sh --input image.png [--json] [--benchmark] [--list-models]`

### 1.8 已知限制

1. **不支持手写体（中文）**：PP-OCRv6 专注印刷体。手写中文识别需用其他模型（如 TrOCR、PaddleOCR-VL）。
2. **布局分析需额外模型**：PP-OCRv6 只管检测+识别文字，不会自动做版面分析（标题/正文/表格分区）。版面分析需搭配 PP-Structure 或 PaddleOCR-VL。
3. **不是 VLM**：PP-OCRv6 是纯 OCR 专用模型，不会"理解"文档内容，只负责把文字提出来。理解交给 LLM。
4. **ONNX 版需要手动拼 pipeline**：不像完整版 `paddleocr` 包一行搞定。

---

## 二、待评估候选模型

> 以下模型尚未评估，列为候选。评估后移入上方正式清单。

| 候选 | 用途 | 为何候选 | 优先级 |
|------|------|---------|--------|
| PaddleOCR-VL-0.9B | 文档结构理解（VLM） | 版式分析+表格识别+公式，比纯 OCR 更强 | 中 |
| ChatTTS（已有） | 中文语音合成 | 已在 Mark1 部署，Mark2 可迁移 | 低 |
| Kokoro-82M | 多语言 TTS | 极轻量，82M 参数 | 低 |
| Whisper tiny/base | 语音识别 | OpenAI 出品，多语言 ASR | 低 |
| PP-OCRv6 手写扩展 | 手写中文 OCR | 如果后续需要 | 低 |

---

## 三、模型评审模板

新增模型到本清单前，按以下模板填写：

```markdown
### N. 模型名

| 项目 | 内容 |
|------|------|
| **全称** | |
| **出品** | |
| **许可证** | |
| **参数量** | |
| **模型大小** | |
| **最低 CPU** | |
| **最低 RAM** | |
| **GPU 需求** | |
| **用途** | |
| **推荐度** | ⭐⭐⭐ |
| **状态** | 待评估 / 待部署 / 已部署 |

#### 安装方式
（具体命令）

#### Mark2 集成方式
（怎么被贾维斯调用）
```

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-15 | v1.0 | 初版，收录 PP-OCRv6，建立模板和候选清单 |
| 2026-06-15 | v1.1 | PaddlePaddle 3.2.2 降级说明（CPU OneDNN bug #77340）；落地 scripts/jarvis-ocr.py + tools/jarvis-ocr.sh 便捷入口 |
