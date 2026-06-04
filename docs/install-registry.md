# 📦 安装注册表 — Install Registry

> 本文件记录所有工具/Skill/扩展的安装、卸载记录。
> 每次安装或卸载，按时间倒序追加，无论换什么模型都能读取。
> 格式：时间、名称、来源/地址、依赖、安装路径、是否成功、备注。

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
