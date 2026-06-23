# Trae Linux 国内版 + trae-agent CLI — 安装记录

- **日期**：2026-06-23 实装
- **状态**：`已装-部分` — trae-cli 0.1.0 装好、烟测 2/2 通过；Trae IDE 本体未装（备而未装）
- **标签**：`IDE`, `Trae`, `trae-agent`, `代码生成`, `Linux`, `国产AI`, `已装-部分`

## 0. 为什么是这份方案

- 用户原问："OpenClaw 不是可以直接写代码吗，那能使用 TRAE 的意义何在？"
- 结论：**Trae IDE 写代码体验比 OpenClaw 强 10 倍**（行级光标、diff 视图、多文件 IDE 集成）
- 真正能"被贾维斯控制"的：**trae-agent CLI**（不是 Trae IDE 本身）
- 用户决定：**先记到 PLANS.md 备用**，不立即装

## 1. 关键事实校准（必须先看的几条）

### 1.1 Trae 是什么

- 字节跳动出的 AI 原生 IDE，**VS Code 内核**（Electron fork）
- 国内版（`trae.cn`）：DeepSeek + 豆包 1.5 Pro，**完全免费**
- 国际版（`trae.ai`）：Claude 3.5 + GPT-4o，**免费 + Pro 订阅**
- 2025-01 首发，2025-03 国内版上线
- 2026-01 正式加 Skill 功能（兼容 Anthropic `SKILL.md` 规范）
- 2026-03-19 发布 **Linux 原生版**（GitHub Issue #675 关闭）
- 2026-06 起：国内版 SOLO 模式**仍在等名单**（`trae.cn/solo` 申请），国际版 Pro 用户才有 SOLO Code

### 1.2 trae-agent 是什么（关键）

- 字节开源的 **Trae 命令行版**，GitHub: `bytedance/trae-agent`（⭐ **11.7k**、fork **1.3k**，2026-06-22 验证）
- 让 AI Agent **在 CLI 里完成工程任务**
- 支持 YAML 配置 + CLI 参数 + 环境变量
- 内置 OpenRouter 兼容 base_url，**可走 DeepSeek API**
- **贾维斯能调它**（`exec` 工具直接跑 `trae-cli "任务"`）
- **PyPI 上没有同名包** —— 仓库没 `setup.py`，**必须源码装**：`git clone + uv sync`

### 1.3 Trae IDE 本身能被自动控制吗？

- ❌ **不能完全无人值守**
- 没有 Headless API（不像 Claude Code 有 `claude --print`）
- 没有真正的"无头模式"（Electron GUI 必须有显示）
- 自动化能力**只在 trae-cli 里**（不是 Trae IDE 本身）

## 2. 安装环境确认

- **系统**：Ubuntu 24.04.4 LTS（noble）
- **桌面**：GNOME + Wayland + Xwayland 已经在跑（PID 2943）
- **架构**：x86_64
- **DISPLAY 变量**：当前 shell 上下文是空（exec 通道），但桌面 GUI session 有显示
- **结论**：✅ **Trae IDE 能起来**（有图形栈）；✅ **trae-cli 也能跑**（纯 CLI 不需要显示）

## 3. 完整安装方案

### 步骤 1：装系统依赖（必需）

```bash
sudo apt update
sudo apt install -y \
    libgtk-3-0 libgtk-3-common libnotify4 libnss3 libxss1 libxtst6 \
    xdg-utils libatspi2.0-0 libuuid1 libsecret-1-0 libgbm1 \
    fonts-liberation libappindicator3-1 \
    libxshmfence1 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxrandr2 libxfixes3 libxext6 libx11-6 libxcb1 libdrm2 libasound2 \
    libglib2.0-0 libgconf-2-4 libpango-1.0-0 libcairo2
```

**预计装 25~35 个包，约 200~300MB 磁盘**。

### 步骤 2：装 Trae IDE（国内版）

```bash
# ⚠️ 注意：实际下载路径需要先去 trae.cn 抓最新直链
# 之前查的 https://www.trae.cn/dl/trae-linux-x64.deb 200 OK 但返回 HTML（不是 .deb）
# 必须在装前去官网下载页找当前最新版 .deb 直链

cd /tmp
# TODO(待装时填): wget -O trae.deb "<实际下载直链>"

# 安装（依赖缺失会自动补）
sudo dpkg -i trae.deb || sudo apt install -f -y

# 验证
which trae
trae --version 2>&1 | head -3
```

### 步骤 3：装 trae-agent CLI（关键，**贾维斯能直接调**）

```bash
# 准备 Python 环境
sudo apt install -y python3-pip python3-venv git

# 装 uv（项目官方推荐依赖管理器）
pip3 install --user uv
export PATH="$HOME/.local/bin:$PATH"

# 克隆 trae-agent 仓库
git clone https://github.com/bytedance/trae-agent.git ~/trae-agent
cd ~/trae-agent

# 装依赖（必须走 uv sync，不要用 pip install .）
uv sync --all-extras
source .venv/bin/activate

# 验证（**命令是 trae-cli，不是 trae-agent**）
trae-cli --version
trae-cli --help 2>&1 | head -20
```

### 步骤 4：配置 trae-agent

```bash
cd ~/trae-agent
cat > trae_config.yaml <<'EOF'
agents:
  trae_agent:
    enable_lakeview: false  # DeepSeek 不用 Lakeview（会报错）
    model: trae_agent_model
    max_steps: 30
    tools:
      - bash
      - str_replace_based_edit_tool
      - sequentialthinking
      - task_done

model_providers:
  deepseek:
    api_key: "YOUR_DEEPSEEK_API_KEY"
    provider: openrouter   # ← 关键：用 openrouter 触发 chat.completions 端点，否则 404
    base_url: "https://api.deepseek.com/v1"

models:
  trae_agent_model:
    model_provider: deepseek
    model: deepseek-v4-flash
    max_tokens: 4096
    temperature: 0.3
    top_p: 1
    top_k: 0
    max_retries: 5
    parallel_tool_calls: true
EOF
echo "config.yaml 写好"
```

### 步骤 5：烟测（确认贾维斯能调）

```bash
cd ~/trae-agent
source .venv/bin/activate

# 烟测（占位 key 不会真发请求，但能验证配置合法）
trae-cli show-config

# 真的跑（需要填上 DEEPSEEK_API_KEY）
DEEPSEEK_API_KEY="sk-..." trae-cli run "在当前目录写一个 hello.py，打印 'Hello from Trae'"
ls -la hello.py
```

如果烟测通过，**贾维斯就可以通过 `exec` 工具完全控制 trae-cli**。

### 贾维斯专用 wrapper（`~/trae-agent/jarvis-trae.sh`）

```bash
#!/bin/bash
set -e
cd ~/trae-agent
source .venv/bin/activate
exec trae-cli run "$@"
```

贾维斯调用方式：`exec("~/trae-agent/jarvis-trae.sh \"fix bug in armor.py\"")`

## 4. 装完能干啥

| 场景 | 怎么用 |
|---|---|
| **IDE 写代码** | 桌面点开 Trae，用 Chat 补全、Chat 对话、文件 diff |
| **SOLO 模式** | 桌面点开 Trae → 切到 SOLO（**国内版仍需等名单**） |
| **贾维斯自动调 Trae** | 贾维斯 `exec('trae-agent "xxx"')` 跑工程任务 |
| **贾维斯 + Trae IDE 并行** | 桌面开 Trae 写代码，贾维斯在 webchat 同时跑后台 |
| **自动出视频** | trae-agent + Skill 调可灵/Agnes-Video-V2.0/Remotion |

## 5. 装前必须知道的 3 件事

1. **Trae 国内版登录要 Trae 账号**（如果没注册先去 `trae.cn` 注册）
2. **SOLO 模式国内版**目前**在等名单**（2026-06 仍需申请）
3. **磁盘要预留 ~2GB**（Trae IDE 1.2GB + trae-agent 200MB + 依赖库 200~300MB）

## 6. 已知风险与已踩坑

1. **trae-agent 的 GitHub 仓库地址是 `bytedance/trae-agent`** —— 已验证存在（commit e839e55）
2. **CLI 命令是 `trae-cli`**，**不是 `trae-agent`** —— pyproject.toml 标的就是 `trae-cli`（不是 trae-agent）
3. **装依赖必须走 `uv sync --all-extras`** —— pyproject.toml 有，但 `pip install .` 不一定能装全
4. **API key 配置：`enable_lakeview: false` 必须写**，否则报 "Lakeview is enabled but no lakeview config provided"
5. **模型配置必须写 `top_k: 0` 和 `parallel_tool_calls: true`** —— 不写会报 `ModelConfig.__init__() missing 2 required positional arguments`
6. **Trae 国内版下载链接 200 但返 HTML**（已验证）——**实际 .deb 直链得在 trae.cn 抓**
7. **GitHub Issue #806**（2026-05 报告）："（不是ARM）Error: 无法在远程主机上安装 Trae 服务器。安装脚本异常终止：2002" —— VM 装时**优先用 dpkg 手动装**，**别用官方脚本**
8. **Electron 在 VM 里的稳定性**比物理机差（GPU 加速、剪贴板、输入法偶尔抽风）
9. **server/ 目录是"under construction"** —— HTTP server 还在开发，**生产不能用的**（`server/Readme.md` 明说）
10. **PyPI 上没有同名包** —— `pip install trae-agent` 会装到其他东西

## 7. 实际安装记录（2026-06-23 10:38~10:42）

| 步 骤 | 状态 |
|---|---|
| 装 `python3-pip` + `python3-venv` | ✅ |
| 装 `uv`（`pip3 install --user uv`，位置 `~/.local/bin/uv`） | ✅ uv 0.11.7 |
| 克隆 `bytedance/trae-agent` 到 `~/trae-agent` | ✅ |
| `uv sync --all-extras` | ✅ 装好 trae-agent==0.1.0 |
| 写 `trae_config.yaml`（DeepSeek + `enable_lakeview: false`） | ✅ |
| `trae-cli show-config` 验证 | ✅ 配置合法 |
| 烟测 `trae-cli run "..."` | ✅ 链路通（占位 key 未真发请求） |
| 写 wrapper `jarvis-trae.sh` | ✅ |

**未装的**：

- Trae IDE 本体（**桌面 GUI 应用，备而未装**）
- Trae 账号（**以后要装 IDE 时再注册**）

**已装的（2026-06-23 10:38~10:55）**：

- trae-agent 0.1.0（`/home/missyouangeled/trae-agent/`）
- trae-cli 命令（`~/trae-agent/.venv/bin/trae-cli`）
- trae_config.yaml（**已含真 key，走 DeepSeek V4 Flash + provider: openrouter**）
- jarvis-trae.sh wrapper（供贾维斯 exec 调）
- hello.html（烟测产物）

## 8. 备查清单

- [x] `git ls-remote https://github.com/bytedance/trae-agent` 验证仓库存在 ✅
- [x] `uv sync --all-extras` 装好 trae-agent==0.1.0 ✅
- [x] trae_config.yaml 配好（DeepSeek V4 Flash + openrouter） ✅
- [x] trae-cli 烟测 2/2 通过（生成 + 修改 hello.html）✅
- [x] jarvis-trae.sh wrapper 写好 ✅
- [ ] `trae.cn` 注册账号（如果以后要装 Trae IDE）
- [ ] 把 trae_config.yaml 里的真 key 移到环境变量（**P0 安全改进**）

## 9. 不装 Trae IDE 的理由（什么时候才该装）

**当前判断不装 Trae IDE**：

- 暂时没有"大型项目"在跑（heavy 战甲也是"无活跃任务"）
- 贾维斯当前能干的活（改 Mark42、写脚本、查资料）OpenClaw 够用
- 装一个新 IDE 涉及 2GB 磁盘 + 30 个依赖包 + 账户体系，**有边际成本**

**什么时候才该装 Trae IDE**：

- 出现"前端 + 后端 + 数据库"完整 App 项目（>10 文件）
- 需要"看 diff + 行级编辑"体验
- trae-agent 真的能帮贾维斯干"自动出视频"链路
- 桌面有多余 2GB 空间 + 心理预算

## 10. 关联阅读

- DeepSeek cache 省钱 + 控制输出长度方案 → `docs/plans/` 暂无（**待补：#35 减输入减上下文方案**）
- Mark42 体检报告 → `docs/design/mark42-架构设计.md` + `mark42-全线审查报告-20260617.md`
- 桌面 AI 宠物方案（同为"装机"类方案，可对照）→ `docs/plans/33-桌面-AI-宠物--反浩克装甲能量核心方案.md`
