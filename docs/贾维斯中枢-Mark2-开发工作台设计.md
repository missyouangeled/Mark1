# 🖥️ Mark2 — 开发工作台与环境设计 v1.0

> 创建：2026-06-15
> 状态：v2.0（架构交叉审查 + 三领域详细设计）
> 适用范围：中枢服务器（Ubuntu 24.04）
> 原则：环境隔离 → 直接可用 → 远程驱动 → 外部可验

---

## 一、设计目标

用户三条核心诉求：

1. **各自尽量独立** — 每个项目的依赖、插件、运行时互不污染
2. **我直接写代码 / 贾维斯直接帮我做** — 人在外面、手边没电脑，手机发条消息就能让贾维斯接手开发
3. **做好后能外部访问验证** — 网站 / 小程序 / API 做完立刻能打开看效果

这三条展开后是五个子目标：

| # | 目标 | 含义 |
|---|------|------|
| A | 项目隔离 | 每个项目独立的依赖和运行时，不互相污染 |
| B | 插件就绪 | code-server 开箱即用，需要的插件提前装好 |
| C | 依赖管理 | 每个项目的依赖声明清晰，能一键安装 |
| D | 远程驱动 | 手机发消息 → 贾维斯接任务 → 开监工 → 写代码 → 测试 → 可预览 |
| E | 外部可验 | 项目做完了能从一个临时 URL 打开看 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        开发工作台 (L3)                                 │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    code-server :8080                          │   │
│  │              (127.0.0.1 only, Caddy 反代)                     │   │
│  │                                                               │   │
│  │  扩展市场: Open VSX  │  认证: password 或 CF Access           │   │
│  │  工作区: /srv/projects/  │  用户数据: ~/.local/share/code-server │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│              ┌───────────────┼───────────────┐                      │
│              ▼               ▼               ▼                      │
│  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │   web/        │ │   miniapp/   │ │   api/       │  ...          │
│  │   (独立环境)   │ │   (独立环境)  │ │   (独立环境)  │               │
│  └───────────────┘ └──────────────┘ └──────────────┘               │
│                                                                     │
│  贾维斯开发驱动层                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  手机发消息 → OpenClaw Gateway → sessions_spawn (子agent)      │   │
│  │  → 开监工 → exec 写代码/装依赖/跑测试 → vite preview          │   │
│  │  → cloudflared tunnel → 临时预览 URL → 回报用户               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  外部预览管道                                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  dev 端口 → cloudflared tunnel → <rand>.trycloudflare.com     │   │
│  │  或 dev 端口 → Caddy 路由 → svc.xxx.com/dev/web/             │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、项目环境隔离

### 3.1 核心原则：每个项目一朵「环境花」

不依赖 Docker 来隔离（太重），用 **目录约定 + 锁文件 + 脚本** 实现轻量隔离：

```
/srv/projects/
├── web/               # 网站项目
│   ├── package.json   # Node 依赖声明
│   ├── node_modules/  # 项目自有一份（不共享）
│   ├── src/
│   ├── public/
│   └── .env
│
├── miniapp/           # 小程序项目（uni-app CLI）
│   ├── package.json
│   ├── node_modules/
│   ├── vite.config.ts
│   └── src/
│       ├── pages/
│       ├── components/
│       └── App.vue
│
├── api/               # API 服务
│   ├── requirements.txt 或 pyproject.toml
│   ├── venv/           # 项目自有 venv
│   └── src/
│
├── image/             # 图片生成与处理
│   ├── prompts/       # 提示词存档（可复用）
│   ├── outputs/       # AI 生成的图片
│   ├── sources/       # 原始素材（图生图的原图）
│   └── README.md      # 记录图片用途和生成参数
│
└── video/             # 视频处理
    ├── downloads/     # 下载的原始视频
    ├── outputs/       # 处理后的输出
    ├── frames/        # 帧提取输出
    └── README.md      # 记录常用命令
```

### 3.2 隔离策略（分级）

| 级别 | 隔离内容 | 做法 |
|------|---------|------|
| **语言运行时** | Node / Python / Go | 系统装好，不隔离（版本一致性由项目说明文档规定） |
| **项目依赖** | npm packages / pip packages | 每个项目 `node_modules/` 或 `venv/` 自有一份 |
| **全局工具** | Vite / ESLint / Prettier | 系统级 `npm i -g` 安装，所有项目共享 |
| **数据库** | SQLite / JSON | 数据库文件放在项目目录下，或用 Docker 的 Postgres/MySQL |
| **环境变量** | API keys / tokens | 每个项目的 `.env` 文件独立 |
| **Git** | 版本控制 | 每个项目独立 `git init`，不共用仓库 |

### 3.3 新项目初始化模板

```bash
# 贾维斯接到任务后自动执行的标准流程：

# Step 1: 创建项目目录
mkdir -p /srv/projects/<project-name>/{src,public,tests}

# Step 2: 初始化 Git
cd /srv/projects/<project-name> && git init

# Step 3: 按类型初始化
# 网站 → npm init / 小程序 → miniapp-cli / API → python -m venv venv
# （贾维斯根据项目类型自动选择）

# Step 4: 安装依赖
# Node: npm install  / Python: pip install -r requirements.txt

# Step 5: 创建 README.md（记录依赖、启动命令、端口）
```

> 📌 参考：code-server 社区讨论（GitHub #4125）公认的做法是单实例多目录，
> 比多实例更省资源、管理更简单。Mark2 单用户场景完全适用。

---

## 四、code-server 插件与依赖

### 4.1 基础插件（部署时预装）

> 📌 code-server 默认使用 Open VSX 市场（`open-vsx.org`）。
> Coder 自建的 `extensions.coder.com` 已于 2024 年下线（issue #7726），不可用。
> 如有必要，可设 `EXTENSIONS_GALLERY` 指向私有市场。

```bash
# 预装插件列表（--extensions-dir 统一管理）

# --- 前端开发 ---
code-server --install-extension Vue.volar                # Vue 3 语法支持
code-server --install-extension dbaeumer.vscode-eslint   # ESLint
code-server --install-extension esbenp.prettier-vscode   # Prettier 格式化
code-server --install-extension bradlc.vscode-tailwindcss # Tailwind CSS IntelliSense
code-server --install-extension formulahendry.auto-rename-tag # HTML 自动重命名

# --- 后端 / API ---
code-server --install-extension ms-python.python         # Python 支持
code-server --install-extension ms-python.debugpy        # Python 调试器

# --- 通用 ---
code-server --install-extension eamodio.gitlens          # Git 增强
code-server --install-extension ms-vscode.live-server    # 🆕 实时预览（核心插件）
code-server --install-extension streetsidesoftware.code-spell-checker # 拼写检查
code-server --install-extension gruntfuggly.todo-tree    # TODO 树

# --- markdown ---
code-server --install-extension yzhang.markdown-all-in-one
```

### 4.2 按项目类型追加插件

```bash
# 小程序
code-server --install-extension uni-helper.uni-app-schemas  # uni-app 语法提示
code-server --install-extension uni-helper.uni-cloud-snippets # uni-cloud 代码段
# 注意：微信官方开发者工具无 Linux 版，见 4.2.1 节的 Linux 开发方案

# React / Next.js
code-server --install-extension dsznajder.es7-react-js-snippets

# 图片处理
# Python 已覆盖，不需要额外插件

# API 后端
code-server --install-extension ms-python.black-formatter   # Python 格式化
code-server --install-extension tamasfe.even-better-toml    # pyproject.toml 支持
```

### 4.2.1 🆕 小程序在 Linux 上开发的实际情况

> **核心事实**：微信官方开发者工具没有 Linux 版。Mark2 服务器是 Ubuntu 24.04（无 GUI），以下为实测可行的方案。

#### 三种可行路线

```
 路线A: uni-app CLI 模式（推荐，主路线）
   ✅ 在 Linux 上完全原生运行（只依赖 Node.js）
   ✅ H5 模式：npm run dev:h5 → 浏览器直接预览
   ✅ 小程序模式：npm run dev:mp-weixin → 编出微信小程序包
   ✅ 在 code-server 中写 Vue3 代码，插件提示完整
   ⚠️ 不能实时小程序真机预览（需上传后扫码）

 路线B: msojocs/wechat-web-devtools-linux（备选，需桌面环境）
   ✅ 社区移植版，支持 Linux GNOME 桌面
   ⚠️ 需要 X11/Wayland 显示服务器 → Mark2 服务器无 GUI，不可用
   ⚠️ 维护依赖微信版本更新，可能滞后
   
 路线C: 手机扫码体验版（验收用）
   ✅ 构建 → 上传微信后台 → 设为体验版 → 手机扫码打开
   ✅ 完全真机环境，所见即所得
   ⚠️ 不能实时 debug（断点/console），只能看表现
```

#### 最终方案

```
Mark2 开发阶段（Linux 服务器上）：
  1. code-server 中写 uni-app Vue3 代码
  2. npm run dev:h5 → 浏览器预览（最快反馈循环）
  3. npm run dev:mp-weixin → 编出小程序包验证无编译错误

验收阶段（手机）：
  4. npm run build:mp-weixin → 上传微信后台
  5. 设为体验版 → 手机扫码打开
  6. 贾维斯用 web_fetch 抓取构建日志回报

备选（如果你的 Windows 掌机可以用）：
  7. 同一份代码 push 到 Git
  8. Windows 掌机 pull → 微信官方开发者工具打开 → 真机调试
```

> 📌 结论：小程序在 Mark2 上用 **uni-app CLI + H5 预览** 写代码完全没问题。
> 真机验收通过上传体验版走。不需要在服务器上折腾 Wine 或 X11 转发的开发工具。

### 4.3 系统级依赖

```bash
# 已在部署手册第 9 层安装：
# - Node.js 22 + npm
# - Python 3.11 + pip + venv
# - FFmpeg
# - Git
# - build-essential（C/C++ 编译）

# 全局前端工具（所有项目共享）
npm i -g vite@latest
npm i -g @vue/cli          # Vue CLI（可选）
npm i -g eslint prettier   # 代码质量
npm i -g typescript        # TypeScript（所有项目可用）
```

### 4.4 依赖安装验证

```bash
# 部署后烟测
node -v     # ≥22
python3 -V  # ≥3.11
git --version
vite --version
npm ls -g --depth=0      # 列出全局包
code-server --version
code-server --list-extensions  # 列出已装插件
```

---

## 五、远程驱动工作流（手机 → 贾维斯 → 产出）

### 5.1 工作流总览

```
你在外面，手机发消息：
  "帮我在 /srv/projects/web/portfolio 做个个人主页，
   要有头像、名字、技能标签、项目展示"

      │
      ▼
┌──────────────────────────────────────────────┐
│ 贾维斯主会话                                   │
│  1. 解析需求 → 拆任务                          │
│  2. sessions_spawn(mode="run") 开分身          │
│  3. 开监工（auto + taskActive=true）            │
│  4. 回报：「收到，正在做，等几分钟」              │
└──────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────┐
│ 子 Agent 分身（后台跑）                         │
│  Step 1: 创建 /srv/projects/web/portfolio/      │
│  Step 2: npm create vite@latest → 初始化项目    │
│  Step 3: 写 HTML/CSS/JS 代码                    │
│  Step 4: npm install → 装依赖                   │
│  Step 5: npm run build → 构建                   │
│  Step 6: npx vite preview --host 0.0.0.0       │
│  Step 7: cloudflared tunnel → 临时 URL          │
│  Step 8: 回报主会话：「做好了，预览地址 xxx」     │
└──────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────┐
│ 监工链路                                       │
│  - 每 30s 检查子 agent 状态                     │
│  - 卡住/完成 → 自动回报前台                      │
│  - 异常 → 告警 + 尝试重试                       │
└──────────────────────────────────────────────┘
      │
      ▼
  你的手机收到：
  "✅ 个人主页做好了 → https://xxx.trycloudflare.com
   需要改什么直接说"
```

### 5.2 远程驱动的三个模式

| 模式 | 触发方式 | 适合场景 | 监工 |
|------|---------|---------|------|
| **「帮我做」模式** | 你发需求 → 贾维斯全自动 | 做一个完整的网站/页面 | 开 |
| **「陪我调」模式** | 你在 code-server 里写 → 贾维斯帮你查/改/跑 | 边写边改 | 可选 |
| **「验收下单」模式** | 贾维斯做好 → 你手机打开预览 → 提修改意见 | 远程验收 | 自动回报 |

### 5.3 「帮我做」模式的标准指令

```
用户消息自然语言示例：

"帮我做一个公司官网，用 Vue3+Vite，
 有首页、关于我们、产品展示、联系方式四个页面，
 配色用蓝色系。
 做好后直接预览"
 
  ↓ 贾维斯自动解析为：
 
  {
    project: "company-site",
    dir: "/srv/projects/web/company-site",
    stack: "vue3+vite",
    pages: ["home", "about", "products", "contact"],
    theme: "blue",
    preview: true
  }
```

### 5.4 子 Agent 任务模板

```python
# 贾维斯分身的标准任务描述（给子 Agent 的第一条消息）
task = f"""
你是一个全栈开发者。在 /srv/projects/web/{project_name}/ 目录下创建项目。

要求：
1. 技术栈：{stack}
2. 功能：{requirements}
3. 完成后必须执行：
   a. npm install && npm run build
   b. npx vite preview --host 0.0.0.0 --port {pick_free_port()}
   c. cloudflared tunnel --url http://localhost:{port}
   d. 把预览 URL 写入 /tmp/preview-{project_name}.txt
   e. 回报主会话：任务完成 + 预览 URL

约束：
- 不装全局包（npm install 只能装项目依赖）
- 不改其他项目目录
- 构建失败时报告具体错误，不要静默跳过
"""

sessions_spawn(task=task, taskName=f"dev-{project_name}", mode="run")
```

### 5.5 端口分配

```
端口范围规划：
  5173-5199: Vite dev/preview (项目按创建顺序递增)
  3000-3019: Next.js
  8000-8019: Python/Flask/FastAPI
  8080:     code-server 自身

每个项目启动时自动分配未被占用的端口。
端口表写入 /srv/projects/.ports.json，重启后清理。
```

---

## 五-A、架构交叉审查（v2.0 新增）

> **审查方法**：将 L3 开发工作台放到 Mark2 七层架构中，逐一交叉检查依赖、冲突、缺口。

### 审查矩阵

```
  L1 — Caddy 网关
  L2 — 贾维斯核心 (OpenClaw Gateway)
  L3 — 开发工作台 ★ 本层
  L4 — Docker 服务 (Nextcloud / Syncthing / DB)
  L5 — Merge VPN (Tailscale)
  L6 — 数据备份
  L7 — 安全防护
  🧹 — 回收机制 (横向)
```

| 交叉层 | 审查项 | 状态 | 分析 |
|--------|--------|------|------|
| L3 ↔ L1 | code-server 反代路由 | ✅ | Caddy → `code.xxx.com` → :8080，已在迁移方案 v3 步骤 4 配置 |
| L3 ↔ L1 | 开发预览路由 | ✅ | Caddy → `dev.xxx.com/*` → 各项目端口，6.4 节已设计 |
| L3 ↔ L1 | Vite HMR WebSocket | ✅ | Caddy 默认支持 WebSocket 升级，HMR 经反代可直通 |
| L3 ↔ L1 | cloudflared 隧道 | ✅ | 零配置临时隧道，5.6 节网页自检链路已对接 |
| L3 ↔ L2 | `sessions_spawn` 开分身 | ✅ | 网页大工程走后台分身；图片走主会话轻量调 |
| L3 ↔ L2 | 监工回报 | ✅ | `auto + taskActive=true`，子 Agent 卡住/完成自动回报前台 |
| L3 ↔ L2 | `image_generate` 工具调用 | ✅ | 主会话直接调，LiteLLM → Agnes API，已在 5.7 节设计 |
| L3 ↔ L2 | `exec` 调用 ffmpeg/构建 | ✅ | 构建命令通过 exec 跑，大视频 >500MB 走后台分身 |
| L3 ↔ L4 | 数据库服务 | ⚠️ | 如项目需要 PostgreSQL/Redis，走 Docker Compose 部署（L4 层），不在 L3 裸机装 |
| L3 ↔ L4 | 图床存储 | ⚠️ | 生成的图片如需长期托管，对接 Lsky Pro（L4 Docker）而不是留在 `/srv/projects/` |
| L3 ↔ L5 | Tailscale 内网预览 | ✅ | 方案 C：`npm run preview --host 0.0.0.0` → 另一台设备 `http://100.x.x.1:5173` |
| L3 ↔ L6 | `/srv/projects/` Git 备份 | ✅ | 每个项目独立 Git，push 到 GitHub 私有仓库 |
| L3 ↔ L6 | 图片输出备份 | ⚠️ 缺口 | 生成的图片暂存在 `outputs/`，需纳入备份策略或定期清理 |
| L3 ↔ L6 | 视频下载持久化 | ⚠️ 缺口 | 下载的视频放 `/mnt/data/video-outputs/`，需明确保留/清理策略 |
| L3 ↔ L7 | code-server 认证 | ✅ | 强密码 + CF Access 双重保护，8.4 节已设计 |
| L3 ↔ L7 | 终端权限 | ✅ | jarvis 用户运行，sudo 需密码，/srv/projects/ 被 auditd 监控 |
| L3 ↔ L7 | 对外暴露的项目安全 | ⚠️ 缺口 | 若项目含 API/表单/XSS 漏洞，经 CF Tunnel 暴露后会被利用 → 默认只开预览，不做长期生产部署 |
| L3 ↔ 🧹 | 构建产物清理 | ✅ | node_modules/dist 膨胀 → 回收机制 L3 负责 |
| L3 ↔ 🧹 | 图片生成累积 | ⚠️ 缺口 | image/outputs/ 无限增长 → 回收机制需增加「超过 N 天未引用的图片自动清理」| 
| L3 ↔ 🧹 | 视频下载累积 | ⚠️ 缺口 | downloads/ + outputs/ 持续增长 → 回收机制需增加「`cleanup-old-video.sh`」规则 |
| L3 ↔ 🧹 | node_modules bloat | ⚠️ 缺口 | 多个项目各自 `node_modules/`，累计可达 GB → 回收机制 L3 应增加「`node_modules` 超过阈值告警」|

### 审查结论

```
✅ 无阻塞缺口 — 可进入详细设计
⚠️ 4 个待补：DB 对接 / 图床对接 / 安全暴露面 / 文件累积回收
📋 三领域详细设计 → 5.6 / 5.7 / 5.8
```

---

### 5.6 网页开发详细设计

> **搜索确认（2025-2026）**：TailwindCSS v4 于 2025-01 发布，改用 CSS-first 配置（`@import "tailwindcss"`），不再需要 `tailwind.config.js`。Vue3 + Vite + Tailwind v4 是当前主流轻量栈。VS Code 1.121（2026-05）内置远程 Agent 支持，验证了远程开发的行业方向。

#### 技术栈固化

| 组件 | 版本要求 | 用途 |
|------|---------|------|
| Vue 3 | ≥3.5 | 组件框架（Composition API + `<script setup>`） |
| Vite | ≥6 | 构建工具 + 开发服务器 |
| TailwindCSS | ≥4 | 原子化 CSS 框架（CSS-first 配置） |
| TypeScript | ≥5.5 | 类型安全（可选，默认不强制） |
| vue-router | ≥4 | SPA 路由 |
| Pinia | ≥2 | 状态管理（按需引入） |

#### TailwindCSS v4 适配（关键）

```bash
# v4 安装方式（不需要 tailwind.config.js）
npm install tailwindcss @tailwindcss/vite

# vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()]
})
```

```css
/* src/style.css — v4 用 CSS 导入替代 JS 配置文件 */
@import "tailwindcss";

/* 自定义主题色（v4 语法） */
@theme {
  --color-primary: #3b82f6;
  --color-primary-dark: #1d4ed8;
}
```

#### 标准项目搭建命令（子 Agent 自动执行）

```bash
# Step 1: 脚手架
npm create vite@latest my-project -- --template vue-ts
cd /srv/projects/web/my-project

# Step 2: 核心依赖
npm install
npm install vue-router pinia
npm install tailwindcss @tailwindcss/vite

# Step 3: 开发工具
npm install -D eslint prettier eslint-plugin-vue

# Step 4: 启动开发
npm run dev -- --host 0.0.0.0
```

#### 目录结构规范

```
/srv/projects/web/<project>/
├── index.html              # 入口 HTML
├── vite.config.ts          # Vite 配置（含 tailwindcss 插件）
├── tsconfig.json           # TS 配置
├── package.json             # 依赖声明
│
├── public/                  # 静态资源（不经过构建）
│   ├── favicon.svg
│   └── images/              # AI 生成的图片落地处
│       └── hero.webp
│
└── src/
    ├── main.ts              # 应用入口
    ├── App.vue               # 根组件
    ├── style.css             # 全局样式（@import "tailwindcss"）
    ├── router/
    │   └── index.ts          # 路由配置
    ├── pages/                # 页面组件
    │   ├── Home.vue
    │   ├── About.vue
    │   └── Contact.vue
    ├── components/           # 复用组件
    │   ├── Header.vue
    │   ├── Footer.vue
    │   ├── HeroSection.vue
    │   └── Card.vue
    ├── composables/          # 组合式函数（hooks）
    │   └── useTheme.ts
    └── assets/               # 需要构建处理的资源
        └── logo.svg
```

#### 子 Agent 工作流（完整版）

```
┌──────────────────────────────────────────────────────────────────┐
│ Step 1: 需求解析                                                   │
│   ├─ 项目名: company-site                                         │
│   ├─ 页面: Home / About / Products / Contact                     │
│   ├─ 配色: blue-600 主色 / slate-800 深色 / white 背景           │
│   └─ 特性: 响应式 / SEO 友好 / 暗色模式                           │
│                                                                   │
│ Step 2: 脚手架搭建                                                 │
│   npm create vite@latest → vue-ts 模板                            │
│   装依赖 → 改 vite.config.ts 加 Tailwind v4 插件                  │
│   建目录结构 → 配路由                                              │
│                                                                   │
│ Step 3: 逐组件生成（每个组件分步验证）                              │
│   写 Header.vue → npm run dev → web_fetch 截图验证                │
│   写 HeroSection.vue → 同上                                       │
│   写页面组件 → Card → Footer                                     │
│   ⚠️ 每完成一个页面截图验证，不全写完才发现问题                     │
│                                                                   │
│ Step 4: 集成 & 自查                                                │
│   npm run build（必须零错误）                                      │
│   vite preview → 本地自检 URL 可达                                │
│   检查 404 页面是否存在                                            │
│                                                                   │
│ Step 5: 预览管道                                                   │
│   cloudflared tunnel --url http://localhost:5173                  │
│   → https://xxx.trycloudflare.com → 回报用户                      │
│   web_fetch + image → 贾维斯远程截图确认                           │
└──────────────────────────────────────────────────────────────────┘
```

#### 前端设计集成

贾维斯已有 `frontend-design` skill（`~/.openclaw/workspace/skills/frontend-design-3/`），子 Agent 任务中启用：

```bash
# 子 Agent 写组件时调用 frontend-design skill 生成高质量 UI
# 产出物直接落到 src/components/ 和 src/pages/
# 风格参考: 现代简约 / 玻璃拟态 / 暗色模式 / 粗野主义
```

#### 质量门禁

| 门禁 | 标准 | 工具 |
|------|------|------|
| 构建 | `npm run build` 零错误 | Vite build |
| 类型 | `vue-tsc --noEmit` 通过 | TypeScript |
| Lint | `eslint .` 无 error | ESLint + plugin-vue |
| 预览可达 | `web_fetch(url)` 返回 200 | 贾维斯工具 |
| 视觉检查 | `image(url)` 截图确认渲染 | 贾维斯工具 |

#### 常见网页需求模板

| 需求类型 | 模板代码位置 | 预估量 |
|---------|-------------|--------|
| 公司官网 | 4 页 SPA（Home/About/Products/Contact） | ~800 行 |
| 落地页 | 单页长滚动，Hero + Features + CTA | ~300 行 |
| 个人主页 | 单页卡片式，头像 + 技能 + 项目 | ~200 行 |
| 产品展示 | 列表 + 详情页，筛选/搜索 | ~600 行 |
| 暗色模式 | 所有页面自动支持，CSS 变量切换 | ~50 行额外 |

### 5.7 图片生成详细设计（AI 文生图 / 图生图）

> **搜索确认**：LiteLLM 的 `image_generation()` 支持多 provider 统一调用（OpenAI DALL-E、RunwayML、ModelsLab、Agnes 等），通过 OpenAI 兼容格式路由。Mark2 当前管线 `litellm/agnes-image-2.1-flash` 符合行业主流通用网关模式。

#### 当前管线详情

```
调用链：
  image_generate(prompt, model, size, ...)
    → OpenClaw 工具层
      → LiteLLM 通道 (provider=litellm)
        → Agnes API 网关 (apihub.agnes-ai.com/v1)
          → agnes-image-2.1-flash 模型
            → 返回图片 URL/路径

关键配置（openclaw.json → models.providers.litellm）：
  api_base: https://apihub.agnes-ai.com/v1
  api_key: 已写入 litellm provider

可用模型：
  agnes-image-2.0-flash   → 速度优先
  agnes-image-2.1-flash   → 质量优先（当前默认）
  agnes-1.5-flash         → 快速原型
  agnes-2.0-flash         → 平衡版
  agnes-video-v2.0        → 视频生成
```

#### 工作流决策树

```
你的消息
│
├─ "生成一张 X 风格的 Y"
│   → 文生图
│   → image_generate(prompt, size/aspectRatio, outputFormat)
│   → 几秒出图 → MEDIA 发你
│
├─ "把这张图改成 Z 效果"（附带图片）
│   → 图生图
│   → image_generate(prompt, image="path/to/photo.jpg")
│   → 基于原图编辑 → MEDIA 发你
│
├─ "给网站生成 Hero 图 / 首页横幅 / 图标"
│   → 文生图 + 落地集成
│   → image_generate → 存入 public/images/
│   → 自动在代码中写 <img> 引用
│   → npm run build → 预览网址包含新图
│
├─ "批量生成同一主题 N 张变体"
│   → count=4 → 一次调 4 张
│   → 或 for 循环 4 次（每次微调 prompt）
│
└─ "这张图不符合预期，调整 XXX"
    → 修改 prompt → 重新生成
    → 原图保存到 outputs/ 备查
```

#### Prompt 工程规则

```yaml
# 贾维斯自动注入的质量增强规则（Mark2 内部策略，用户无感）

文生图 prompt 结构:
  subject: "一只黑猫"                              # 📍 主体
  style: "赛博朋克风格，霓虹灯，雨夜城市背景"        # 🎨 风格
  quality: "高细节，4K，电影级光照"                 # 📐 质量
  technical: "居中构图，f/2.8"                      # 🔧 技术

图生图 prompt 约束:
  - 必须说明"保留主体和构图"
  - 只描述要修改的部分，不要说主体特征
  - 例：✅ "色调改为暖金色电影风格"
        ❌ "一只黑猫，暖色调"（会改变主体）
```

#### 图片落地与引用

```
生成后自动执行的收尾流程：

  1. 命名规范
     生成时间戳 → 2026-06-15-hero-banner.png
     语义化           → website-hero-cyberpunk-v1.png

  2. 存放位置
     网站项目  → /srv/projects/web/<project>/public/images/
     独立图片  → /srv/projects/image/outputs/

  3. 代码引用（网站项目）
     <img src="/images/hero-banner.webp" alt="Hero Banner" />
     贾维斯自动写 lazy loading + width/height

  4. 格式转换（如需）
     # PNG → WebP（网页用，体积小 70%）
     ffmpeg -i out.png -quality 85 out.webp

  5. 透明背景
     background="transparent" + outputFormat="png"
     用于 logo / 贴纸 / 叠加素材
```

#### 批量生成策略

```python
# 场景 1: 同一个角色 N 种表情（一次性批量）
image_generate(
    prompt="...8张不同表情的同一个角色，网格排列",
    count=4  # 一次出 4 张，两次出完
)

# 场景 2: 同一页面 N 个不同位置的图（逐个生成）
# Hero 横幅 → aspectRatio="16:9"
# 卡片配图 → size="1024x1024"
# 背景纹理 → aspectRatio="1:1"
# 每一张 prompt 不同，尺寸不同，逐个调

# 场景 3: 迭代优化（不满意 → 改 prompt → 重新生成）
# 保留原图到 outputs/archive/
# 新图覆盖原位置
# 文件名加 v2/v3 后缀区分
```

#### 质量验收流程

```
生成后贾维斯自动检查：
  1. 图片文件存在 + 大小 > 0
  2. 格式正确（png/webp/jpeg）
  3. 加载验证（web_fetch 图片 URL 返回 200）
  4. 如果是网站项目：build 后确认 img 标签引用正确
  5. 回报用户：「生成完成，共 N 张 → 预览地址 xxx」
```

### 5.8 视频处理详细设计

> **搜索确认**：FFmpeg 自动化最佳实践 → 队列化处理、CPU 核心数匹配进程数、文件 I/O 与转码分离。单用户场景不需要分布式队列，直接调用即可。大文件转码建议限制 CPU 使用（`-threads` 参数）。

#### 工具链版本锁定

| 工具 | 安装方式 | 验证命令 |
|------|---------|---------|
| FFmpeg | `sudo apt install ffmpeg` | `ffmpeg -version` |
| FFprobe | （随 FFmpeg 安装） | `ffprobe -version` |
| yt-dlp | `pip install yt-dlp` 或 `sudo apt install yt-dlp` | `yt-dlp --version` |
| download-platform-video.py | Mark1 脚本，同步到 Mark2 `scripts/` | `python3 scripts/download-platform-video.py --help` |

#### 常用操作完整命令集

```bash
# ===== 信息查看 =====
ffprobe -v quiet -print_format json -show_format -show_streams input.mp4
# 提取关键字段: duration / bit_rate / width / height / codec_name

# ===== 转码 (H.264 兼容性最好) =====
# 1080p 高质量
ffmpeg -i input.mp4 -c:v libx264 -crf 23 -preset medium \
  -c:a aac -b:a 128k -movflags +faststart output.mp4

# 720p 小体积
ffmpeg -i input.mp4 -c:v libx264 -crf 28 -preset fast \
  -vf scale=-1:720 -c:a aac -b:a 96k output.mp4

# 极致压缩（Web 优化）
ffmpeg -i input.mp4 -c:v libx264 -crf 32 -preset veryslow \
  -c:a aac -b:a 64k -movflags +faststart output.mp4

# ===== 剪辑 =====
# 截取片段（从 30s 开始，取 10s）
ffmpeg -ss 00:00:30 -i input.mp4 -t 00:00:10 -c copy output.mp4

# 精确剪辑（重新编码，无关键帧漂移）
ffmpeg -ss 00:00:30 -i input.mp4 -t 00:00:10 \
  -c:v libx264 -crf 23 -c:a aac output.mp4

# ===== 帧提取 =====
# 每 N 秒一帧
ffmpeg -i input.mp4 -vf "fps=1/10" frames/frame_%04d.png

# 缩略图网格（NxM）
ffmpeg -i input.mp4 -vf "fps=1/10,scale=320:-1,tile=5x4" thumbnails.jpg

# 提取封面帧（第 5 秒）
ffmpeg -ss 5 -i input.mp4 -vframes 1 -q:v 2 cover.jpg

# ===== 合并 =====
# 先创建文件列表 filelist.txt（每行: file 'xxx.mp4'）
ffmpeg -f concat -safe 0 -i filelist.txt -c copy merged.mp4

# ===== 音频 =====
# 提取音频
ffmpeg -i input.mp4 -vn -c:a aac -b:a 192k audio.aac

# 替换音频
ffmpeg -i video.mp4 -i audio.aac -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 output.mp4

# ===== 格式转换 =====
# WebM（VP9）→ 网页最优
ffmpeg -i input.mp4 -c:v libvpx-vp9 -crf 30 -b:v 0 -c:a libopus output.webm

# GIF 动图（短视频片段）
ffmpeg -ss 10 -i input.mp4 -t 3 \
  -vf "fps=10,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
  output.gif

# ===== 硬字幕 =====
ffmpeg -i input.mp4 -vf "subtitles=subtitle.srt" output.mp4
```

#### 转码参数速查

| 参数 | 含义 | 推荐值 |
|------|------|--------|
| `-crf` | 质量系数（越小越好） | 23（高清）/ 28（小体积）/ 18（近乎无损） |
| `-preset` | 编码速度 | medium / fast / veryslow |
| `-threads` | CPU 线程数 | 服务器 CPU 核心数的 75%（8核→6线程）|
| `-movflags +faststart` | Web 渐进式加载 | 网页视频一律加 |
| `-c copy` | 无损复制流 | 不需重编码时优先用（秒级完成）|

#### 下载平台视频

```bash
# YouTube / B站 / 通用平台
cd /mnt/data/video-outputs/downloads/
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]" '<URL>'

# 抖音（Mark1 已验管线）
python3 ~/.openclaw/workspace/scripts/download-platform-video.py \
  --pick=first '<分享文案或视频URL>'

# 只列候选、不下（先确认）
python3 ~/.openclaw/workspace/scripts/download-platform-video.py \
  --list-only '搜索关键词'

# 批量下载（从候选文件）
python3 ~/.openclaw/workspace/scripts/download-platform-video.py \
  --input-file tmp/candidates.txt --pick=first
```

#### 大文件处理策略

```
视频大小         策略
────────────────────────────────────────
<100MB           主会话 exec 直接跑
100MB-500MB      主会话跑，告知用户等待
>500MB           sessions_spawn 后台分身跑
                 
                 子 Agent 启动时：
                 1. 先 free -h + df -h 检查资源
                 2. 输出写入 /mnt/data/video-outputs/
                 3. 每 30s 刷新监工状态（进度）
                 4. 完成后回报：「处理完成，文件在 xxx」

AI 视频生成       特殊处理：
                 image_generate(model="litellm/agnes-video-v2.0")
                 预期 1-3 分钟，显式告知：「视频生成中，约 2 分钟...」
                 走后台分身，不阻塞主会话
```

#### 输出规范

```
/mnt/data/video-outputs/
├── downloads/           # 原始下载（保留至用户确认删除）
│   └── douyin_xxx.mp4
├── processed/            # 转码/剪辑后的输出
│   ├── company-intro-1080p.mp4
│   └── company-intro-720p.webm
├── frames/               # 帧提取输出
│   └── video_thumbnails.jpg
├── archives/             # 处理完成的原始文件归档
└── README.md             # 记录各文件用途和命令

命名规范：
  <来源>-<描述>-<规格>.<格式>
  例: douyin-产品介绍-1080p-h264.mp4
      bilibili-教程-帧提取-00.png
```

---

### 5.9 跨领域集成：一次完整的「帮我做」

> 一个真实场景：网页 + 图片 + 视频 三领域联动。

```
你说：
"帮我做一个产品介绍落地页。产品是一款智能猫砂盆。
 需要 Hero 横幅图、产品配图 3 张、
 还有一个产品介绍视频（30 秒的已有素材在我发的链接里）。
 配色用暖白+橙色。"

      │
      ▼
┌──────────────────────────────────────────────────────────────┐
│ 贾维斯主会话 → 拆解为 4 个子任务                                │
│                                                                │
│  ╔══════════════════════════════════════════════════════════╗ │
│  ║ 子Agent A: 网页主体                                       ║ │
│  ║  npm create vite → Vue3 + Tailwind v4 + 暖橙主题        ║ │
│  ║  写 Home.vue（Hero区 + 产品特点区 + 视频区 + CTA区）     ║ │
│  ║  占位图片来源: /images/ 目录（等图片子Agent产出后替换）    ║ │
│  ╚══════════════════════════════════════════════════════════╝ │
│                                                                │
│  ╔══════════════════════════════════════════════════════════╗ │
│  ║ 主会话: 图片生成（轻量，不开分身）                         ║ │
│  ║  [1] Hero横幅: image_generate(                           ║ │
│  ║        "智能猫砂盆产品Hero横幅，暖白+橙色，-16:9")        ║ │
│  ║  [2] 配图×3: image_generate(count=3,                     ║ │
│  ║        "智能猫砂盆产品展示图，不同角度")                   ║ │
│  ║  → 全部落地到 public/images/                             ║ │
│  ╚══════════════════════════════════════════════════════════╝ │
│                                                                │
│  ╔══════════════════════════════════════════════════════════╗ │
│  ║ 子Agent B: 视频处理                                       ║ │
│  ║  下载视频 → ffprobe 检查 → 截取30s精华 →                 ║ │
│  ║  转码 1080p h264 + WebP 缩略图 → 输出到                 ║ │
│  ║  public/videos/  → 视频嵌入网页                          ║ │
│  ╚══════════════════════════════════════════════════════════╝ │
│                                                                │
│  ╔══════════════════════════════════════════════════════════╗ │
│  ║ 收尾: 贾维斯主会话                                        ║ │
│  ║  所有子完成 → npm run build → vite preview               ║ │
│  ║  → cloudflared tunnel → 验证图片+视频都正常              ║ │
│  ║  → 回报: "✅ 落地页已完成 → https://xxx.trycloudflare.com" ║ │
│  ╚══════════════════════════════════════════════════════════╝ │
└──────────────────────────────────────────────────────────────┘
```

---

## 六、外部预览与测试访问

### 6.1 三种预览管道

```
 方案A: cloudflared tunnel（推荐用于临时预览）
   npm run dev → localhost:5173
   cloudflared tunnel --url http://localhost:5173
   → https://random-name.trycloudflare.com
   免费、无需配置、每次重启域名变

 方案B: Caddy 路由（推荐用于长期预览）
   npm run dev --host 0.0.0.0 --port 5173
   Caddy: dev.yourdomain.com/web/portfolio → localhost:5173
   → https://dev.yourdomain.com/web/portfolio
   需要域名、稳定地址、适合反复测试

 方案C: 直接用项目端口 + Tailscale
   npm run build && npm run preview --host 0.0.0.0
   通过 Tailscale IP 访问: http://100.x.x.1:5173
   内网访问、不暴露公网、最安全
```

### 6.2 预览管道选择规则

| 场景 | 管道 | 理由 |
|------|------|------|
| 快速验收（「帮我做」做完后第一次看） | A: cloudflared | 零配置、立刻能用 |
| 反复迭代测试 | B: Caddy 固定路由 | 域名不变、方便反复打开 |
| 你自己调试 | C: Tailscale + code-server 内置预览 | 隐私、无公网暴露 |
| 偶尔给外部人看 | A: cloudflared | 用完即弃、不暴露主域名 |

### 6.3 实时预览（Hot Reload）

> 📌 Vite HMR (Hot Module Replacement) 在远程开发时需要正确处理 WebSocket 连接。
> Caddy 已配置 WebSocket 支持（迁移方案 v3 步骤 4），HMR 经 Caddy 反代可直接工作。

```bash
# 开发中实时预览（经 Caddy 反代）
npm run dev -- --host 0.0.0.0 --port 5173
# 浏览器打开: https://dev.yourdomain.com/web/myproject/
# 修改代码后自动刷新

# 构建后预览（验收用）
npm run build
npx vite preview --host 0.0.0.0 --port 5173
```

### 6.4 多项目并行预览

```
Caddy 路由（方案B）:
  dev.yourdomain.com/web/company-site   → localhost:5173
  dev.yourdomain.com/web/portfolio      → localhost:5174
  dev.yourdomain.com/api/user-service   → localhost:8000

每个项目启动时分配一个端口，Caddy 按路径转发。
```

---

## 七、测试框架与质量

### 7.1 按项目类型的测试工具

| 项目类型 | 单元测试 | E2E 测试 | 启动命令 |
|---------|---------|---------|---------|
| 前端网站 (Vue/React) | Vitest | Playwright / Cypress | `npm test` |
| 小程序 | miniprogram-simulate | 手机扫码体验版 | `npm run dev:mp-weixin` |
| API 后端 (Python) | pytest | httpx / requests | `pytest` |
| 静态网站 | HTML validate | Lighthouse | 无需测试 |
| 图片处理 | pytest (PIL/opencv) | 目视验收 | `pytest` |

### 7.2 贾维斯自动测试流程

```
开发完成后，子 Agent 自动：
  1. npm run build (或等效)           # 构建
  2. npm test (或 pytest)             # 单元测试
  3. npx vite preview --host 0.0.0.0  # 启动预览
  4. cloudflared tunnel               # 暴露外部 URL
  5. 用 web_fetch 自检预览 URL 可达    # 自动验证
  6. 用 image 截图检查页面渲染          # 视觉验证
  7. 回报结果                          # 产出验收报告
```

### 7.3 自动化烟测脚本（部署时创建）

```bash
#!/bin/bash
# /srv/projects/.smoke-test.sh
# 项目创建后自动跑的烟测

PROJECT_DIR=$1
cd "$PROJECT_DIR"

# 检查必要文件存在
[ -f package.json ] || [ -f pyproject.toml ] || [ -f requirements.txt ] || {
    echo "FAIL: 没有依赖声明文件" && exit 1
}

# Node 项目
if [ -f package.json ]; then
    npm install --prefer-offline 2>&1 | tail -3
    npm run build 2>&1 | tail -5
    echo "BUILD_OK"
fi

# Python 项目
if [ -f pyproject.toml ] || [ -f requirements.txt ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt 2>&1 | tail -3
    echo "INSTALL_OK"
fi
```

---

## 八、code-server 部署配置（完整版）

### 8.1 安装

```bash
curl -fsSL https://code-server.dev/install.sh | sh

# 配置
mkdir -p ~/.config/code-server
cat > ~/.config/code-server/config.yaml << 'EOF'
bind-addr: 127.0.0.1:8080
auth: password
password: <强密码>
cert: false

# 用户数据路径
user-data-dir: ~/.local/share/code-server
extensions-dir: ~/.local/share/code-server/extensions

# 禁用遥测（安全+隐私）
disable-telemetry: true
disable-update-check: true
EOF

# systemd 用户服务
systemctl --user enable --now code-server
```

### 8.2 Caddy 反代

```caddy
# /etc/caddy/Caddyfile（追加）
code.yourdomain.com {
    # Cloudflare Access 应在 CF Dashboard 中为此域名开启
    reverse_proxy localhost:8080
    header_down X-Real-IP {remote_host}
}

# 开发预览
dev.yourdomain.com {
    # 按路径转发到不同项目端口
    handle_path /web/company-site/* {
        reverse_proxy localhost:5173
    }
    handle_path /web/portfolio/* {
        reverse_proxy localhost:5174
    }
    handle_path /api/user-service/* {
        reverse_proxy localhost:8000
    }
}
```

### 8.3 工作区配置文件

```json
// /srv/projects/jarvis.code-workspace
// 贾维斯预置的多根工作区，直接在 code-server 中打开所有项目
{
  "folders": [
    { "name": "Web 项目",     "path": "/srv/projects/web" },
    { "name": "小程序(uni-app)", "path": "/srv/projects/miniapp" },
    { "name": "API 服务",     "path": "/srv/projects/api" },
    { "name": "图片生成",     "path": "/srv/projects/image" },
    { "name": "视频处理",     "path": "/srv/projects/video" }
  ],
  "settings": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "files.exclude": {
      "**/node_modules": true,
      "**/__pycache__": true,
      "**/venv": true
    }
  }
}
```

### 8.4 安全规则

| 规则 | 做法 |
|------|------|
| 不监听公网 | `bind-addr: 127.0.0.1:8080`，只接受本机连接 |
| 认证 | 强密码 + Cloudflare Access 双重保护 |
| 终端隔离 | code-server 终端以 `jarvis` 用户运行，不是 root |
| 目录边界 | 终端默认只能操作 `/srv/projects/` 和 `~/.openclaw/workspace/` |
| 审计 | `/srv/projects/` 下关键文件变更由 auditd 监控 |

> 📌 code-server 的终端等同于一个 shell 会话。没有额外容器隔离时，终端本身就是完全系统权限（以 jarvis 用户）。
> 这是设计选择而非漏洞——你就是唯一用户，不需要多租户隔离层。

---

## 九、部署启动上下文（放入部署手册）

### 9.1 依赖关系

```
开发工作台依赖以下已部署的组件：
  ✅ L1 Caddy（反代 code-server 和 dev 域名）
  ✅ L3 Node.js + Python + FFmpeg（开发工具链）
  ✅ /srv/projects/（目录结构由步骤7创建）
  ✅ CF Tunnel（外部预览管道）
```

### 9.2 分层推进位置

```
部署手册推进路线：
  ...
  ├─ 第 5 层：开发环境 ← code-server + 插件 + 项目骨架
  │   ├─ 安装 code-server
  │   ├─ 预装插件（四.1 清单）
  │   ├─ 系统级依赖（四.3）
  │   ├─ 安装 cloudflared（预览通道）
  │   ├─ 创建工作区配置文件
  │   └─ 跑烟测验证
  │
  ├─ 第 6 层：Docker 服务
  ...
```

---

## 十、设计决策记录

| # | 决策 | 理由 | 参考 |
|---|------|------|------|
| 1 | 单 code-server 实例，多项目目录 | 单用户不需要多实例；省资源、管理简单 | GitHub #4125 社区共识 |
| 2 | 项目隔离用目录约定 + 锁文件，不用 Docker | Docker 隔离太重，且你需要直接在服务器上跑代码 | 用户需求「轻量」 |
| 3 | 扩展市场用 Open VSX | Coder 自建市场已下线（issue #7726），Open VSX 是唯一选项 | code-server 默认配置 |
| 4 | 预览用 cloudflared + Caddy 双通道 | cloudflared 零配置快验；Caddy 固定域名反复测 | CF 官方文档 + 用户需要外部访问 |
| 5 | 终端不做容器化隔离 | 你唯一用户，jarvis 用户级隔离足够；容器化增加复杂度 | 用户需求「简单」 |
| 6 | 部署预装插件（不动态安装） | 因为你在外面手机发消息时不能等插件下载 | 核心诉求「手机驱动」 |
| 7 | 端口表集中管理 | 避免端口冲突；重启服务器后自动清理 | 多项目并行需求 |
| 8 | 网页默认 Vue3+Vite+Tailwind | 贾维斯最熟、生态最轻、出活最快 | 前端 skill 经验 |
| 9 | 图片生成不走分身 | image_generate 几秒到十几秒，开分身反而增加延迟 | 操作轻量 |
| 10 | 视频下载输出放数据盘 | 视频文件大，不占系统盘；/mnt/data/video-outputs/ | 磁盘规划 |
| 11 | 大视频操作后台分身 | >500MB 的转码/下载可能跑很久，不阻塞主会话 | 异步卸载协议 |
| 12 | TailwindCSS v4 CSS-first 配置 | 2025-01 发布，不再需要 tailwind.config.js | 社区趋势 |
| 13 | 网页组件逐页验证 | 每写完一个页面截图确认，不全写完才发现问题 | 质量闭环 |
| 14 | Prompt 工程标准化 | 文生图4段结构（主体/风格/质量/技术） | 输出一致性 |
| 15 | FFmpeg 限制 75% CPU 线程 | 避免转码把服务器打满影响其他服务 | 系统稳定性 |
| 16 | 图片/视频累积 → 回收机制挂钩 | 见架构审查 ⚠️ 缺口，回收到 v2.1 时补 | 协同设计 |

---

## 十一、与 Mark2 其他设计文档的关系

```
本文件（开发工作台设计）
│
├─ 被引用: docs/贾维斯中枢-Mark2-部署启动手册.md 第5层
├─ 对接:   docs/贾维斯中枢-Mark2-回收机制设计.md L3 code-server 回收
│          开发环境产生的临时构建文件、node_modules 缓存纳入回收
├─ 对接:   docs/贾维斯中枢安全体系设计.md
│          code-server 认证 + 终端权限 + auditd 监控
└─ 独立:   本文件不内嵌到任何其他文档
```

---

## 十二、待确认项

| # | 问题 | 影响 |
|---|------|------|
| 1 | ~~需要装微信小程序开发工具吗？~~ → 已确认：uni-app CLI + H5 预览 + 手机扫码体验版 | ✅ 已写入 4.2.1 节 |
| 2 | 是否需要 Playwright/Cypress 做 E2E 测试？当前默认只有构建+视觉自检 | 依赖体积 ~500MB，E2E 场景是否频繁？ |
| 3 | 项目是直接用 `npm create vite@latest`（每次都最新），还是固定模板仓库？ | 开发一致性和可复现性 |
| 4 | 临时预览域名要不要绑到固定子域名（如 `preview.yourdomain.com`）？ | Caddy 配置复杂度 |
| 5 | 图片输出累积 → 回收机制需增加「超过 N 天未引用的图片自动清理」 | 🧹 回收机制 v2.1 补充 |
| 6 | 视频下载累积 → 需明确视频保留策略（用户确认删 / 7天自动删 / 手动） | 🧹 回收机制 v2.1 补充 |
| 7 | 项目如需 PostgreSQL/Redis：走 L4 Docker Compose 还是 SQLite 够用？ | 架构边界 L3↔L4 |
