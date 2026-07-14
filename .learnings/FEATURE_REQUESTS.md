# Feature Requests

Capabilities requested by user that don't currently exist.

---

## [FEAT-20260714-001] missing-capability-request

**Logged**: 2026-07-14T05:09:31.226Z
**Priority**: medium
**Status**: pending
**Area**: docs

### Requested Capability
1 状态增加除了对外"还能用",还必须主动上报 "我现在在降级" 给主AI 看到一次,主AI 可以继续用但心里有数。2 我好奇为什么不能让它自由探索。3 两个思路组合:契约测试定基础、信号定运行态。4 改成 主AI 先在备件池找替代 → 启动了替代再删 → 万一没有备件,标记槽位为空 5 按照常见做法:设备自己报(硬件指纹 + runtime 探针),主AI接收但不深信,启动后再用真实指标二次校准。6 不，在互联网上我看过 把OpenClaw装进非常简陋的一个芯片里的。我坚信是可以只保留对话模式的。如果不行 那就一定是模块不够独立。7 "模块主动汇报健…

### User Context
User explicitly asked for a concrete capability or workflow the assistant does not reliably have yet.

### Complexity Estimate
medium

### Suggested Implementation
Evaluate whether this capability belongs in agent workflow, hook automation, or a dedicated skill update.

### Metadata
- Frequency: first_time
- Related Features: self-improvement
- Session Key: agent:main:dashboard:9d7566a0-122a-42c0-b8a6-9082de455fa7

---
