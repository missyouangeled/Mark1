# NVIDIA Build / NIM 图像模型备注

## 当前后端分层

### `build-hosted`
- 当前正式可用主线
- 直接复用 OpenClaw 的 `nvidia:default`
- 适合：文生图、快速切模型、稳定快反应
- 当前实测成功：`flux-dev`、`flux-schnell`、`flux-klein`

### `nim-http`
- 为未来 self-hosted NVIDIA Visual GenAI NIM 预留的第二后端
- 目标：把真正图生图 / 编辑入口接进同一份 skill，而不是另起一套散脚本
- 当前状态：接口层已准备，但这台机器上尚未验证实际服务可用
- 当前本机现实边界：`nvidia-smi` 不可用，因此不能把“本机已具备 self-hosted NIM 条件”当成事实

## Build hosted：已验证模型

### `flux-dev`
- 端点：`https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev`
- 适合：真实感人像、夜景、人像比例更稳的图
- 当前已验证可用字段：
  - `prompt`
  - `seed`（必须 `< 4294967296`）
  - `steps`
  - `width` / `height`
  - `cfg_scale`
  - `mode=base`
- 已踩坑：
  - 不能传 `guidance_scale`
  - 不能传 `aspect_ratio`
  - 要改用 `cfg_scale` + `width/height`

### `flux-schnell`
- 端点：`https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell`
- 适合：快速 smoke test、先看大概方向
- 当前已验证可用字段：
  - `prompt`
  - `seed`
  - `steps`

### `flux-klein`
- 端点：`https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b`
- 适合：快速切另一条 NVIDIA 官方文生图模型做对比
- 当前已验证可用字段：
  - `prompt`
  - `seed`
  - `steps`
- 当前状态：已完成最小 200 成功探活

## self-hosted NIM：当前预留接口

### `flux-dev`（`nim-http`）
- 目标路径：`/v1/infer`
- 预留模式：`base` / `canny` / `depth`
- 预留行为：
  - `canny` / `depth` 时接受 `image` + `preprocess_image=true`
- 依据：NVIDIA Visual GenAI NIM 文档的原生 `v1/infer` 示例

### `flux-schnell`（`nim-http`）
- 目标路径：`/v1/infer`
- 当前预留：基础文生图
- 依据：NVIDIA Visual GenAI NIM 文档的 FLUX.1-schnell 路线

### `flux-kontext`（`nim-http`）
- 目标路径：`/v1/infer`
- 当前预留：带 `image` 的编辑入口
- 要求：必须传 `--image`
- 依据：NVIDIA Visual GenAI NIM 文档的 FLUX.1-Kontext-dev 示例

## 为什么现在不把 hosted 图生图写成已可用

- `flux.1-dev` 的 `canny/depth` 在当前 hosted 路线上会报：`Expected: example_id, got: base64`
- `flux.1-kontext-dev` 在当前 hosted 路线上同样卡在：`Expected: example_id, got: base64`
- NVIDIA 文档里的 OpenAI-compatible `/v1/images/generations` 与 `/v1/images/edits` 描述的是 Visual GenAI NIM 能力，不等于当前 `ai.api.nvidia.com` / `integrate.api.nvidia.com` 上已有同路由可直接用；本轮对 hosted 入口的访问结果是 404

## 当前工作流建议

1. 首次试图：`build-hosted + flux-schnell`
2. 人像/真实感：`build-hosted + flux-dev`
3. 需要快速换另一条官方模型比较：`build-hosted + flux-klein`
4. 真要图生图：先确认有可访问的 self-hosted Visual GenAI NIM，再切 `--backend nim-http`

## Prompt 偏好（当前用户验证）

- 更喜欢自然直说式 prompt
- 不喜欢过度模板化、表单化、堆结构词的 prompt
- 女性人像优先：真实、自然、好看、少 AI 感
- 若要更性感，优先“更有女性感、克制、优雅”，不要直接走廉价夸张路线
