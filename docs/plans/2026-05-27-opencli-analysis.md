# OpenCLI — 完整分析与使用报告

> 整理日期：2026-05-27 | 适用机器：公司（Linux）

---

## 一、OpenCLI 是什么

OpenCLI（作者 jackwener，GitHub 22.6k ⭐）是一个 **把任意网站变成命令行工具** 的框架。它的核心创新是：**复用 Chrome 已有的登录态，绕过了网站登录/验证码/风控系统**。

传统自动化工具要面对：
- 登录态管理 → 频繁掉线、需要存密码
- 验证码 → 需要 OCR / 打码平台
- 风控检测 → 自动化操作特征被识别而封号

OpenCLI 的解法：
- 你在 Chrome 里正常登录一次 → OpenCLI 通过 Chrome 扩展和 CDP 协议复用这个会话
- 没有额外登录步骤，没有密码存储，没有验证码
- 网站以为是你本人在操作，零风控

**这就是为什么它说自己是"为应对网站登录页面设计的"——它根本不碰登录流程，而是直接复用你已登录的 Chrome。**

---

## 二、架构原理

```
┌─────────────┐    CDP协议     ┌──────────────┐
│  OpenCLI    │ ◄────────────► │  Chrome 扩展  │──► 已登录的 Chrome
│  (CLI/NPM)  │                │ (Browser Bridge)│    (你的正常浏览器)
└─────────────┘                └──────────────┘
```

- Chrome DevTools Protocol（CDP）：Chrome 自带的调试/控制协议，允许外部程序操控浏览器
- Browser Bridge 扩展：在 Chrome 和 OpenCLI CLI 之间建立通信桥梁
- 本地 daemon：按需启动的小型守护进程，维持连接

---

## 三、硬件 & 依赖要求

### 运行环境
| 项目 | 要求 | 本机（公司 Linux） | 判定 |
|------|------|-------------------|------|
| **Node.js** | >= 20 | v22.22.2 | ✅ |
| **npm** | 随 Node.js | 已安装 | ✅ |
| **Chrome / Chromium** | 任意现代版本 | Google Chrome 148 | ✅ |
| **DISPLAY（桌面环境）** | 需要（Chrome 依赖图形界面） | :0 存在 | ✅ |
| **磁盘** | < 100MB | 充足 | ✅ |
| **网络** | 访问 Chrome Web Store | ⚠️ 国内网络限制 | ⚠️ |
| **GitHub** | 安装适配器/skill | ⚠️ 国内被墙 | ⚠️ |

### 软件依赖
| 依赖 | 安装方式 | 说明 |
|------|---------|------|
| `@jackwener/opencli` | `npm install -g` | 核心 CLI |
| Chrome 扩展 | Chrome Web Store | Browser Bridge 扩展 |
| AI Skill（可选） | `npx skills add` | 给 AI Agent 用的技能包 |

### 额外说明
- **不需要 Python、CUDA、GPU**
- 不需要安装额外数据库
- 100% 纯 Node.js 项目

---

## 四、下载 & 安装

### 4.1 安装 CLI

```bash
# Node.js >= 20 先决条件（本机已满足）
node --version

# 全局安装
npm install -g @jackwener/opencli
```

### 4.2 安装 Chrome 扩展

**方式 A — Chrome Web Store（推荐）**
1. 打开 Chrome
2. 访问：`https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk`
3. 点击"添加到 Chrome"

**方式 B — 手动安装（国内网络受限时）**
1. 从 GitHub Releases 下载 `opencli-extension-v{version}.zip`
2. 解压
3. Chrome 地址栏输入 `chrome://extensions`，开启"开发者模式"
4. 点击"加载已解压的扩展程序"，选择解压目录

### 4.3 验证安装

```bash
opencli doctor
opencli list               # 查看所有可用命令
opencli bilibili hot --limit 5   # 测试 B站热门
```

---

## 五、核心能力

### 5.1 直接使用现成适配器（87+ 平台）

开箱即用，不需要任何配置：

| 类别 | 支持的平台 |
|------|-----------|
| **中文平台** | B站、知乎、小红书、抖音、微博 |
| **海外平台** | Twitter/X、Reddit、YouTube、HackerNews |
| **学术** | arXiv、Google Scholar |
| **开发** | GitHub、npm、Docker Hub |
| **内容** | Medium、Substack |

命令格式：
```bash
opencli   <平台>   <操作>   [参数]
opencli bilibili hot --limit 10 -f json    # B站热门，JSON 输出
opencli zhihu hot -f yaml                   # 知乎热榜
opencli xiaohongshu feed                    # 小红书推荐流
```

### 5.2 让 AI Agent 操控浏览器

给 AI Agent（Claude Code、Cursor 等）安装 `opencli-browser` skill 后，AI 可以：
- **导航**到任意 URL（使用你的已登录 Chrome）
- **读取**页面内容（结构化 DOM，不是截图）
- **交互**——点击按钮、填写表单、选择选项
- **提取**页面数据或拦截网络 API 响应
- **等待**元素、文本或页面跳转

安装 skill：
```bash
npx skills add jackwener/opencli --skill opencli-browser
```

### 5.3 自己写适配器

给新网站写 CLI 命令：
```bash
opencli browser init <site>/<command>    # 初始化适配器
opencli browser recon verify <site>      # 验证
```

---

## 六、登录相关的核心机制

### 为什么说它"为应对登录页面设计"

| 传统自动化方案 | OpenCLI |
|--------------|---------|
| 需要存储用户名密码 | ❌ 不复用浏览器会话，需自己登录 |
| 需要处理验证码 | 网站以为是真人，正常操作不触发验证码 |
| 需要处理 2FA | 不需要，浏览器已登录 |
| Cookie 管理 | 浏览器自动管理 |
| 风控风险 | 极低，操作特征等同于真人 |
| 需要单独维护登录状态 | Chrome 正常使用即可维持登录 |

**一句话总结**：OpenCLI 不登录网站——它让你已登录的 Chrome 替你操作。

---

## 七、本机适配结论

### 可用性评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 环境兼容 | ✅ 9/10 | Node.js ✅ Chrome ✅ DISPLAY ✅ |
| 扩展安装 | ⚠️ 6/10 | Chrome Web Store 国内可访问，但 GitHub 拉取适配器时需代理 |
| 本机可用 | ✅ 8/10 | 主要功能可直接使用 |
| 综合 | ✅ 可用 | 核心能力都在，代理解决 GitHub 访问即可 |

### 限制
1. **这个 Linux 机是 VMware 虚拟机**，Chrome 运行可能有图形性能问题，但不影响 OpenCLI 功能
2. **国内访问 GitHub 需要代理**（拉适配器/skill 时）
3. **Chrome 扩展安装建议走方式 B**（手动从 GitHub Releases 下载，避免 Chrome Web Store 速度问题）

---

## 八、与你的工作流集成

OpenCLI 可以和 OpenClaw（你自己）配合使用：
- 我通过 OpenCLI 操控 Chrome 帮你搜索/抓取内容
- 安装了 `opencli-browser` skill 后，我可以直接用你的已登录浏览器操作任意网站
- 可以写自定义适配器，把常用的工作网站变成 CLI 命令

---

## 九、官方资源

| 资源 | 地址 |
|------|------|
| GitHub 主页 | `https://github.com/jackwener/opencli` |
| 官网 | `https://opencli.info` |
| npm 包 | `https://www.npmjs.com/package/@jackwener/opencli` |
| Chrome Web Store 扩展 | `https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk` |
| 中文 README | `https://github.com/jackwener/opencli/blob/main/README.zh-CN.md` |
| 阮一峰周刊推荐 | GitHub Issue #9309 |
