# OpenClaw Control UI 黑屏应急修复

- 适用机器：通用（当前先在公司 Linux 验证）
- 系统 / OS：通用 / Linux / Windows（按当前机器实际 OpenClaw 安装路径）
- 文档类型：应急 runbook
- 最后更新：2026-06-01

## 入口

```bash
cd /home/missyouangeled/.openclaw/workspace
python3 scripts/openclaw-control-ui-emergency.py --check --print-human
```

如果只是想看机器整体状态：

```bash
python3 scripts/openclaw-system-summary.py --print-human
```

## ⚠️ 预防规则

**推送到 GitHub 后不要立刻刷新 Control UI。**

原因：推送可能会触发 Gateway 自动重启（工作区变更 → hook/watcher 检测 → 重启）。在重启中间按 F5，页面加载到一半 Gateway 还没就绪，就会黑屏。

- **等 5-10 秒**再刷新，等 Gateway 完全就绪
- **习惯做法**：推送 → 等几秒 → 再 F5
- 如果已经黑了，按下面的诊断/修复流程走

---

## 三种模式

### 1. 只诊断，不修改

```bash
python3 scripts/openclaw-control-ui-emergency.py --check --print-human
```

会检查：

- Gateway 是否 running / probe ok
- `GET /` 是否返回 Control UI HTML
- `index.html` 里的 JS / CSS / manifest / branding override 是否可访问
- `<openclaw-app>` mount 点是否存在
- `jarvis-branding-override.js` 是否存在且关键函数正常
- 模型选择器补丁标记是否存在
- broker views / sidecar / unified proxy 是否可达

### 2. 低风险修复

```bash
python3 scripts/openclaw-control-ui-emergency.py --repair --print-human
```

只做低侵入动作：

- Gateway 不可达时：`openclaw gateway restart`
- Control UI 自定义静态资源异常时：重跑 `apply-openclaw-control-ui-branding.py`
- 模型选择器补丁异常时：重跑 `apply-openclaw-session-model-selector-fix.py`
- broker views 缺失时：重建 broker views
- sidecar / unified proxy 不可达时：重启或重应用对应服务

预览不执行：

```bash
python3 scripts/openclaw-control-ui-emergency.py --repair --dry-run --print-human
```

### 3. Safe Mode：优先救回原始页面

如果黑屏怀疑是自定义 branding / 前台辅助注入导致，可以临时进入 safe mode：

```bash
python3 scripts/openclaw-control-ui-emergency.py --safe-mode --print-human
```

它会：

- 备份 `dist/control-ui/index.html`
- 从 `index.html` 移除 `jarvis-branding` 注入块
- 旁路保留 `jarvis-branding-override.js` 副本
- 不删除原始文件
- 不碰主 bundle / 不清浏览器数据 / 不新增 timer

如果只是想看会做什么：

```bash
python3 scripts/openclaw-control-ui-emergency.py --safe-mode --dry-run --print-human
```

恢复自定义注入：

```bash
python3 scripts/apply-openclaw-control-ui-branding.py
python3 scripts/apply-openclaw-session-model-selector-fix.py
```

## 浏览器侧排查顺序

脚本无法直接清理用户浏览器数据；黑屏时先按这个顺序：

1. 打开 `http://127.0.0.1:18789/`
2. `Ctrl+F5` / `Cmd+Shift+R` 强制刷新
3. 用无痕窗口打开
4. 临时禁用会注入脚本的扩展：脚本管理器、广告拦截、翻译、暗色模式插件等
5. 清理 `127.0.0.1:18789` 的站点数据：缓存、LocalStorage、IndexedDB、Service Worker
6. 打开开发者工具 Console / Network，记录第一条红色 JS 错误和失败资源 URL

## 判断结果

如果输出全是 ✅：

- 服务端与静态资源层基本正常；更可能是浏览器缓存/扩展/站点数据问题。

如果 `browser.http.index` 失败：

- 优先查 Gateway / 端口 / 反代。

如果 `browser.http.assets` 失败：

- 多半是 Control UI 静态资源缺失或缓存引用过期，先跑 `--repair`。

如果 `controlui.branding` 失败：

- 自定义注入可能异常，先跑 `--repair`；如果仍黑屏，跑 `--safe-mode`。

如果 `frontstage.*` 失败但页面能打开：

- 这是前台辅助数据层问题，不一定导致主页面黑屏；可单独修 broker / sidecar / proxy。

## 边界

- 不安装/卸载浏览器扩展。
- 不自动清理用户浏览器数据。
- 不做驱动、内核、硬件监控级操作。
- 不新增 systemd timer。
- 不把 NVIDIA 音频桥这类可选支路当成 Control UI 黑屏根因。
