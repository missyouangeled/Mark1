# Mark42 Quick Start（2026-07-01）

> 目标：让第一次接手 Mark42 的人，在 **3~10 分钟内确认系统能跑**。
> 不承诺“一键安装到陌生机器”，只承诺“先跑起来、先验活”。

---

## 最小步骤

在仓库根目录执行：

```bash
python3 scripts/mark42.py --init
python3 scripts/mark42.py --config
python3 scripts/mark42.py armor --check
python3 scripts/mark42.py status --json
```

### 成功判据

- `--init` 不报错，能创建 state 目录
- `--config` 能打印版本、阈值、模型表
- `armor --check` 能返回 usagePercent / summary
- `status --json` 能输出完整 JSON，而不是 traceback

---

## 本机 7/01 实测基线

```text
316 passed, 8 skipped, 0 fail
coverage: 53.3%
```

`python3 scripts/mark42.py status --json` 实测包含：

- armor usagePercent
- engine activeLoops / loops
- heavy activeTasks
- logs rotationCount
- broker 事件数
- scratch 目录统计

---

## 前台启动整套守护

```bash
python3 scripts/mark42.py assemble
```

这会：

- 拉起 `armor --guard`
- 拉起 `engine --daemon`
- 前台监护子进程
- `Ctrl+C` 时优雅收尾

适合开发/调试，不等于安装。

---

## 为什么这份文档先于 install.sh

因为当前 service / shell 仍带机器专用硬编码：

- `/home/missyouangeled/.openclaw/workspace/...`
- `/home/missyouangeled/.local/state/openclaw/mark42/...`
- `openclaw-gateway.service` 依赖

所以当前阶段：

- ✅ Quick Start 可交付
- ❌ 通用 install.sh 不可诚实交付

---

## 写 install.sh 前必须先修

1. service 模板参数化
2. bootstrap/watchdog 路径参数化
3. Gateway / openclaw 可用性检测
4. 开发模式 vs 生产守护模式分离

---

## 建议阅读顺序

1. `README.md`
2. `docs/design/mark42-商品化路线图.md`
3. `docs/design/mark42-更新日志.md`
4. `scripts/mark42.py --help`
5. `python3 -m pytest scripts/tests/ --no-cov -q`
