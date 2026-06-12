# 📦 安装注册表 — Install Registry

> 本文件记录所有工具/Skill/扩展的安装、卸载记录。
> 每次安装或卸载，按时间倒序追加，无论换什么模型都能读取。
> 格式：时间、名称、来源/地址、依赖、安装路径、是否成功、备注。

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
