# ChatTTS On-Demand Daemon

按需启动 + 空闲自动退出的 ChatTTS 热启动方案。

## 架构

```
用户请求 ──→ chattts-on-demand.sh ──→ chattts-daemon.sh (client)
                                            │
                                            ▼
                                    Unix socket (AF_UNIX)
                                            │
                                            ▼
                                    chattts_daemon.py (server)
                                      ├── ChatTTS model (pre-loaded)
                                      ├── idles 300s → auto-exit
                                      └── auto-started on first request
```

**设计原则：**
- **非常驻**：不随系统/OpenClaw 启动，首次调用时自动拉起
- **自动回收**：300 秒空闲后进程退出、释放 ~2GB 内存
- **过期清理**：生成超过 4 小时的 reply 音频会自动删除
- **兼容稳定**：与 `chattts-stable` 共用同一套资产链和补丁
- **零侵入**：不改 OpenClaw gateway 配置，不影响主会话

### 2026-05-09 Stale PID 修复

**问题**：daemon 空闲自动退出时（`os._exit(0)` 路径）会清理 `.sock` 和 `.lock` 文件，但**不会清理 `.pid` 文件**。
这导致后续 `--status` 总是报告 ``PID file exists but process is dead (stale PID)``。

**修复**：
1. `chattts_daemon.py`：新增 `_cleanup_all_artifacts()` 函数，统一清理 PID / socket / lock 三个文件；
   在 idle timeout watcher 退出前、`main_async` finally 块中、以及 `KeyboardInterrupt` 处理中都调用它。
2. `chattts-daemon.sh`：`request` 处理前先检查并清理 stale PID；restart 时也清理 PID 文件。

**验证结果**（2026-05-09）：
- ✅ 空闲退出后所有三个 artifacts（`.pid`, `.sock`, `.lock`）全部清除
- ✅ `--status` 稳定返回 ``Daemon not running``
- ✅ 空闲退出后再次请求仍能 auto-start daemon 并正常合成
- ✅ 模拟 stale PID 的 `--status` 报告后自动清理干净
- ✅ 模拟 stale PID 后的 `--request` 也能正常恢复（先清理 stale、再 auto-start、再合成）

## 文件

| 文件 | 作用 |
|------|------|
| `chattts_daemon.py` | 核心 daemon，加载模型 + Unix socket 服务 |
| `chattts-daemon.sh` | daemon 生命周期管理（start/stop/status/request） |
| `chattts-on-demand.sh` | **用户接口** CLI，推荐使用 |
| `cleanup-old-audio.sh` | 清理超过 4 小时的生成语音 |
| `README.md` | 本文档 |

## 使用

### 基础用法（推荐）

```bash
cd ~/.openclaw/workspace

# 合成语音（首次自动启动 daemon）
bash tools/chattts-on-demand/chattts-on-demand.sh \
  --text "你好，你在吗？"

# 指定输出路径和预设音色
bash tools/chattts-on-demand/chattts-on-demand.sh \
  --text "换一个声音。" \
  --out /tmp/output.wav \
  --preset preset-1

# 列出可用音色
bash tools/chattts-on-demand/chattts-on-demand.sh --list-presets

# 强制冷启动（不用 daemon，排障用）
bash tools/chattts-on-demand/chattts-on-demand.sh --text "测试" --cold

# 停止 daemon
bash tools/chattts-on-demand/chattts-on-demand.sh --stop

# 查看状态
bash tools/chattts-on-demand/chattts-on-demand.sh --status
```

### 从 OpenClaw 主会话调用

在任意工具/技能脚本中：

```bash
CHATTTS="$HOME/.openclaw/workspace/tools/chattts-on-demand/chattts-on-demand.sh"
"$CHATTTS" --text "后台语音回复。" --out /tmp/reply.wav
```

### 过期语音清理

默认会删除 `tmp/voice-replies/` 下超过 4 小时的以下文件：

- `chattts-ondemand-*`
- `voice-reply-*`

可手动运行：

```bash
# 正常清理
bash tools/chattts-on-demand/cleanup-old-audio.sh

# 预演（不删除）
bash tools/chattts-on-demand/cleanup-old-audio.sh --dry-run
```

也支持通过环境变量修改保留时长：

```bash
OPENCLAW_VOICE_REPLY_RETENTION_HOURS=6 \
  bash tools/chattts-on-demand/cleanup-old-audio.sh
```

### 手动管理 daemon

```bash
# 启动（默认 300s 空闲超时）
bash tools/chattts-on-demand/chattts-daemon.sh start

# 启动并指定更长的空闲超时
nohup $VENV_PYTHON tools/chattts-on-demand/chattts_daemon.py \
  --idle-timeout 600 > /dev/null 2>&1 &

# 发送原始 JSON 请求（通过 stdin）
echo '{"text":"你好","out":"/tmp/test.wav","preset":"preset-1"}' | \
  bash tools/chattts-on-demand/chattts-daemon.sh request
```

## 性能数据（本机 CPU，无 CUDA）

| 场景 | 耗时 | 说明 |
|------|------|------|
| 首次冷启动（含模型加载） | ~12-15s | 导入 torch + ChatTTS + 加载模型 + 合成 |
| 热启动（短句 ~8 字） | ~4.5s | daemon 已运行，纯合成 + 套接字通信 |
| 热启动（长句 ~25 字） | ~9.8s | 纯合成时间 |
| 空闲自动退出 | ~300s | 可配置，默认 5 分钟 |

> 注：合成速度受 CPU 算力限制。`~/chattts-stable` 和 daemon 模式在相同文本下产出相同声线。

## 风险说明

### 已知风险

1. **内存占用**：ChatTTS 加载后占用 ~1.5-2GB RAM。空闲 5 分钟后自动释放。
   - 确认方法：`ps -o pid,rss,cmd -p $(cat ~/.openclaw/workspace/tmp/.chattts-daemon.pid)`

2. **串行处理**：daemon 单线程处理请求。连续快速请求会排队。
   - 若一个请求耗时 10s，第二个需要等 10s。

3. **稳定性**：ChatTTS 内部仍有已知 `warnings`（UNEXPECTED/MISSING keys）。daemon 继承了与原 `chattts-stable` 相同的补丁方案。
   - 如果 daemon 崩溃，`chattts-on-demand.sh` 会自动回退冷启动。

4. **套接字并发**：Unix socket 每次处理一个完整 JSON-NL 请求。未使用 HTTP 或线程池。

### 低风险项

- ✅ **不影响 OpenClaw**：纯用户级进程，无 gateway 配置修改
- ✅ **可回退**：停掉 daemon + 删掉目录即可回退到 `chattts-stable` 原模式
- ✅ **声线一致**：复用同一套 `chattts-stable` 资产链和 `spk_emb`
- ✅ **无写权限问题**：所有路径在 `~/` 下
- ✅ **无外部网络请求**：纯本地推理

## 回退方案

如需彻底回退到原 `chattts-stable` 模式：

```bash
# 1. 停止 daemon
bash tools/chattts-on-demand/chattts-on-demand.sh --stop

# 2. 确认不再运行
bash tools/chattts-on-demand/chattts-daemon.sh status

# 3. 清理状态文件
rm -f ~/.openclaw/workspace/tmp/.chattts-daemon.*

# 4. 继续使用原稳定入口
~/.local/share/openclaw-voice-venv311/bin/python3 \
  ~/.openclaw/workspace/skills/chattts-stable/scripts/chattts_stable.py \
  --text "正常模式。" --out /tmp/test.wav
```

## 集成到 OpenClaw

建议通过 taskflow 或技能脚本异步调用，示例 Python 封装：

```python
import subprocess, json, tempfile, os

def chattts_tts(text: str, preset: str = "default") -> str | None:
    """Synthesize text via on-demand daemon. Returns path to output file."""
    sh = os.path.expanduser(
        "~/.openclaw/workspace/tools/chattts-on-demand/chattts-on-demand.sh"
    )
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_path = f.name
    result = subprocess.run(
        [sh, "--text", text, "--out", out_path, "--preset", preset],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode == 0:
        return out_path
    return None
```
