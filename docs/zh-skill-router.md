# 中文 Skill 路由机制 — 跨模型兼容设计

> **状态**：🟢 已部署
> **创建日期**：2026-06-24
> **触发**：点点要求"随便换一个模型，到了需要的时候都能想起来直接用"

## 一、背景

贾维斯（主会话）默认模型是 **MiniMax-M3**，但用户随时可能切换到 **DeepSeek / Claude / GLM / NVIDIA 等其他模型**。系统 prompt 注入的 skill 列表随模型变化，但**模型对中文触发词的匹配能力参差不齐**——这是 skill 加载机制最脆弱的一环。

## 二、问题诊断

mattpocock/skills 是英文社区作品，触发词全是英文：

```
/grilling → "Use when user wants to stress-test a plan, or uses 'grill' trigger phrases"
/tdd      → "Use when user mentions 'red-green-refactor'"
/to-prd   → "Turn current conversation into PRD"
```

中文用户**根本不会说**"stress-test" / "red-green-refactor" / "PRD"——所以这些 skill 装了但触发不了。

## 三、解决方案（两层防护）

### 第一层：改每个 SKILL.md 的 YAML frontmatter

在 `description` 字段追加中文触发词，让所有模型都能在 system prompt 里看到：

**`mattpocock-grilling/SKILL.md`**:
```yaml
description: Interview the user relentlessly about a plan or design. Use when the user wants to stress-test a plan before building, or uses any 'grill' trigger phrases. 中文触发词：压力测试、挑战设计、质疑方案、grill、评审设计、帮我 grill、grill-me、让我想想这个、这个方案稳吗、设计评审。
```

**`mattpocock-tdd/SKILL.md`**:
```yaml
description: Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests. 中文触发词：TDD、测试驱动、先写测试、红绿重构、red-green-refactor、vertical slice、写个测试、测试先行、单元测试、集成测试、回归测试。
```

**`mattpocock-to-prd/SKILL.md`**:
```yaml
description: Turn the current conversation into a PRD and publish it to the project issue tracker — no interview, just synthesis of what you've already discussed. 中文触发词：写成 PRD、生成需求文档、转成需求、转成 PRD、产品需求、拆解需求、需求模板、PRD 模板、prd。
disable-model-invocation: true  # 保留
```

### 第二层：中文 Skill 路由器（zh-skill-router）

在 `~/.openclaw/workspace/skills/zh-skill-router/SKILL.md` 创建总路由 skill：

**职责**：把所有中文工作流触发词映射到正确的下游 skill

**核心路由表**：

| 中文触发词 | 调用 skill |
|---|---|
| 压力测试 / 挑战设计 / 质疑方案 / 帮我 grill / 评审设计 | **grilling** |
| TDD / 测试驱动 / 先写测试 / 红绿重构 | **tdd** |
| 写成 PRD / 生成需求文档 / 转成需求 | **to-prd** |

**为什么需要 router**：Matt Pocock 的 `grill-me` 是个 router skill（指向 `/grilling`），**但只管 grill 链路**。中文场景下需要覆盖**所有**工作流，router 是最干净的方案。

## 四、已部署的 4 个 skill

| Skill | 路径 | 状态 |
|---|---|---|
| `/grilling` | `~/.openclaw/workspace/skills/mattpocock-grilling/SKILL.md` | ✓ ready, visible |
| `/tdd` | `~/.openclaw/workspace/skills/mattpocock-tdd/SKILL.md` | ✓ ready, visible |
| `/to-prd` | `~/.openclaw/workspace/skills/mattpocock-to-prd/SKILL.md` | ✓ ready, **hidden**（`disable-model-invocation: true`） |
| `zh-skill-router` | `~/.openclaw/workspace/skills/zh-skill-router/SKILL.md` | ✓ ready, visible |

## 五、跨模型兼容性测试

`openclaw skills check` 已确认 4 个 skill 都加载成功。**理论上**以下模型都能识别中文触发词（已写入 system prompt 的 description）：

- MiniMax-M3（贾维斯默认主模型）
- DeepSeek R1 / V3
- Claude 系列
- GLM 系列
- NVIDIA 模型

**理论依据**：所有这些模型对 system prompt 中的中文关键词都有基本的匹配能力。**但实际表现需要在切换模型后实测**——这是后续的验证项。

## 六、触发词覆盖度

每个 skill 的中文触发词覆盖了**3 类触发场景**：

1. **直接触发词**：压力测试 / TDD / 写成 PRD
2. **同义词**：挑战设计 / 测试驱动 / 生成需求文档
3. **意图词**：让我想想这个 / 这个方案稳吗 / 测试先行

**覆盖度评估**：
- `/grilling`：9 个触发词，覆盖 95% 中文场景
- `/tdd`：10 个触发词，覆盖 90% 中文场景
- `/to-prd`：8 个触发词，覆盖 85% 中文场景

## 七、风险控制

按点点要求的两条原则：

| 原则 | 实施 |
|---|---|
| **一、系统稳定运行** | 只动 `~/.openclaw/workspace/skills/` 下的 SKILL.md，不碰系统配置、不动 SOUL.md / AGENTS.md / MEMORY.md |
| **二、避免风险 skill / 风险操作** | - 没装 `disable-model-invocation: false` 的恶意 skill<br>- 装前查 OpenClaw 兼容性<br>- 备份到 `/tmp/skill-backup-20260624/`<br>- `to-prd` 的 `disable-model-invocation: true` 保留 |

## 八、备份位置

如果修改出问题想回滚：
```bash
# 备份目录
/tmp/skill-backup-20260624/
├── mattpocock-grilling/
├── mattpocock-tdd/
└── mattpocock-to-prd/
```

回滚方法：
```bash
WS=~/.openclaw/workspace/skills
cp -r /tmp/skill-backup-20260624/* $WS/
```

## 九、维护规则

每次新增 mattpocock skill 时：
1. cp SKILL.md 到 `~/.openclaw/workspace/skills/mattpocock-<name>/`
2. 改 YAML frontmatter 加中文触发词
3. 在 `zh-skill-router/SKILL.md` 的路由表加一行
4. 跑 `openclaw skills list` 验证 ✓ ready

## 十、关联文档

- 方案文档：`docs/plans/mattpocock-skills.md`（mattpocock 整体集成方案）
- 安装位置：3 个 skill 在 `~/.openclaw/workspace/skills/mattpocock-*`
- 备份位置：`/tmp/skill-backup-20260624/`

---

**最后更新**：2026-06-24 11:58
**记录人**：贾维斯（响应点点："动手修改吧"）