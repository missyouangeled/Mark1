# Control UI infos-handle CSP 修复方案（2026-06-02）

**目标**：修复 Control UI branding 脚本把 infos-handle 请求写死到 `http://127.0.0.1:18790`，导致浏览器在当前 CSP 下拦截 `connect-src` 的问题；让 live dock 默认走同源 `/v1/...` 统一入口，并保留 snapshot 回退链路。

**涉及文件**：
- `config/control-ui-branding.json`
- `scripts/apply-openclaw-control-ui-branding.py`
- `scripts/apply-openclaw-frontstage-broker-data.py`
- `scripts/test-infos-handle-frontstage-callers.py`
- `docs/公司-Linux-OpenClaw-维护说明.md`
- `docs/通用-OpenClaw-补丁变更流水.md`

**验证方式**：
- `python3 scripts/test-infos-handle-frontstage-callers.py`
- `python3 scripts/apply-openclaw-control-ui-branding.py`
- `python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-snapshot-dock --require-control-ui-snapshot-dock --verify-control-ui-infos-handle-sidecar --require-control-ui-infos-handle-sidecar`
- `curl -s http://127.0.0.1:18788/v1/query/snapshot.summary?format=json | head`
- 检查 live `jarvis-branding-override.js` 不再包含 `http://127.0.0.1:18790` 的 Control UI infos-handle Href

## 任务 1：改 branding 配置与生成脚本
- [ ] 把 Control UI 默认 infos-handle 入口改为同源 `/v1/...` 路径，而不是写死 `127.0.0.1:18790`
- [ ] 给 task / recovery 卡片补显式 Href，避免继续依赖 `infosHandleBaseUrl` 拼接绝对地址
- [ ] 保留 snapshot JSON 回退逻辑

## 任务 2：改验证脚本
- [ ] 让 `apply-openclaw-frontstage-broker-data.py` 能识别相对路径 Href
- [ ] 当 Href 为相对路径时，优先按统一入口 `http://127.0.0.1:18788` 做本机验证
- [ ] 保持 sidecar image artifact / SSE 验证可继续跑通

## 任务 3：补测试与维护说明
- [ ] 更新 `test-infos-handle-frontstage-callers.py` 的期望
- [ ] 更新维护说明，明确 Control UI live dock 走同源 `/v1/...`（经统一入口代理）
- [ ] 追加变更流水
