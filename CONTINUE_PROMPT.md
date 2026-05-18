# CONTINUE_PROMPT.md

把下面这段话原样复制给任何新的 AI 模型 / 代理，就能尽量无缝接着当前工作继续。

---

继续 `broker / infos-handle` 这条主线。

先不要重写结构，也不要直接开大改。先按下面顺序恢复上下文：

1. 读 `HANDOFF.md`，重点看：
   - `给下一个模型的增强阶段直读摘要`
   - `可直接贴给下一个模型的接手提示词`
   - `明天/下周一继续时的最短恢复路径`
2. `git log --oneline -5`
3. `git status --short`
4. 跑最小验证：
   - `python3 scripts/test-openclaw-infos-handle.py`
   - `python3 scripts/test-frontstage-broker.py`
   - `python3 scripts/apply-openclaw-frontstage-broker-data.py --verify-control-ui-infos-handle-sidecar`
5. 看 sidecar 状态：
   - `systemctl --user --no-pager --full status openclaw-infos-handle-sidecar.service`
6. 以当前 Git 最新状态和 `HANDOFF.md` 为准继续开发

当前必须先记住的事实：

- 这条线的当前正确定位是：
  - `broker = sidecar 数据层 + compat 壳`
  - `infos-handle = 正式请求/处理层`
  - `Control UI = 优先消费 infos-handle sidecar，失败再回退 snapshot`
- 正式主入口继续保持：
  - `handle --request-file`
  - `openclaw_infos_handle_contract.py`
- 不要把新逻辑塞回 `broker emit/query/notify-frontstage` 这些 compat 壳
- 不要把当前工作重新定义成“大拆分层重构”

当前代码停点：

- `9d6f358` `Verify infos-handle sidecar artifact transport`

最近两步已做完：

- 最新：把 `apply-openclaw-frontstage-broker-data.py --verify-control-ui-infos-handle-sidecar` 扩到会真实验证 image artifact transport：实际调用 `handle(format=image)`，并确认返回的 `artifactHref` 确实可经 `/v1/artifacts/...` 取回 SVG
- 上一步：把 `*.summary` 类音频 spoken-text plan 收紧为：**最多 3 段、最多 1 条建议**
- 另已补：`health.summary` 音频回归测试，以及 sidecar artifact transport 的 caller/contract 回归测试
- 昨晚/今天早上发生过一次临时关机，但恢复后已验证主链、broker 视图、sidecar 与最小 consumer 都仍正常

如果继续做，默认只在下面两个方向里二选一：

1. 继续增强 `image/audio delivery`，但**不改主入口**
2. 继续把新增 caller / consumer 收口到 `infos-handle handle --request-file` 主路径

如果你接手后不确定从哪开始，就先输出：

- 当前已完成哪些能力
- 当前最新停点 commit 是什么
- 当前验证是否仍全绿
- 下一步只选哪一个增强方向，为什么

---

## 极简版（一句话）

继续 `broker / infos-handle`；先读 `HANDOFF.md`，再看最近提交和工作区状态，先跑 `test-openclaw-infos-handle.py`、`test-frontstage-broker.py`、`apply-openclaw-frontstage-broker-data.py --verify-control-ui-infos-handle-sidecar`，确认仍是绿的后，再沿 `handle --request-file + openclaw_infos_handle_contract.py` 主路径小步继续。