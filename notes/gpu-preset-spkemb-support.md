# GPU ChatTTS preset/spk_emb support — 完成记录

## 2026-05-12 17:03 (Asia/Shanghai)

## 改动文件

只改了 1 个文件：`scripts/chattts_seeta_gpu.py`

### 新增功能

1. **`--preset` 参数**：指定预设音色（name 或 alias）。不传 `--preset` 时，自动使用 `skills/chattts-stable/assets/presets.json` 中的 `defaultPreset`（当前为 `"default"`，即 seed_1910 固定版主会话默认女声）。

2. **`--list-presets` 参数**：列出所有可用预设。

3. **多音色支持**：
   - `default` / `a` / `main` — 主会话默认女声（seed_1910 固定版）
   - `model-default` / `md` — 原始 model-default（无 spk_emb，会漂移）
   - `preset-1` / `b` / `1` — 候选音色 1
   - `preset-2` / `c` / `2` — 候选音色 2
   - `preset-3` / `d` / `3` — 候选音色 3
   - `first-female` — 从 .mp3 提取的首选女声

### 技术实现

- spk_emb 数据从本地 `skills/chattts-stable/assets/presets/*.spk.txt` 读取（base14 + LZMA 压缩的 float16 speaker embedding）
- 通过 base64 编码，作为 `CHATITTS_SPK_EMB_B64` 环境变量传递到远端 GPU 机器
- 远端脚本解码后，通过 `ChatTTS.Chat.InferCodeParams(spk_emb=...)` 注入推理
- 远端 `pybase16384` 已在之前安装完成，LZMA 是 CPython 内置模块

### 验证结果（4/4 通过）

| 测试 | 预设 | 结果 | 文件 |
|------|------|------|------|
| 默认音色（seed_1910） | default | ✅ 2.38s, 114KB | `tmp/voice-replies/chattts-gpu-default-preset-test.wav` |
| 候选音色 1 | preset-1 | ✅ 1.89s, 91KB | `tmp/voice-replies/chattts-gpu-preset-1-test.wav` |
| 别名切换 | a (=default) | ✅ 0.95s, 46KB | `tmp/voice-replies/chattts-gpu-alias-a-test.wav` |
| 无 spk_emb | model-default | ✅ 1.46s, 70KB | `tmp/voice-replies/chattts-gpu-model-default-test.wav` |

### 兼容性说明

- 移除了 `--text` 的 `required=True`（改为手工校验），以允许 `--list-presets` 无需 `--text`
- 远端 InferCodeParams 的导入路径为 `ChatTTS.Chat.InferCodeParams`（即类属性，不是独立模块导出）
- `--text` 仍为必要参数（`--list-presets` 除外）
