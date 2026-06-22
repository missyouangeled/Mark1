## 2026-05-18:infos-handle phase2 最小增强落点

### 结论

这一轮继续沿 `broker sidecar 数据层 + infos-handle 正式请求层` 主线小步推进,当前最小可交付落点定为:

1. **richer image/audio 仍留在 `scripts/openclaw-infos-handle.py` 现有 preview handler 内**
   - `image` 不新开入口,只把单条 summary-card 提升成 richer multi-panel SVG preview,并稳定回传 `layout / panels / badge / footerLines`
   - `audio` 不碰主聊天链,只补稳定 spoken-text plan(`textPlanVersion / strategy / segmentCount / segments / estimatedDurationSeconds`)后再走现有 local TTS
   - `handle --request-file` 继续是唯一推荐主路径

2. **Control UI 直连 infos-handle 采用"sidecar 优先 + snapshot 静态回退"**
   - 不硬拆现有 broker snapshot 入口
   - live branding override 只补最小直连字段:`infosHandleSummaryHref / infosHandleContractHref / infosHandleSseHref`
   - health dock 优先读本地 infos-handle sidecar,失败再回退 `jarvis-frontstage-snapshot.json`

3. **HTTP/SSE 先做独立最小 sidecar,不改 gateway 主链**
   - 独立脚本:`scripts/openclaw-infos-handle-sidecar.py`
   - 最小 HTTP:`GET /v1/query/<kind>`、`POST /v1/handle`
   - 最小 SSE:`GET /v1/events/stream`,先提供只读状态流,足够给 Control UI 做轻量刷新
   - 仓库内同步补正式落点:`tools/openclaw-infos-handle-sidecar/README.md`、`tools/openclaw-infos-handle-sidecar/openclaw-infos-handle-sidecar.service`

### 边界

- 这不是 broker compat 壳的新主逻辑
- 这也不是 gateway 主链接口定稿
- 后续若继续扩,优先补 richer renderer / consumer,而不是回退正式入口
