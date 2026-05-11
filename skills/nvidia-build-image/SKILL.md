---
name: nvidia-build-image
description: "Generate images with NVIDIA Build using the existing local `nvidia:default` auth profile. Use when the user wants text-to-image, quick model switching between NVIDIA Build image models, or a repeatable local workflow for prompts, seeds, ratios, and saved outputs. Triggers include requests like ‘生成图片’, ‘文生图’, ‘换图片生成模型’, ‘继续上次那张图’, or any request to use NVIDIA Build / FLUX image generation directly. Current note: self-hosted NVIDIA Visual GenAI NIM documents support image editing / image-guided inputs, but the current NVIDIA Build hosted route on this machine does not yet accept arbitrary local image base64 input."
---

# NVIDIA Build Image

Use the local script instead of ad-hoc one-off snippets so image generation stays fast and consistent.

## Quick start

### 文生图（默认 `flux-dev`）

```bash
python3 skills/nvidia-build-image/scripts/nvidia_build_image.py \
  --model flux-dev \
  --prompt 'photorealistic portrait of a quiet young East Asian woman on a night street' \
  --ratio 1:1 \
  --steps 28 \
  --seed 20260511 \
  --out tmp/nvidia-image-test/portrait.jpg
```

### 快速草图（`flux-schnell`）

```bash
python3 skills/nvidia-build-image/scripts/nvidia_build_image.py \
  --model flux-schnell \
  --prompt 'a futuristic city at night after rain' \
  --steps 4 \
  --seed 42 \
  --out tmp/nvidia-image-test/fast.jpg
```

### 更快的另一条文生图模型（`flux-klein`）

```bash
python3 skills/nvidia-build-image/scripts/nvidia_build_image.py \
  --model flux-klein \
  --prompt 'cinematic rainy city street at night, realistic photography' \
  --steps 4 \
  --seed 42 \
  --out tmp/nvidia-image-test/flux-klein.jpg
```

### 关于图生图（当前状态）

- NVIDIA **self-hosted** Visual GenAI NIM 文档里，`/v1/images/edits` 与部分 image-guided 能力是存在的
- 但这台机器当前接的是 **NVIDIA Build hosted** 路线
- 实测无论是 `flux.1-dev` 的 `canny/depth`，还是 `flux.1-kontext-dev` 的本地图输入，都会返回：
  - `Expected: example_id, got: base64`
- 所以目前这个 skill **先稳定做文生图 / 快速切模型**，不要把“本地图片直接图生图”当成已可用能力

## Current model policy

- `flux-dev`: 主线质量模型，优先用于真实感人物图
- `flux-schnell`: 最快的 smoke test / 先看方向
- `flux-klein`: 已验证可用的另一条官方文生图模型，适合快速切模型比较
- 当前先不要在这个 skill 里乱混外部 inference.sh / Gemini 路线，保持 NVIDIA Build 主线干净

## Rules

- 默认优先用自然语言 prompt，不要把 prompt 写成很僵的表单
- 如果目标是“真实、好看”的女性人像，优先沿 `flux-dev + 自然直说式描述` 微调
- 当前默认把这个 skill 当成“文生图 + 快速切模型”入口；图生图仍记为待补能力
- 输出图片会同时生成一个同名 `.json` 元数据文件，里面保存 endpoint、payload 和 seed
- 如果要了解当前已验证的模型习惯、踩坑和偏好，读 `references/model-notes.md`

## Known pitfalls

- `seed` 必须 `< 4294967296`
- `flux-dev` 不吃 `guidance_scale` / `aspect_ratio`，要改用 `cfg_scale` 和 `width` / `height`
- 当前 NVIDIA Build hosted 路线对本地图片直传会卡在 `Expected: example_id, got: base64`
- 因此当前 skill 里不要把 `--image` / `canny` / `depth` 当成已可用主功能
