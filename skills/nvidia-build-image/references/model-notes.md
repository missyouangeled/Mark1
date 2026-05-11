# NVIDIA Build 图像模型备注

## 当前首发支持

### `flux-dev`
- 端点：`https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev`
- 适合：真实感人像、夜景、人像比例更稳的图
- 当前已验证可用字段（Build hosted 实测成功）：
  - `prompt`
  - `seed`（必须 `< 4294967296`）
  - `steps`
  - `width` / `height`
  - `cfg_scale`
  - `mode=base`
- 当前已确认：
  - `base`：文生图可用
- 当前未打通：
  - `canny`
  - `depth`
  - 任意本地图片直传图生图
- 已踩坑：
  - 不能传 `guidance_scale`
  - 不能传 `aspect_ratio`
  - 要改用 `cfg_scale` + `width/height`
  - 当尝试把本地图片以 base64 直接送进 hosted 路线时，会返回：`Expected: example_id, got: base64`
  - `flux.1-kontext-dev` 在当前 hosted 路线上也同样卡在 `example_id`，所以不能把它当成当前可用图生图入口

### `flux-schnell`
- 端点：`https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell`
- 适合：快速 smoke test、先看大概方向
- 当前已验证可用字段：
  - `prompt`
  - `seed`
  - `steps`
- 推荐：先出概念图、再切 `flux-dev` 做精修

### `flux-klein`
- 端点：`https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b`
- 适合：快速切另一条 NVIDIA 官方文生图模型做对比
- 当前已验证可用字段：
  - `prompt`
  - `seed`
  - `steps`
- 当前状态：已完成最小 200 成功探活

## 当前工作流建议

1. 首次试图：`flux-schnell`
2. 人像/真实感：`flux-dev`
3. 需要快速换另一条官方模型比较：`flux-klein`
4. 想要图生图：先明确当前 NVIDIA Build hosted 还没打通本地图片直传；若真要补这条能力，优先改走 self-hosted Visual GenAI NIM 或者后续确认过的 hosted 编辑入口

## Prompt 偏好（当前用户验证）

- 更喜欢自然直说式 prompt
- 不喜欢过度模板化、表单化、堆结构词的 prompt
- 女性人像优先：真实、自然、好看、少 AI 感
- 若要更性感，优先“更有女性感、克制、优雅”，不要直接走廉价夸张路线
