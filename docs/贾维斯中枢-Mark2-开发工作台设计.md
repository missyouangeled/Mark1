# 🖥️ Mark2 — 开发工作台与环境设计 v1.0

> 创建：2026-06-15
> 状态：v1.2（三大领域工作流补全：网页/图片/视频）
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

### 5.6 网页开发专用流

> **定位**：从用户一句话到网站上线，全流程自动化。

```
触发示例：
  "帮我做一个公司官网，蓝色系，有首页/产品/联系"
  "把 portfolio 页面改成暗色模式"
  "基于这个设计稿，做一个落地页"

      │
      ▼
┌──────────────────────────────────────────────────────┐
│ 子 Agent 自动执行                                       │
│                                                        │
│  1. 初始化                                              │
│     npm create vite@latest → Vue3 + TS 或 React + TS   │
│     cd /srv/projects/web/<project>                      │
│                                                        │
│  2. 装依赖                                              │
│     npm install                                         │
│     npm i -D tailwindcss @tailwindcss/vite              │
│     （Tailwind 默认配色体系，快速出视觉）                  │
│                                                        │
│  3. 写代码                                              │
│     - 目录结构: src/{pages,components,assets,utils}/     │
│     - 路由: vue-router / react-router                   │
│     - 样式: Tailwind 原子类 + 自定义主题色                │
│     - 组件: 贾维斯自动生成 Vue SFC / React JSX           │
│                                                        │
│  4. 自检                                                │
│     npm run build（零错误才继续）                         │
│     npm run lint（如有配置）                              │
│                                                        │
│  5. 预览                                                │
│     npx vite preview --host 0.0.0.0 --port <port>       │
│     cloudflared tunnel → 临时 URL                        │
│                                                        │
│  6. 回报                                                │
│     "✅ <项目名> 已上线预览 → https://xxx.trycloudflare.com" │
│     "共 N 个页面 / M 个组件 / 构建体积 X KB"              │
└──────────────────────────────────────────────────────┘
```

**技术栈选择规则**：

| 场景 | 技术栈 | 理由 |
|------|-------|------|
| 通用网站/落地页 | Vue3 + Vite + Tailwind | 轻量、快、贾维斯最熟 |
| 复杂交互/后台 | React + Vite + Tailwind | 生态丰富 |
| 静态内容站 | 纯 HTML + Tailwind（零 JS 框架） | 极致轻量 |
| 公司官网/展示 | Vue3 + Vite + Tailwind | 默认首选 |

**前端设计能力**：贾维斯有 `frontend-design` skill，可生成高质量 UI。子 Agent 任务中可指定使用。

### 5.7 图片生成专用流（AI 文生图 / 图生图）

> **定位**：直接调用 `image_generate` 工具生成图片，不走外部 API 或第三方服务。
>
> **当前管线**：`litellm/agnes-image-2.1-flash`（通过 LiteLLM 通道 → Agnes API 网关 `apihub.agnes-ai.com/v1`）
> **可用模型**：`agnes-image-2.0-flash`、`agnes-image-2.1-flash`、`agnes-video-v2.0`、`agnes-1.5-flash`、`agnes-2.0-flash`

```
触发示例：
  "帮我生成一张赛博朋克风格的猫"
  "把这张照片的色调改成电影质感"
  "给首页做一个 16:9 的 Hero 横幅图"

      │
      ▼
┌──────────────────────────────────────────────────────┐
│ 贾维斯主会话 / 子 Agent（轻量，不开分身）               │
│                                                        │
│  文生图：                                               │
│    image_generate(                                      │
│      prompt="赛博朋克风格的黑猫，霓虹灯，雨夜，4K",       │
│      size="1024x1024",         或 aspectRatio="16:9",   │
│      outputFormat="png"                                 │
│    )                                                    │
│    → 返回图片路径 → MEDIA 发给你                         │
│                                                        │
│  图生图：                                               │
│    image_generate(                                      │
│      prompt="保留人物和构图，色调改为电影级暖色",         │
│      image="path/to/photo.jpg"                          │
│    )                                                    │
│    → 基于原图修改 → 返回新图                             │
│                                                        │
│  批量生成（多张）：                                      │
│    image_generate(                                      │
│      prompt="同一个角色 8 种情绪表情包",                 │
│      count=4                                            │
│    )                                                    │
│    → 一次出 4 张                                        │
└──────────────────────────────────────────────────────┘
```

**尺寸速查**：

| 用途 | 参数 |
|------|------|
| 头像/Avatar | `size="1024x1024"` |
| Hero 横幅 | `aspectRatio="16:9"` |
| 手机海报 | `aspectRatio="9:16"` |
| 宽屏壁纸 | `aspectRatio="21:9"` |
| 方形贴纸 | `aspectRatio="1:1"` |

**生成后的落地**：
- 图片默认存入项目 `public/images/` 或 `assets/`
- 贾维斯自动在代码中引用（`<img src="/images/hero.webp">`）
- 如需透明背景：`background="transparent"` + `outputFormat="png"`

> 📌 图片生成是轻量操作（几秒到十几秒），**不走分身**，主会话直接调 `image_generate`
> 然后 MEDIA 贴给你。不像网页开发那样需要开子 Agent。

### 5.8 视频处理专用流

> **定位**：视频下载、剪辑、转码、帧提取。工具链已在 Mark1 验证，迁移到 Mark2。

```
触发示例：
  "帮我把这个视频转成 MP4 1080p"
  "从这个视频里提取每 10 秒一帧"
  "下这个抖音视频然后截取封面"

      │
      ▼
┌──────────────────────────────────────────────────────┐
│ 贾维斯 / 子 Agent（大文件走分身）                       │
│                                                        │
│  工具链（系统级已安装）：                                │
│    ffmpeg    → 转码、剪辑、合并、提取音频               │
│    ffprobe   → 查看视频元信息（分辨率/码率/时长）        │
│    yt-dlp    → 下载 YouTube/B站/其他平台               │
│    scripts/download-platform-video.py → 抖音等短视频   │
│                                                        │
│  典型工作流：                                           │
│    1. ffprobe input.mp4         → 了解源格式           │
│    2. ffmpeg -i input.mp4 ...   → 转码/剪辑            │
│    3. ffprobe output.mp4        → 验证输出             │
│    4. 回报结果 + 文件路径                              │
│                                                        │
│  帧提取：                                               │
│    ffmpeg -i video.mp4 -vf fps=1/10 frames/%04d.png    │
│    → 每 10 秒一帧，输出到 frames/ 目录                  │
│                                                        │
│  下载抖音视频（Mark1 已验证管线）：                      │
│    python3 scripts/download-platform-video.py \        │
│      --pick=first '<视频URL>'                          │
│    → 下载 + ffprobe 校验                                │
│                                                        │
│  AI 视频生成（实验性）：                                │
│    image_generate(                                      │
│      prompt="...",                                      │
│      model="litellm/agnes-video-v2.0"                  │
│    )                                                    │
│    → 注：视频模型较慢，显式告知用户等待                   │
└──────────────────────────────────────────────────────┘
```

**视频项目目录结构**：

```
/srv/projects/video/
├── downloads/       # 下载的原始视频
├── outputs/         # 处理后的输出
├── frames/          # 帧提取输出
├── scripts/         # 视频处理脚本
└── README.md        # 记录常用命令
```

**边界规则**：
- 大视频（>500MB）操作必须走 `sessions_spawn` 后台分身
- 下载前检查数据盘剩余空间
- 不自动删除原始文件（用户确认后删）
- 视频输出写入 `/mnt/data/video-outputs/`，不占系统盘

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
| 2 | 是否需要 Playwright/Cypress 做 E2E 测试？ | 依赖体积较大 |
| 3 | 项目是直接用 `npm create vite@latest`（每次都最新），还是固定模板？ | 开发一致性 |
| 4 | 临时预览域名要不要绑到固定子域名（如 `preview.yourdomain.com`）？ | Caddy 配置 |
