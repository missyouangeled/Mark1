# Mark42 开发经验

> 不从 bug 里学东西，bug 就白修了。
> 每次审查/烟测后，把根因和教训记下来，下一次写代码前先看一遍。

---

## 一、整体数据

| 轮次 | 日期 | 问题数 | 红色(🔴) | 黄色(🟡) |
|:---|:---|:---:|:---:|:---:|
| v2.2 首次烟测 | 2026-06-17 | 5 bug | 0 | — |
| v2.3 #2 真跑排查 | 2026-06-17 | 6 bug | 2 | — |
| v2.3 #3 全线审查 | 2026-06-17 | 9 | 2 | 7 |
| **合计** | | **20** | **4** | **7** |

---

## 二、根因六类

把 20 个问题按根因归类，不是按表面现象归类。

### 第 1 类：对输入格式假设错误（3 个）

**v2.2 #1**：`_read_session_tail` 返回 0 条消息 → OpenClaw JSONL 格式是 `{"type":"message","message":{"role":"user"}}`，我当成平级结构去读  
**v2.2 #2**：content 提取失败 → content 是 `[{type:"text",text:"..."}]` 数组，我当字符串处理  
**v2.2 #4**：daemon 无条件创建 watch Loop → 事件里有 `heavy.task.started` 就创建，没验证文件是否真的存在

**教训**：
- 消费任何外部数据前，先 `print` 3 条真实样本，确认结构
- 写 `if event == "X"` 之前，问自己：如果 event 为空/不存在/格式错了，会崩吗？

### 第 2 类：变量/状态初始化遗漏（2 个）

**v2.2 #3**：`task-watch` 在无活跃任务时 `UnboundLocalError`（pending/failed 变量未初始化）  
**v2.2 #5**：`task-watch-2` 残留 → 由已不存在的测试任务触发创建，但从未被清理

**教训**：
- 函数开头先声明 `pending = 0; failed = 0`，再在 if/else 里赋值
- 消费外部事件后，检查是否有死状态需要清理

### 第 3 类：修改时只修了一半（2 个）

**v2.3 #2.1**：CLI 手动 `engine --run` 后 cycle/lastRun 不持久化 → 改 daemon 时让 `engine_run_loop` 不自己保存，但忘了给 CLI 路径留 `persist=True`  
**v2.3 #2.2**：daemon 的 loops 修改被丢弃 → `engine_run_loop` 内部自己 `_load_loops`，daemon 传入的引用从未被改动

**教训**：
- 改任何函数签名/行为前，先 `grep -rn "函数名"` 找到所有调用方
- 改完后反搜确认每个调用方都知道了语义变化

### 第 4 类：资源管理粗放（3 个）

**v2.3 #2.3**：`assemble()` 每次启动泄漏 4 个 fd → `open("a")` 创建的 stdout/stderr 对象永不 `.close()`  
**v2.3 #2.5**：flock 锁文件用 `"w"` 模式 → 每次 truncate 丢失元数据  
**v2.3 #2.6**：子进程未设 `start_new_session` → Ctrl+C 可能穿透

**教训**：
- `Popen(stdout=open(...))` 必须在父进程 track 并 close
- 锁文件用 `"a"` 模式不 truncate
- 子进程默认 `start_new_session=True`

### 第 5 类：阻塞调用未隔离（1 个）

**v2.3 #2.4**：daemon broker 循环内 `armor_compress()` 可能阻塞 45 秒 → LLM API 同步调用卡住整个 daemon

**教训**：
- daemon/事件循环内**禁止同步 IO**
- 所有网络调用、大文件读写必须走子进程或异步

### 第 6 类：编码健壮性细节（9 个，来自审查报告）

**A1**：token 估算用固定常数 14KB/KToken → 改为前 100 行采样 `avg_chars_per_line / 2.5`  
**C1**：文件扫描规则三处重复 → 抽取 `_list_project_files()`  
**B3**：health-watch 用 `df -h`/`free -h` 解析 → 改用 `shutil.disk_usage()` + `/proc/meminfo`  
**C3**：batch_size 公式里有魔法数字 200 → 加注释说明  
**B2**：Loop 模板编号边界不清晰 → 同名活跃 Loop 提示"将被覆盖"  
**C2**：execute 脚本 TODO 占位 → 加 `--command` 参数  
**B1**：daemon 无心跳检测 → 加 `daemon-heartbeat.json`  
**D1**：config 版本号写死 2.2 → 更新为 2.3  
**—**：`_load_json` 在 utils/config 重复 → 确认是有意的防循环导入架构，保留

**教训**：
- 能用 Python 标准库就不要 `os.popen` 解析外部命令输出
- 三处重复的逻辑必须抽公共函数
- magic number 必须加注释
- 估算算法不要用单一固定常数，要用采样
- TODO 占位符要有可替换的参数入口
- daemon 必须有外部可观测的心跳
- 版本号不要硬编码在多处

---

## 三、开发自检清单

每次写 Mark42 模块代码时，过一遍：

1. **外部数据**：读了真实样本吗？
2. **变量初始化**：所有分支都有默认值吗？
3. **调用方**：改签名前 grep 全仓了吗？
4. **fd/锁**：flock `"a"`、fd close、`start_new_session` 设了吗？
5. **阻塞**：循环内有网络 IO 吗？异步了吗？
6. **外部命令**：能用标准库替代 `os.popen` 吗？
7. **重复代码**：三处一样该抽函数吗？
8. **magic number**：有注释说明来历吗？
9. **可观测**：daemon 有外部可查的心跳吗？
10. **版本号**：所有 init 入口都写对了版本吗？

---

## 四、防止复发规则

| 规则 | 触发条件 |
|:---|:---|
| 改函数签名 → `grep -rn` 全仓 | 任何函数签名/返回值/语义变化 |
| 加新事件消费 → 先验证文件存在 | 任何 `if event == "X"` 或 broker 扫描 |
| 打开文件/进程 → 确认 close 时机 | 任何 `open()` 或 `Popen()` |
| daemon 循环加新逻辑 → 检查是否同步 IO | 任何 daemon tick 内的新增代码 |
| 消费外部格式 → 先打真实样本 | 任何 JSONL/API/命令输出消费 |
| 新增常量/公式 → 写注释说明来历 | 任何非显而易见数字或公式 |

---

*此文件由 Mark42 v2.3 全线审查驱动创建，今后每次修复 bug 或审查发现新问题后更新。*
