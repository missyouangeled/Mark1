# 本地向量模型常驻方案

**目标**：消除每次语义搜索 10 秒模型加载耗时，让 L2.5 层搜索 < 1s。

**日期**：2026-06-12

---

## 现状分析

| 项目 | 数值 |
|------|------|
| 冷启动耗时 | ~12s（模型加载 10.8s + 编码 1.3s + 余弦 0.3s） |
| 热命中理想耗时 | ~2s（仅编码） |
| 模型常驻内存 | ~1.2GB（470MB FP32 模型 + PyTorch 运行时） |
| 可用内存 | 4.3GB available（7.7G 总） |
| 已有参考架构 | infos-handle-sidecar（HTTP + systemd） |

---

## 方案对比

### 方案 A：HTTP sidecar 常驻服务（推荐）

**原理**：和 infos-handle-sidecar 一样——一个 Python HTTP 服务，启动时加载模型到内存，之后接收 HTTP POST 查询返回向量搜索结果。systemd 管理生命周期 + 自动重启。

**架构**：
```
memory-search-router.py (L2.5)
  → POST http://127.0.0.1:18792/search {"query":"..."}
  → embed-sidecar.py (常驻，模型已在内存)
  → {"results":[...], "confidence": 0.78}
```

**优点**：
- 复用现有 sidecar 架构，代码模式成熟
- systemd 管理：开机自启、崩溃重启、日志 journald
- 搜索结果 < 2s
- 可随时 curl 测试
- 不修改 router 逻辑（只需改子进程调用 → HTTP 调用）

**缺点**：
- 常驻 1.2GB 内存（但 4.3GB available 够用）
- 需要 systemd service + timer 维护
- 多一个端口（18792）

---

### 方案 B：Unix socket + lazy warm-up

**原理**：不常驻，但在第一次调用时通过 Unix socket 启动并保持连接，后续请求复用同一进程。

**优点**：不占内存直到首次使用

**缺点**：
- 首次仍然是 12s
- Unix socket 调试不如 HTTP 直观
- 需要更复杂的连接池/超时管理

---

### 方案 C：进程级缓存（不改架构）❌

**原理**：在 `memory-search-router.py` 中把模型加载到模块级变量，让同一 Python 进程内的多次调用共享。

**缺点**：
- router 每次都是 `subprocess.run` 新进程，下次调用又是冷启动
- 除非 router 本身长驻，否则无效
- 不是真正的常驻

---

## 推荐：方案 A

理由：
1. 已经在生产环境有 `infos-handle-sidecar` 的先例，架构完全可复用
2. systemd 成熟稳定
3. 实现简单（一个 HTTP 服务 + 一个 service 文件 + 一行 router 改动）
4. 内存开销可接受（1.2GB 常驻，余量 3GB）

### 实施计划

| 步骤 | 内容 | 文件 |
|------|------|------|
| 1 | `scripts/embed-sidecar.py` — HTTP 服务（Flask-like 但只用标准库） | 新建 |
| 2 | `~/.config/systemd/user/openclaw-embed-sidecar.service` — systemd | 新建 |
| 3 | `scripts/memory-search-router.py` — L2.5 改为 HTTP 调用 | 修改 |
| 4 | 启用 service → 烟测 → 文档 | 验证 |

---

## 待确认

1. 1.2GB 额外常驻内存是否可接受？（当前 4.3GB available，吃掉后剩 ~3GB）
2. 是否开机自启还是按需手动启动？（建议默认 `enabled`）
3. 是否需要健康检查 endpoint？（建议带 `/healthz`）
