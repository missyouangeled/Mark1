# CPU 负载过高 — 临时处理方案

> 适用机器：公司（Linux）
> 系统：Linux (Ubuntu/GNOME)
> 最后更新：2026-06-09
> 触发条件：CPU 1min 平均负载持续 > 核心数（当前 8 核） → 即 > 8.0；或用户明确提示"CPU 负载过高"
>
> ⚠️ 此为**临时应急处理方案**，目标是让系统短期内恢复可操作状态。
> 根因修复（如内存膨胀→swap I/O）需单独排查，参考 `docs/通用-OpenClaw-升级记录.md` 中"Gateway 根因分析"相关条目。

---

## 一、核心理念：Stop → Shrink → Single

```
Stop   — 停掉非必要的（先止血）
Shrink — 清理释放资源（再减负）  
Single — 一个一个来（防止二次冲击）
```

**不要什么都不管。不要同步跑很多东西。**

---

## 二、执行清单（按顺序，不可跳过）

### Step 1 — 快速判伤（30 秒内）

```bash
# 必跑
uptime                           # CPU 负载1min/5min/15min
free -h                          # 内存 + swap
df -h / /mnt/data                # 磁盘余量
ps aux --sort=-%cpu | head -8    # top CPU 进程
```

判断标准：
- 1min 负载 > 核心数 → 是真的过载，继续 Step 2
- 1min 负载 < 核心数，但 15min 持续升高 → 即将过载，继续
- swap > 2GB 且还在增长 → 内存压力叠加，优先关大内存进程

### Step 2 — 关掉能关的（1 分钟内）

按优先级从高→低：

| 优先级 | 进程 | 命令 | 省多少 | 风险 |
|:---:|------|------|:---:|------|
| 🔴 | nautilus（文件管理器） | `killall nautilus` | CPU 50-65% | 低：GNOME 会自动重启 |
| 🔴 | gnome-text-editor/gedit | `killall gnome-text-editor` | CPU 15% + swap 100MB | 低：打开的文件内容已保存则无损失 |
| 🟡 | tracker-miner（文件索引） | `tracker3 daemon -t` | CPU 10-25% | 低：索引暂停，搜索暂时不可用 |
| 🟡 | 浏览器非活动标签 | 手动关标签（不是关浏览器） | 内存 100-200MB + swap | 低 |
| 🟢 | snapd / fwupd（后台自动更新） | `sudo systemctl stop snapd` | CPU 5-10% | 低：手动更新延后 |
| 🟢 | evince / eog 等文档查看器 | `killall evince eog` | CPU 5-10% | 低 |

**规则**：
- 关桌面应用优先于关服务
- 关用户进程优先于关系统进程
- **永远不关**：Gateway / OpenClaw核心 / 当前终端 / systemd-init
- 如果某个进程不确定能不能关 → 先记录 PID，不杀

### Step 3 — 清理临时/垃圾文件（1 分钟内）

```bash
# Python 缓存（每次跑完 python 脚本都可能有残留）
find ~/.openclaw/workspace -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find ~/.openclaw/workspace -name "*.pyc" -type f -delete 2>/dev/null

# npm 缓存
npm cache clean --force 2>/dev/null &

# systemd journal（保留最近 2 天，删除旧日志）
journalctl --user --vacuum-time=2d 2>/dev/null

# /tmp 大文件（>100MB）
find /tmp -type f -size +100M -mmin +60 -delete 2>/dev/null

# OpenClaw 旧日志（>3天）
find ~/.openclaw/logs/ -name "*.log" -mtime +3 -delete 2>/dev/null

# scratch 过期项目（>7天、无 .keep 标记）
python3 scripts/openclaw-scratch-cleanup.py --print-kept 2>&1 | tail -3
```

### Step 4 — 释放内存压力

```bash
# 清 kernel cache（安全，不会杀进程）
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches 2>/dev/null

# 如果 swap > 2GB：关掉最大的 swap 占用进程（通常是浏览器）
for pid in $(ps aux --sort=-%mem | awk 'NR>1{print $2}' | head -5); do
  swap=$(awk '/Swap:/{sum+=$2}END{print sum}' /proc/$pid/smaps 2>/dev/null || echo 0)
  [ "$swap" -gt 100000 ] && echo "PID $pid swap=${swap}KB $(ps -p $pid -o cmd --no-headers)"
done
```

### Step 5 — 恢复验证

```bash
uptime && free -h | head -2 && df -h / | tail -1
```

如果负载已回落至 < 核心数，进入 Step 6；否则重复 Step 2-4。

### Step 6 — 串行化后续操作（核心）

```
🛑 停止一切并行操作
✅ 把后续任务按优先级排成单列
✅ 一个任务完成后，验证负载 → 再启动下一个
❌ 不要再同步跑 2+ 个重任务
```

**落地规则**：
- 如果有后台分身正在跑 → 等它跑完，不要同时再开后门
- 拆分批处理 → 每批之间间隔 5-10 秒
- 每个命令执行后检查 exit code 再继续

---

## 三、`openclaw-cpu-emergency.py` 一键脚本

> 路径：`scripts/openclaw-cpu-emergency.py`
> 用途：自动执行 Step 1-5，一条命令完成判断→清理→验证

### 预设命令

```bash
# 诊断模式（只看不修）
python3 scripts/openclaw-cpu-emergency.py --diagnose

# 自动修复（Step 1-5 全自动）
python3 scripts/openclaw-cpu-emergency.py --repair

# 轻度清理（只清理缓存和临时文件，不杀进程）
python3 scripts/openclaw-cpu-emergency.py --light-clean
```

### 脚本行为

```
--diagnose:
  ✅ 打印 full status card（CPU/内存/磁盘/进程TOP5/swap大户）
  ✅ 给出建议操作（哪些可以关、省多少）
  ❌ 不做任何实际操作

--repair:
  ✅ 自动执行 Step 1-5（杀非必要进程 + 清理 + 释放内存）
  ✅ 打印 before/after 对比
  ✅ 最后输出恢复状态

--light-clean:
  ✅ 只做 Step 3-4（临时文件 + journal + kernel cache）
  ❌ 不杀任何进程
```

---

## 四、禁止事项

| ❌ 禁止 | 原因 |
|------|------|
| CPU 高负载时继续开新后台分身 | 火上浇油，可能触发 OOM Killer |
| 在清理完成前连续跑大量 python 脚本 | 每个脚本的 import 都触发 .pyc 缓存写盘 |
| 不关 nautilus 直接当没事 | nautilus 在文件多的目录下常占 50%+ CPU |
| 发现 swap 涨了不管它 | swap I/O 会连锁拖慢整个事件循环 |
| 同时跑 `npm install` + `git push` + `python3` 重任务 | 三合一 = 磁盘 IO 饱和 |

---

## 五、与监工/后台分身的协调

| 场景 | 行为 |
|------|------|
| CPU 过载，有后台分身 running | 分身继续跑（不杀），但暂停开新的 |
| CPU 过载，监工在位 | 监工保持 active，继续 3min 回报机制 |
| CPU 过载已回落，后台分身仍在 | 正常恢复，按串行化规则逐个推进 |
| CPU 过载已回落，无后台任务 | 正常，进入恢复验证 |

---

## 六、历史案例

| 时间 | 触发 | 1min 负载 | 最大 CPU 进程 | 处理 |
|------|------|:----:|------|------|
| 2026-06-09 16:33 | 用户提示 | 5.27 | nautilus 58% + gateway 93% | kill nautilus, 关 gnome-text-editor, 清 pyc 缓存, swap 从 738M 短暂升至 1.2G 后回落 |
| 2026-06-09 16:37 | 持续观察 | 4.62 | node 36% + firefox 29% | 清 journal 2天, 清 npm/npx 临时文件, swap 保持 1.1G |

---

## 七、启动链集成

- 本文件已挂入 `RULES_INDEX.md`：系统操作 → 加载本文件
- 本文件已挂入 `BOOT_INDEX.md` 按需加载表：`docs/通用-CPU负载过高临时处理方案.md`
- `openclaw-system-summary.py` 的 `--diagnose` 模式已引用本文档的判伤阈值
