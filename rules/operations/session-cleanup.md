# 会话清理 操作规则

> 按需加载：当用户说"清会话" / "再清一下会话" 或需要清理时读取。
> 触发条件：用户明确表达清理意图
> ⚠️ 相关逻辑也出现在 `rules/system.md` §7 和 `rules/work.md` §12——更新任一处时同步检查另外两处。

## 默认流程

1. 核对 `sessions.json` vs 保留集
2. 清理旧的 dashboard / 旧直聊 / 僵尸 subagent 索引和 jsonl
3. 清理非保留会话的 trajectory/checkpoint/bak/reset/.deleted
4. 最后才视情况删旧备份目录

## 默认保留集

- 当前会话树（当前会话 + 父 dashboard + 关联链）
- 主会话
- 用户没要求更激进 → 不扩大

## 不碰的东西

- 当前活跃会话的核心文件
- 除非用户明确要求激进瘦身

## 完成后

- 关掉已完成的背景子任务
- 清理明显陈旧的合成会话
- 用 `openclaw sessions cleanup` 定期修剪
