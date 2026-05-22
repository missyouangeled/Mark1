# 贾维斯自进化方案：self-improvement + capability-evolver 融合

> 状态：待开工 | 日期：2026-05-22
> 前置：语音架构重构（排在这后面）

---

## 一、现状问题

### self-improvement skill 现状

| 文件 | 行数 | 问题 |
|------|------|------|
| ERRORS.md | 10,452 | hook 自动误报堆积，几乎无价值 |
| LEARNINGS.md | 936 | 大部分未 review |
| FEATURE_REQUESTS.md | 5 | 基本空的 |
| INBOX.md | 105 | 大量误抓（用户情感表达被当低置信度信号） |

**核心缺陷：只会"记"，不会"做"。** 记了一堆错误和纠正，但从不自动提炼行动、写修复脚本、更新行为规则。最终变成垃圾场。

### capability-evolver 的长处

- **GEP 协议**（Genome Evolution Protocol）：扫描运行历史 → 生成结构化改进提案 → 按协议执行 → 审计追踪
- 区别：self-improvement = 记笔记；capability-evolver = 自己动手改
- 但"Mad Dog Mode"全自动执行风险大，不适合生产机

---

## 二、融合方案

**在现有 self-improvement 基础上加一条"进化腿"，不另起炉灶。**

```
现有 self-improvement（记笔记）
  │
  ▼
新增: 自进化协议（从笔记 → 行动）
  │
  ├── 定期扫描 .learnings/ 里的 pending 条目
  ├── 对重复 3 次以上的模式 → 自动生成修复脚本/规则
  ├── 对用户明确请求的能力 → 自动调研 + 写 skill 草稿
  ├── 所有自动改动先走 --review 模式（用户确认后才生效）
  └── 每次进化写入审计日志（可回滚）
```

---

## 三、四项改进

### 3.1 自动清理

- 收紧 hook 抓取规则，减少误报
- 清理 ERRORS.md 里 10,000+ 行历史误报
- INBOX.md 里的情感表达误抓加入白名单排除

### 3.2 周期进化 cron

- 每天一次（建议凌晨 3:00 或用户下班后）
- 扫描 `.learnings/` 的 pending 条目
- 尝试提炼成行动建议
- 输出进化报告到 `tmp/evolution-report-YYYY-MM-DD.md`

### 3.3 晋升自动化

- 发现 `Recurrence-Count >= 3` → 自动生成晋升草稿
- 草稿写入 `tmp/promotion-drafts/`，等用户确认
- 确认后自动更新 AGENTS.md / TOOLS.md / SOUL.md

### 3.4 能力缺口自动调研

- FEATURE_REQUESTS.md 有新条目时 → 自动搜 ClawHub
- 找到现成 skill → 输出安装建议
- 没找到 → 输出"可能需要自建"标记

---

## 四、不做的事

| 不做 | 原因 |
|------|------|
| ❌ Mad Dog Mode 全自动执行 | 生产机，agent 不能自己改自己不经人审 |
| ❌ 替换 self-improvement | 它的分类体系和晋升机制设计得好，只是缺执行腿 |
| ❌ 安装 capability-evolver 原版 | GEP 协议太重，且依赖 EvoMap 网络注册 |

---

## 五、实施路线

| 步骤 | 内容 | 预估 |
|------|------|------|
| 1 | 清理 .learnings/ 历史垃圾 + 收紧 hook 规则 | 小 |
| 2 | 写进化扫描脚本 `scripts/openclaw-evolution-scan.py` | 中 |
| 3 | 配 cron 每日执行 | 小 |
| 4 | 晋升自动化草稿生成 | 中 |
| 5 | 能力缺口 ClawHub 搜索集成 | 小 |

排在语音架构重构之后开工。

---

## 六、参考

- 现有 skill：`~/.openclaw/workspace/skills/self-improving-agent/SKILL.md`
- capability-evolver：ClawHub 35k 安装量，`evomap/evolver`，GEP 协议
- 深度研究报告：`gist.github.com/SQLOPTIMISE/2ca9313bb11e37c573aae053b8f0f80d`
