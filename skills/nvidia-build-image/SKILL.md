---
name: nvidia-build-image
description: "Generate images with NVIDIA Build using the existing local `nvidia:default` auth profile, and keep a prepared backend switch for future self-hosted NVIDIA Visual GenAI NIM usage. Use when the user wants text-to-image, quick model switching between NVIDIA Build image models, or a repeatable local workflow for prompts, seeds, ratios, and saved outputs. Triggers include requests like ‘生成图片’, ‘文生图’, ‘图生图’, ‘换图片生成模型’, ‘继续上次那张图’, or any request to use NVIDIA Build / FLUX image generation directly. Current note: this machine’s NVIDIA Build hosted route does not yet accept arbitrary local image base64 input, so direct image editing remains a self-hosted NIM path, not a hosted claim."
---

# NVIDIA Build Image

Use the local script instead of ad-hoc one-off snippets so image generation stays fast and consistent.

## Quick start

### 当前正式主线：Build hosted 文生图

```bash
python3 skills/nvidia-build-image/scripts/nvidia_build_image.py \
  --backend build-hosted \
  --model flux-dev \
  --prompt 'photorealistic portrait of a quiet young East Asian woman on a night street' \
  --ratio 1:1 \
  --steps 28 \
  --seed 20260511 \
  --out tmp/nvidia-image-test/portrait.jpg
```

### 快速试方向

```bash
python3 skills/nvidia-build-image/scripts/nvidia_build_image.py \
  --backend build-hosted \
  --model flux-schnell \
  --prompt 'a futuristic city at night after rain' \
  --steps 4 \
  --seed 42 \
  --out tmp/nvidia-image-test/fast.jpg
```

### 快速换另一条官方模型

```bash
python3 skills/nvidia-build-image/scripts/nvidia_build_image.py \
  --backend build-hosted \
  --model flux-klein \
  --prompt 'cinematic rainy city street at night, realistic photography' \
  --steps 4 \
  --seed 42 \
  --out tmp/nvidia-image-test/flux-klein.jpg
```

### 为未来 self-hosted NIM 预留的后端入口

```bash
python3 skills/nvidia-build-image/scripts/nvidia_build_image.py \
  --backend nim-http \
  --base-url http://127.0.0.1:8000 \
  --model flux-kontext \
  --image ./reference.jpg \
  --prompt 'keep the subject, make it more realistic and refined' \
  --seed 20260511 \
  --out tmp/nvidia-image-test/kontext-edit.jpg
```

## Backend policy

- `build-hosted`：当前正式可用主线；默认就走它
- `nim-http`：为未来 self-hosted Visual GenAI NIM 预留的第二后端接口
- 在当前这台机器上，不要把 `nim-http` 当成已经本地跑通；它是**接口准备完成**，不是**本机服务已部署完成**

## Current model policy

### `build-hosted`
- `flux-dev`：主线质量模型，优先用于真实感人物图
- `flux-schnell`：最快的 smoke test / 先看方向
- `flux-klein`：已验证可用的另一条官方文生图模型，适合快速切模型比较

### `nim-http`
- `flux-dev`：按 NVIDIA NIM 文档预留 `base/canny/depth` 入口
- `flux-schnell`：按 NVIDIA NIM 文档预留基础文生图入口
- `flux-kontext`：按 NVIDIA NIM 文档预留本地图编辑入口

## Rules

- 默认优先用自然语言 prompt，不要把 prompt 写成很僵的表单
- 如果目标是“真实、好看”的女性人像，优先沿 `flux-dev + 自然直说式描述` 微调
- 当前主会话里，把这个 skill 先当成“文生图 + 快速切模型”的正式入口
- 只有在 self-hosted NIM 服务真实存在时，才切到 `--backend nim-http`
- 输出图片会同时生成一个同名 `.json` 元数据文件，里面保存 backend、endpoint、payload 和 seed
- 如果要了解当前已验证的模型习惯、踩坑和后端边界，读 `references/model-notes.md`

## Known pitfalls

- `seed` 必须 `< 4294967296`
- `flux-dev` 在 Build hosted 路线上不吃 `guidance_scale` / `aspect_ratio`，要改用 `cfg_scale` 和 `width` / `height`
- 当前 NVIDIA Build hosted 路线对本地图片直传会卡在 `Expected: example_id, got: base64`
- `nim-http` 后端当前是**接口已准备**，不是**这台机器已部署**；若服务没起，会直接失败
- 当前 `nim-http` 正式入口还没有把 ratio/size 与 cfg_scale 参数完全展开，先走最小稳定参数集
