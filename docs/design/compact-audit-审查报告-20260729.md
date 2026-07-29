# 上下文压缩全面审查报告

> 审查日期：2026-07-29
> 审查范围：OpenClaw compaction 配置 + Mark42 armor_compress + Post-Compact Audit
> 审查人：贾维斯

---

## 🔴 P0 严重 Bug（必须修复）

### Bug 1: SummaryExtractor 的 compaction 标记全错

**文件**: `audit/summary_extractor.py`

**问题**: `_COMPACTION_MARKERS` 用了 `["<summary>", "## Compaction", "compaction_summary"]`，
但 OpenClaw 实际的 compaction 条目格式是：
```json
{"type": "compaction", "summary": "## Decisions\n...", "tokensBefore": 0, "fromHook": true}
```

实际标记应该是 `"type":"compaction"` 或 `"type": "compaction"`，且摘要文本在 `summary` 字段里，不在 `content` 字段里。

**影响**: SummaryExtractor 永远找不到 compaction 摘要，永远 fallback 到"最后 20 条消息"。
Audit 核对的是错误的数据，结论不可信。

**修复**:
1. `_COMPACTION_MARKERS` 改为 `['"type":"compaction"', '"type": "compaction"']`
2. 找到 compaction 条目后，提取 `summary` 字段而非 `content` 字段

### Bug 2: audit hook 传的 pre/post timestamp 相同

**文件**: `armor.py` 第 984-994 行

**问题**:
```python
_audit.audit_compact_async(
    pre_compact_snapshot={"timestamp": _now_iso(), ...},  # <- compact 完成后的时间
    post_compact_summary={"timestamp": _now_iso(), ...},   # <- 同一时刻
)
```

两个时间戳都是 `_now_iso()`（compact 完成后的当前时间）。

但 `SnapshotReader.find_latest_before(timestamp)` 的语义是"找到此时间之前最新的快照"。
传 compact 完成后的时间，能找到 compact 前的快照（因为快照每 10 分钟更新一次，compact 前的快照时间一定早于 compact 完成时间）。

**结论**: 逻辑上没 bug，但语义不清晰。pre_snapshot 的 timestamp 应该是 compact 开始前的时间。

### Bug 3: RuleChecker 的关键词提取对中文不合理

**文件**: `audit/checker.py`

**问题**: `_extract_keywords` 用 `re.sub(r"[^\w\s]", " ", text)` 移除标点，但 `\w` 在 Python 中默认包含中文字符。
所以 `"用户: 袁文涛"` 被分成 `["用户", "袁文涛"]`（2 个关键词），而不是 `["用户", "袁文", "涛"]`。

但 `len(w) >= 2` 的过滤会把单字中文关键词过滤掉，这可能导致短名称丢失。

**实际影响**: 低。大部分关键信息（人名、项目名）都是 2 字以上。

---

## 🟠 P1 设计漏洞（应该修复）

### 漏洞 1: OpenClaw compaction 配置缺少 qualityGuard

**问题**: `openclaw.json` 里 compaction 配置没有设 `qualityGuard`。
OpenClaw 默认 `qualityGuard.enabled=true, maxRetries=1`，但我们的配置没显式设。

**影响**: 如果 OpenClaw compact 质量差（LLM 摘要丢信息），没有重试机制。

**修复**: 显式设置 `qualityGuard: {enabled: true, maxRetries: 1}`。

### 漏洞 2: compact 超时不一致

**问题**:
- OpenClaw 配置 `timeoutSeconds: 600`（10 分钟）
- armor.py 调 `openclaw sessions compact` 用 `timeout=320`（5.3 分钟）
- armor.py subprocess timeout 是 320 秒，但 OpenClaw 内部超时是 600 秒

**影响**: armor 在 320 秒杀掉 subprocess，但 OpenClaw 内部可能还在跑（直到 600 秒）。
compact 锁 TTL 是 400 秒，如果 OpenClaw 在 320-400 秒之间完成了 compact，
armor 已经报 timeout 但实际 compact 成功了。

**修复**: armor 的 subprocess timeout 应该 > OpenClaw 的 timeoutSeconds。
改为 `timeout=620`（比 OpenClaw 的 600 多 20 秒缓冲）。

### 漏洞 3: 平台探测期检查 usage 用的是同一个 armor_check()

**问题**: `_platform_compact_probe` 每 10 秒调 `armor_check()`。
但 `armor_check()` 里有 `subprocess.run(["du", "-s", ...])`，这个 du 命令检查的是 sessions 目录大小。
如果 OpenClaw compact 后把旧 JSONL 替换成新文件，du 结果可能不变（因为文件数量不变，只是内容变了）。

**实际影响**: 中等。`armor_check` 还会调 `_estimate_tokens_smart` 读文件大小，
如果 session 文件被 compact 截短了，tokens 会下降，usage 会降。
但如果 OpenClaw 用 SQLite 存储（不走 JSONL），`_estimate_tokens_smart` 可能读不到变化。

### 漏洞 4: audit hook 只在 compactTriggered=True 时触发

**问题**: armor.py 第 983 行：
```python
if not dry_run and index.get("compactTriggered"):
```

如果 compact 失败了（`compactTriggered=False`），audit 不会触发。
但 compact 失败时也可能丢失信息（比如 compact 超时但 OpenClaw 内部部分执行了）。

**建议**: 改为 `if not dry_run` 即可（不管 compact 成功失败都审计）。

### 漏洞 5: SummaryExtractor 读 JSONL 时的编码问题

**问题**: `summary_extractor.py` 读 JSONL 用 `encoding="utf-8", errors="replace"`。
但 OpenClaw session JSONL 可能包含二进制数据（如果用户上传了图片等），
`errors="replace"` 会把无效字节替换成 `\ufffd`，可能导致 JSON 解析失败。

**影响**: 低。OpenClaw 的 JSONL 应该是纯文本。

### 漏洞 6: compact 锁的竞态条件

**问题**: `_try_acquire_compact_lock()` 检查文件存在 -> 写文件，不是原子操作。
两个进程可能同时检查到锁不存在，然后都写入锁文件。

**修复**: 用 `O_CREAT | O_EXCL` 原子创建文件：
```python
import errno
try:
    fd = os.open(COMPACT_LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, json.dumps(...).encode())
    os.close(fd)
    return True
except OSError as e:
    if e.errno == errno.EEXIST:
        # 锁文件已存在，检查是否过期
        ...
    return False
```

---

## 🟡 P2 改进建议（可以后续做）

### 建议 1: OpenClaw 配置补全缺失字段

```json
{
  "compaction": {
    "enabled": true,              // 显式启用
    "recentTurnsPreserve": 3,     // OpenClaw 默认值
    "identifierPolicy": "strict", // OpenClaw 默认值
    "qualityGuard": {             // 显式设置
      "enabled": true,
      "maxRetries": 1
    }
  }
}
```

### 建议 2: audit 的 LLMChecker 应该有自己的超时

**问题**: LLMChecker 调 `llm.chat()` 没有设超时。如果 LLM 响应慢，审计线程会一直挂着。

**修复**: 加 `timeout=60` 参数。

### 建议 3: BuiltinAudit 的异步线程没有错误可见性

**问题**: `_async_run` 吞掉所有异常。如果审计持续失败，用户完全不知道。

**修复**: 在 `_async_run` 的 except 里写 broker 事件。

### 建议 4: snapshot_reader 的 _extract_preferences 只看 MEMORY.md

**问题**: 偏好规则实际上分散在 `memory/rules/chat-prefs.md`、`work-prefs.md` 等文件里。
但快照里只有 `MEMORY.md`，不包含 `memory/rules/` 目录。

**影响**: 偏好类信息提取不完整。

### 建议 5: RuleChecker 的关键词匹配不处理同义词

**问题**: "贾维斯" 和 "AI" 可能是同一个实体，但 RuleChecker 不会关联。
如果摘要里写了 "AI 助手" 而快照里是 "贾维斯"，会被判 lost。

**缓解**: 这是 RuleChecker 的已知限制，LLMChecker 能处理这种情况。

---

## ✅ 设计正确的部分

1. **平台探测期设计**: 先等 60 秒看平台是否自己处理，避免与 OpenClaw auto-compaction 冲突
2. **compact 锁**: 防止多个 Mark42 实例同时 compact（虽然有竞态，但 TTL 兜底）
3. **冷却期**: 30 分钟内不重复 compact，避免摘要膨胀
4. **已含 compaction 摘要检查**: 避免对已 compact 的 session 再 compact
5. **Session Fence**: compact 前后记录文件状态，检测外部篡改
6. **ArcLock 接口设计**: audit 作为独立锁扣，可替换、可配置
7. **异步 hook**: compact 完成后异步触发审计，不阻塞主流程
8. **降级链**: LLMChecker -> RuleChecker -> 跳过
9. **报告清理**: 保留最近 20 份，自动清理旧报告
10. **连续无效检查**: 连续 3 次压缩无效升级 broker 事件

---

## 修复优先级

| 优先级 | 问题 | 修复难度 |
|--------|------|----------|
| P0 | SummaryExtractor compaction 标记全错 | 10 分钟 |
| P1 | compact 超时不一致 (320 vs 600) | 5 分钟 |
| P1 | audit hook 只在成功时触发 | 2 分钟 |
| P1 | compact 锁竞态条件 | 15 分钟 |
| P2 | OpenClaw 配置补全 | 5 分钟 |
| P2 | LLMChecker 超时 | 5 分钟 |
| P2 | 异步线程错误可见性 | 5 分钟 |
