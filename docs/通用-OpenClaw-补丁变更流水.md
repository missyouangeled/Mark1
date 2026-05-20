# OpenClaw 补丁变更流水

- 适用机器：通用
- 系统 / OS：通用
- 文档类型：按时间追加的修改 / 补丁 / 功能变更流水

## 用途

这份文档记录**每次实际改了什么**，重点回答：

- 这次改动发生在什么时候
- 改的是功能、补丁、修复还是维护流程
- 影响范围是什么
- 改了哪些文件
- 是否已经同步到补丁注册表 / 重建清单 / 自检清单

它和其它文档的关系：

- `docs/通用-OpenClaw-补丁注册表.md`：记录**正式补丁清单**
- `docs/通用-OpenClaw-补丁重建清单.md`：记录**升级后怎么重建**
- `docs/通用-OpenClaw-升级后自检清单.md`：记录**升级后怎么快速验**
- `docs/通用-OpenClaw-非正式修改备忘录.md`：记录**未进入正式补丁体系的临时/手工/外部修改**
- **本文件**：记录**这次具体动了什么**

## 记录规则

1. 只要发生了实际修改、修补、接链路、打补丁、改脚本、改配置、改文档，就应追加一条流水。
2. 若本次改动已经达到“正式补丁”标准，还要同步更新注册表 / 重建清单 / 必要时更新自检清单。
3. 若只是一次性排查、临时试验、未形成稳定入口，可只记流水，不强行登记为正式补丁；若它对后续排查仍重要，再补进 `docs/通用-OpenClaw-非正式修改备忘录.md`。

---

## 2026-05-20 08:18:44 CST (+08:00) — 建立补丁自动留痕模式

- 类型：process
- 适用范围：通用
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 新增补丁变更流水文档，用来按时间记录每次实际改了什么
- 新增 openclaw-change-log 脚本，后续修改任务可直接追加流水
- 把自动留痕规则写进 AGENTS.md / TOOLS.md / MEMORY.md，作为默认工作模式
- 验收 / 验证：
- python3 -m py_compile scripts/openclaw-change-log.py 通过
- 已创建 memory/daily/2026-05-20.md 记录本轮变更
- 相关文件：
- `AGENTS.md`
- `MEMORY.md`
- `TOOLS.md`
- `docs/通用-OpenClaw-补丁变更流水.md`
- `memory/daily/2026-05-20.md`
- `scripts/openclaw-change-log.py`

## 2026-05-20 08:19:16 CST (+08:00) — 补齐 OpenClaw 补丁台账覆盖范围

- 类型：patch
- 适用范围：通用
- 补丁注册表：已更新
- 重建清单：已更新
- 升级后自检清单：未更新
- 结果摘要：
- 补丁注册表新增 Linux resume-watch、supervisor 状态层、local-health 诊断层、Windows battery policy 等条目
- 补丁重建清单新增 sidecar / unified proxy / supervisor / local-health / resume-watch / Windows battery policy 的重建步骤
- 把推荐重建顺序改成先补自动重打入口，再补 broker / sidecar / proxy，再补各类 watcher/service，最后补机器专用 patch
- 验收 / 验证：
- 已读取 docs/通用-OpenClaw-补丁注册表.md，确认新增条目落盘
- 已读取 docs/通用-OpenClaw-补丁重建清单.md，确认新增步骤与顺序落盘
- 相关文件：
- `docs/通用-OpenClaw-补丁注册表.md`
- `docs/通用-OpenClaw-补丁重建清单.md`

## 2026-05-20 08:24:41 CST (+08:00) — 接入非正式修改备忘录并补入掌机历史修复

- 类型：maintenance
- 适用范围：通用
- 补丁注册表：不适用
- 重建清单：不适用
- 升级后自检清单：不适用
- 结果摘要：
- 新增 docs/通用-OpenClaw-非正式修改备忘录.md，用来记录临时修复、手工补配、外部修改等未进入正式补丁体系的条目
- openclaw-change-log 脚本新增 memo 子命令，可直接追加非正式修改备忘录
- 已补入掌机微信二维码登录 Content-Length 兼容修复、微信通道手工补配回写、watchdog 保持卸载状态三条历史记录
- 验收 / 验证：
- python3 -m py_compile scripts/openclaw-change-log.py 通过
- 已读取 docs/通用-OpenClaw-非正式修改备忘录.md，确认三条条目落盘
- 相关文件：
- `AGENTS.md`
- `MEMORY.md`
- `TOOLS.md`
- `docs/通用-OpenClaw-补丁变更流水.md`
- `docs/通用-OpenClaw-非正式修改备忘录.md`
- `memory/daily/2026-05-20.md`
- `scripts/openclaw-change-log.py`
