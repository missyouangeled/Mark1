# 📦 安装注册表 — Install Registry

> 本文件记录所有工具/Skill/扩展的安装、卸载记录。
> 每次安装或卸载，按时间倒序追加，无论换什么模型都能读取。
> 格式：时间、名称、来源/地址、依赖、安装路径、是否成功、备注。

---

## 2026-06-18

### ✅ 安装：Agent Reach v1.5.0
- **时间**：2026-06-18 12:54 CST
- **来源**：https://github.com/Panniantong/Agent-Reach
- **安装方式**：uv venv + pip install from GitHub archive
- **安装路径**：`~/.agent-reach-venv/`（venv）+ `~/.agent-reach/`（config/token）
- **依赖**：Python 3.12、requests、feedparser、loguru、pyyaml、rich、yt-dlp、mcporter、Exa
- **前置审查**：MIT 协议、安全/隐私/兼容性全项通过
- **激活渠道**：YouTube、RSS、Exa 搜索、Jina Reader（网页）、B站（基础搜索）、OpenCLI（Twitter/小红书/Reddit 兜底后端）
- **未装**：twitter-cli（编译 OOM，OpenCLI 兜底）、小宇宙播客（需 Groq Key，用户要求删除）
- **待配置**：GitHub（需 gh auth login）、V2EX（需代理）、Twitter/小红书（需配 Cookie）
- **命令**：`~/.agent-reach-venv/bin/agent-reach` 或 `agent-reach`（需 PATH）
- **SKILL.md**：已安装到 `~/.openclaw/skills/agent-reach/` 和 `~/.agents/skills/agent-reach/`
- **备注**：5/13 渠道立即可用。需登录的平台用 `agent-reach install --channels=xxx` 解锁

---

## 2026-06-17

### ✅ 调研：3D Gaussian Splatting (3DGS)
- **时间**：2026-06-17 11:50 CST
- **触发**：点点主动搜索 GitHub 3DGS
- **调研范围**：开源仓库、零代码在线查看器、Web 渲染库
- **保存位置**：docs/reference/3d-gaussian-splatting-速查.md
- **本地克隆**：tmp/3dgs-demo/（GaussianSplats3D，因缺少 .ply 未跑通本地 demo）
- **关键链接**：https://supersplat.xyz | https://poly.cam | https://github.com/mkkellogg/GaussianSplats3D
- **状态**：已整理保存，待后续有具体用途时深入

## 2026-06-16

### ✅ 安装：Scrapling Official Skill
- **时间**：2026-06-16 11:10 CST
- **来源**：Clawhub → `clawhub install scrapling-official`
- **GitHub**：https://github.com/D4Vinci/Scrapling
- **安装路径**：`skills/scrapling-official/`（336KB）
- **依赖**：无（纯文档 Skill，不包含 Python 库本身；实际使用需 `pip install scrapling` + Playwright）
- **备注**：全栈网页抓取框架 Skill。支持反爬绕过（含 Cloudflare Turnstile）、自适应元素追踪、浏览器自动化、大规模爬虫编排、MCP Server。已登记到 SKILL_CATALOG.md。BSD-3 开源。

---

## 2026-06-10 | 老电脑（Windows 10 + GTX 1070）计算节点部署

### ✅ 安装：Python 3.12.8 完整版
- **时间**：2026-06-10 11:30 CST
- **来源**：https://mirrors.tuna.tsinghua.edu.cn/python/3.12.8/python-3.12.8-amd64.exe
- **命令**：`python-3.12.8-amd64.exe /quiet InstallAllUsers=0 TargetDir=E:\tools\python312 PrependPath=0 Include_test=0`
- **安装路径**：`E:\tools\python312\`
- **依赖**：无
- **备注**：完整版解决嵌入式 Python DLL 加载问题（PyTorch shm.dll 依赖链断裂）。未加入系统 PATH。pip 已配阿里云镜像。

### ✅ 安装：PyTorch 2.6.0+cu118
- **时间**：2026-06-10 11:40 CST
- **来源**：https://download.pytorch.org/whl/cu118/torch-2.6.0%2Bcu118-cp312-cp312-win_amd64.whl（宿主机下载后局域网拷贝到 E 盘）
- **命令**：`E:\tools\python312\python.exe -m pip install E:\tools\torch-2.6.0+cu118-cp312-cp312-win_amd64.whl`
- **安装路径**：`E:\tools\python312\Lib\site-packages\torch\`
- **依赖**：numpy, sympy, jinja2, networkx, filelock, fsspec, typing-extensions 等
- **备注**：GTX 1070 CUDA 可用，实测 1000×1000 矩阵 2ms（CPU 77ms，快 39 倍）。原尝试 cu124 版但驱动 472.84 只到 CUDA 11.4 不兼容，降级 cu118 成功。直接 SSH 下载 2.5GB 多次断流，改为宿主机下载局域网拷贝。

### ✅ 安装：numpy
- **时间**：2026-06-10 11:42 CST
- **来源**：阿里云 PyPI 镜像
- **命令**：`E:\tools\python312\python.exe -m pip install numpy`
- **安装路径**：`E:\tools\python312\Lib\site-packages\numpy\`
- **备注**：PyTorch 的 NumPy 集成所需

### 🔧 配置：SSH Server（OpenSSH）
- **时间**：2026-06-10 08:30 CST
- **操作**：启用 Windows 自带的 OpenSSH Server，设为开机自启
- **防火墙**：已放行 22 端口
- **VM 侧配置**：`~/.ssh/config` 添加 `Host old-pc` 别名（密码认证）
- **备注**：局域网直连，ping 延迟 ~7ms

### ⚠️ 已知限制：NVIDIA 驱动过旧
- **当前版本**：472.84（2021年 R470 分支，CUDA 11.4）
- **最新可用**：566.36（支持 CUDA 12.4）
- **影响**：PyTorch cu124+ 不可用，仅能用 cu118
- **更新尝试**：403 Forbidden 拦下，暂不更新
- **备注**：cu118 对当前任务完全够用

---

## 2026-05-28 | 批量卸载清理

### ❌ 卸载：google-chrome-stable
- **时间**：2026-05-28 08:40 CST
- **操作**：卸载
- **方式**：`apt purge google-chrome-stable`
- **原安装路径**：`/opt/google/chrome/`（已清理）
- **释放空间**：~423MB
- **残留清理**：`~/config/google-chrome/`、`~/.cache/google-chrome/` 已删除
- **备注**：OpenCLI 依赖 Chrome，OpenCLI 已先行卸载，故 Chrome 一并清除

### ❌ 卸载：OpenCLI (`@jackwener/opencli`)
- **时间**：2026-05-28 08:40 CST
- **操作**：卸载
- **方式**：`npm uninstall -g @jackwener/opencli`
- **原安装路径**：`~/.npm-global/lib/node_modules/@jackwener/opencli/`（已清理）
- **释放空间**：~26MB
- **残留清理**：`~/.opencli/` 配置目录已删除、`/tmp/opencli-extension/` 已删除
- **原安装原因**：应对网站登录页面设计，复用 Chrome 已登录会话态
- **卸载原因**：用户主要使用 Firefox，Chrome 用不上；Chrome 被墙无法正常登录 Google 账号

### ❌ 卸载：browser-automation Skill（软链接）
- **时间**：2026-05-28 08:40 CST
- **操作**：卸载
- **方式**：`rm ~/.openclaw/plugin-skills/browser-automation`
- **路径**：软链接指向 `openclaw` npm 包内置扩展（源文件未动）
- **备注**：用户不需要 Web 页面自动化 Skill

### 🧹 清理：npm 缓存
- **时间**：2026-05-28 08:40 CST
- **操作**：清理
- **方式**：`npm cache clean --force`
- **释放空间**：~527MB

---

## 2026-05-27 | OpenCLI & 相关尝试

### ✅ 安装：OpenCLI (`@jackwener/opencli`)
- **时间**：2026-05-27 17:31 CST
- **来源**：npm registry
- **安装命令**：`npm install -g @jackwener/opencli`
- **版本**：1.8.0
- **安装路径**：`~/.npm-global/lib/node_modules/@jackwener/opencli/`
- **依赖**：Node.js、Chrome/Chromium 浏览器、Chrome 扩展（`opencli` 扩展 ID: `ildkmabpimmkaediidaifkhjpohdnifk`）
- **是否成功**：⚠️ 部分成功（CLI + daemon 已安装，但 Chrome 扩展未加载成功）
- **备注**：GitHub 被墙无法下载扩展离线包；Chrome Web Store 需手动加载；用户未完成扩展加载

### ❌ 安装失败：browser-use (Python)
- **时间**：2026-05-27 17:48~17:55 CST
- **来源**：PyPI (`browser-use`)
- **安装命令**：`uv pip install browser-use`
- **是否成功**：❌ 失败
- **失败原因**：OOM——依赖多，机器 7.7G 内存无法完成安装（进程被 OOM killer 杀掉）
- **备注**：无残留

---

## 2026-04-03 | agent-browser

### ✅ 安装：agent-browser
- **时间**：2026-04-03 14:59 CST
- **来源**：OpenClaw Skill 注册表（slug: `openclaw-agent-browser`）
- **版本**：1.0.0（npm 包 `agent-browser@0.24.0`）
- **Skill 目录**：`~/.openclaw/workspace/skills/openclaw-agent-browser/`
- **npm 路径**：`~/.npm-global/lib/node_modules/agent-browser/`
- **安装大小**：~52MB
- **是否成功**：✅ 成功
- **依赖**：Node.js、Chrome/Chromium（用于无头浏览器自动化）
- **功能**：无头浏览器自动化（导航/填表/点击/截图/抓取）
- **状态**：🟢 仍保留

---

## 格式模板

以后新增安装记录，按以下格式追加：

```markdown
## YYYY-MM-DD | 简短标题

### ✅/⚠️/❌ 安装/卸载：工具名称
- **时间**：YYYY-MM-DD HH:MM CST
- **来源**：URL 或 registry
- **安装命令**：
- **版本**：
- **安装路径**：
- **安装大小**：
- **依赖**：
- **是否成功**：✅/⚠️/❌
- **备注**：
```

## 2026-05-28 | 卸载系统自带游戏

### ❌ 卸载：GNOME 自带游戏（3个）
- **时间**：2026-05-28 08:59 CST
- **操作**：卸载
- **方式**：`sudo apt purge -y gnome-mahjongg gnome-mines gnome-sudoku`
- **原安装路径**：`/usr/games/`、`/usr/share/applications/*.desktop`
- **释放空间**：~8.9MB + 依赖 404KB = ~9.3MB
- **残留依赖清理**：`sudo apt autoremove` 清除了 libgnome-games-support-1-3、libgnome-games-support-common、libqqwing2v5
- **是否成功**：✅ 成功
- **备注**：gamemode/gamemode-daemon 保留（系统性能工具，被 ubuntu-desktop-minimal 依赖，仅 327KB）

## 2026-05-28 | 卸载5个非必要桌面应用

### ❌ 卸载：Onboard + Pluma + gnome-power-manager + Printers 配置 + 残留依赖
- **时间**：2026-05-28 09:15 CST
- **操作**：卸载
- **方式**：`sudo apt purge -y onboard onboard-common onboard-data pluma pluma-common gnome-power-manager system-config-printer system-config-printer-common system-config-printer-udev`
- **释放空间**：56.2MB + 残留依赖 5.8MB = ~62MB
- **残留依赖清理**：`autoremove` 清了 avahi-utils / gtksourceview / python3-cups 等 9 个包
- **是否成功**：✅ 成功
- **内含**：
  - Onboard（虚拟键盘，~25MB）— 无触屏，无用
  - Pluma（MATE 文本编辑器，~27MB）— 功能偏弱，有更好替代
  - Power Statistics（电池历史统计，~300KB）— 虚拟机无电池
  - Printers（打印机配置，~1.9MB）— 不需要

## 2026-05-28 | 卸载 LibreOffice Draw + Math（连带 Impress）

### ❌ 卸载：LibreOffice Draw + Math + Impress
- **时间**：2026-05-28 09:20 CST
- **操作**：卸载
- **方式**：`sudo apt purge -y libreoffice-draw libreoffice-math libreoffice-uiconfig-draw libreoffice-uiconfig-math`
- **释放空间**：22.7MB + 残留依赖 8.2MB = ~31MB
- **连带卸载**：libreoffice-impress（PPT）因共享底层矢量图形库被一并移除
- **残留依赖清理**：`autoremove` 清了 libcdr/libfreehand/libmspub/libpagemaker/libvisio 等 6 个包
- **是否成功**：✅ 成功
- **保留**：Writer（Word）、Calc（Excel）、Common/Core 核心库
- **备注**：Draw=矢量绘图（类似Visio）、Math=公式编辑器、Impress=PPT，三者均非日常所需

## 2026-05-28 | 系统整体审计 + 三连修复

### 🔧 修复1：health-collector 误判修复
- **时间**：2026-05-28 15:37 CST
- **问题**：supervisor exit 2(warning/degraded) 被当作 crash → `return 1` → systemd FAILURE → 频繁重启循环
- **修复**：修改 `scripts/openclaw-health-collector.py`：
  - `run_sub_check` 增加 `degraded` 字段（exit 2）
  - `overall` 改为三态：OK / ⚠ DEGRADED / ❌ FAILED
  - 退出码：0(=OK+DEGRADED) / 1(=true failures only)
- **是否成功**：✅ 验证通过，exit 0 on degraded, exit 1 only on real failures

### 🔧 修复2：QMD 记忆索引重建
- **时间**：2026-05-28 15:38 CST
- **操作**：`openclaw memory index --force`
- **结果**：119/119 文件已索引，索引数据库 4.9MB
- **是否成功**：✅ 索引正常；搜索 0 结果需进一步排查 (QMD Vector:disabled)

### 🔧 修复3：ChatTTS 资产确认
- **时间**：2026-05-28 15:39 CST
- **结果**：资产在 `tmp/voice-replies/chattts-hybrid/asset/`（7文件，~325MB），完整
- **是否成功**：✅ 无问题（之前查错了目录 `tools/` → 应为 `tmp/`）

## 2026-06-04 - openclaw-unity-skill

- **时间**: 2026-06-04 10:40 ~ 10:42 GMT+8
- **来源**: LobeHub Marketplace (`openclaw-skills-openclaw-unity-skill`)
- **安装命令**:
  1. `npx -y @lobehub/market-cli register --name "贾维斯" --description "OpenClaw AI Assistant" --source open-claw`
  2. `npx -y @lobehub/market-cli skills install openclaw-skills-openclaw-unity-skill --agent open-claw`
  3. `bash scripts/install-extension.sh` (安装 gateway extension)
  4. `openclaw gateway restart`
- **版本**: v1.6.1
- **路径**: `~/.openclaw/skills/openclaw-skills-openclaw-unity-skill/`
- **扩展路径**: `~/.openclaw/extensions/unity/`
- **依赖**: `@lobehub/market-cli` (已注册 Client ID: cli_dKyyZLF3vd4smqN0pkPARTXu5T56zJeo)
- **是否成功**: ✅ 成功
- **备注**: 
  - ~100 个 Unity Editor 控制工具（场景/GameObject/Component/Material/Prefab/Shader/Texture 等）
  - `disableModelInvocation: true` - 不会自动调用，需用户显式请求
  - 需要掌机 Unity 项目安装 openclaw-unity-plugin 才能连通
  - 连接模式：HTTP（Unity Editor 侧运行 plugin HTTP server）
  - LobeHub Client 凭据保存在 `~/.lobehub-market/credentials.json`

### 本地向量语义搜索 (sentence-transformers)
- **日期**: 2026-06-12
- **来源**: HuggingFace Hub (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`)
- **模型**: paraphrase-multilingual-MiniLM-L12-v2 (118M 参数, 458MB, 384 维向量, 50+ 语言)
- **安装命令**: `uv venv --python 3.11 ~/.local/share/openclaw-embed-venv311 && uv pip install sentence-transformers torch numpy`
- **版本**: sentence-transformers 5.5.1, torch 2.12.0+cpu, numpy 2.4.6
- **路径**: 
  - venv: `~/.local/share/openclaw-embed-venv311`
  - 模型: `/mnt/data/openclaw/huggingface/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/main/`
  - 索引: `/mnt/data/openclaw/scratch/memory-embed-index/`
  - 脚本: `scripts/memory-embed-index.py`, `scripts/memory-embed-search.py`
- **依赖**: Python 3.11+, sentence-transformers, torch (CPU), numpy
- **是否成功**: ✅ 模型加载验证通过
- **备注**: 国内 HuggingFace 被墙，模型需手动下载后放入对应路径；镜像站可用于小文件下载

### embed-sidecar 常驻服务
- **日期**: 2026-06-12
- **路径**: `scripts/embed-sidecar.py`, `tools/embed-sidecar/openclaw-embed-sidecar.service`
- **端口**: 127.0.0.1:18792
- **systemd**: `systemctl --user enable openclaw-embed-sidecar`
- **内存**: ~1.3GB RSS（模型 + 索引常驻）
- **效果**: L2.5 搜索从 12s → 250ms（48x 提升）

### BaiduPCS-Go

- **时间**：2026-06-12 13:42
- **来源**：https://github.com/qjfoidnh/BaiduPCS-Go/releases/download/v4.0.1/BaiduPCS-Go-v4.0.1-linux-amd64.zip
- **安装方式**：下载预编译二进制 → 解压 → `sudo cp` 到 `/usr/local/bin/BaiduPCS-Go`
- **版本**：v4.0.1
- **路径**：`/usr/local/bin/BaiduPCS-Go`
- **配置**：`~/.config/BaiduPCS-Go/`
- **依赖**：无（Go 静态编译）
- **用途**：百度网盘命令行客户端，支持登录分享下载，主要用于绕过百度网盘客户端限速
- **备注**：登录需 BDUSS + STOKEN（从 pan.baidu.com cookie 获取）

### Gopeed（够快下载器）

- **时间**：2026-06-12 16:01
- **来源**：https://github.com/GopeedLab/gopeed/releases/tag/v1.9.3
- **安装方式**：下载 gopeed-web-v1.9.3-linux-amd64.zip → 解压到 `/opt/gopeed/` → symlink 到 `/usr/local/bin/gopeed`
- **版本**：v1.9.3
- **路径**：`/usr/local/bin/gopeed`（实际 `/opt/gopeed/gopeed-web-v1.9.3-linux-amd64/gopeed`）
- **配置**：systemd 用户服务 `~/.config/systemd/user/gopeed.service`
- **依赖**：Go 静态编译，无系统依赖
- **用途**：免费全平台下载器，支持 HTTP/BT/Magnet/ED2K，Web UI 管理
- **备注**：Web UI 地址 http://192.168.79.128:9999，下载到 /mnt/data/gopeed/downloads，16 线程并发，实测 30MB/s+

### openclaw-context-monitor (systemd timer)

- **时间**: 2026-06-15 13:20
- **来源**: 自建（上下文溢出主动防御方案 Layer 2）
- **安装命令**:
  ```bash
  cp tools/openclaw-context-monitor/openclaw-context-monitor.service ~/.config/systemd/user/
  cp tools/openclaw-context-monitor/openclaw-context-monitor.timer ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user enable --now openclaw-context-monitor.timer
  ```
- **版本**: v1.0
- **路径**: 
  - 脚本: `scripts/openclaw-context-monitor.py`
  - systemd: `tools/openclaw-context-monitor/`
  - 状态: `~/.local/state/openclaw/context-monitor/status.json`
- **依赖**: Python 3, systemd user session
- **成功**: ✅ 烟测通过
- **备注**: 每 5 分钟检查上下文使用率，70%/85%/95% 三级告警

### OpenClaw 升级：v2026.6.8 → v2026.6.9
- **日期**：2026-06-22
- **操作**：升级
- **方式**：`openclaw update`（通过 systemd-run 瞬态单元执行）
- **新增/变更**：deepseek 插件自动安装；session-utils JS 文件名变更；chat model switch 函数名 CW→sH
- **备注**：升级过程因需要在 gateway 外执行，使用 systemd-run 绕过；并行修复了 cron 模型、systemd timeout、boot-health-check

### ponytail (DietrichGebert/ponytail) — 2026-06-22 00:31 UTC
- 类型: OpenClaw Skill (ClawHub)
- 来源: https://github.com/DietrichGebert/ponytail · clawhub install ponytail
- 版本: v4.7.0
- 协议: MIT
- 子 skill:
  - ponytail (主) — clawhub 安装
  - ponytail-review / audit / debt / gain / help — 手动从 GitHub raw 下载
- 用途: AI agent 代码极简模式（YAGNI → stdlib → native → dep → 一行 → 最少）
- 备注: 与 karpathy-guidelines 共存，实测后定取舍

### OfficeCLI (2026-06-22)

- **名称**: OfficeCLI
- **版本**: v1.0.116
- **安装方式**: `curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash`
- **二进制**: `~/.local/bin/officecli`
- **Skill**: `~/.agents/skills/officecli/SKILL.md`
- **用途**: AI Agent 用 CLI 创建/读取/编辑 Word (.docx)、Excel (.xlsx)、PPT (.pptx)
- **许可**: Apache 2.0
- **备注**: 单二进制、零依赖、内置 HTML/PNG 渲染引擎。OpenClaw 自动识别安装。

### design-taste-frontend（2026-06-22）
- **来源**：`https://github.com/Leonxlnx/taste-skill`
- **类型**：前端设计 skill
- **用途**：让 AI 在做 UI/前端时避免通用模板（anti-slop），强排版/留白/字距
- **安装**：`git clone https://github.com/Leonxlnx/taste-skill skills/taste-skill`
- **状态**：✓ ready（v2 experimental）
- **配套**：v1（`design-taste-frontend-v1`）一并安装
- **触发**："做 UI"、"前端设计"、"landing page"、"redesign"

