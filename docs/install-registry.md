# 📦 安装注册表 — Install Registry

> 本文件记录所有工具/Skill/扩展的安装、卸载记录。
> 每次安装或卸载，按时间倒序追加，无论换什么模型都能读取。
> 格式：时间、名称、来源/地址、依赖、安装路径、是否成功、备注。

---

## 2026-08-06

### ✅ 配置：doubao-seedream-5.0-lite 接入 image_generate 工具
- **时间**：2026-08-06 07:56 CST
- **触发**：点点要求把图生从 agnes-image-2.1-flash 换成豆包方案（最近生图一直用豆包）
- **变更**：
  - `agents.defaults.imageGenerationModel.primary`：`litellm/agnes-image-2.1-flash` → `volcengine-agent/doubao-seedream-5.0-lite`
  - `models.providers.volcengine-agent.models` 新增 `doubao-seedream-5.0-lite` 声明
  - `agents.defaults.models` 注册表新增该模型
- **API 端点**：`https://ark.cn-beijing.volces.com/api/plan/v3/images/generations`
- **实测**：HTTP 200 / 18.4s / 1920x1920 出图成功
- **备份**：`~/.openclaw/openclaw.json.bak-20260806-075354`
- **是否成功**：✅ `openclaw config validate` = Config valid
- **待办**：需重启 gateway 才生效（主会话内不可重启，CASE-012）
- **坑点留痕**：provider models 数组 `additionalProperties: False`，写 `output: ["image"]` 会导致 `validate` 报 `models.3: Invalid input`。合法字段用 `openclaw config schema` 查，required 仅 `id`+`name`

### ✅ 实测追记：Agnes 国内址 api.agnes-ai.cn 可用
- **时间**：2026-08-06 07:52 CST
- **背景**：配置里 baseUrl 已是国内址，但**换址 + 实测通过的记录一直没留痕**（grep 全仓库 `agnes-ai.cn` 零命中），本次补上
- **实测结果**：
  | 目标 | 结果 |
  |---|---|
  | `api.agnes-ai.cn` + agnes-2.5-flash | ✅ HTTP 200 / 0.47s / 正文正常 |
  | `api.agnes-ai.cn` + agnes-2.0-flash | ⚠️ HTTP 200 但 content 空 / finish_reason=length |
  | `apihub.agnes-ai.com`（老址） | ❌ HTTP 000 / 12s 超时 / 解析到 Teredo 保留段 |
- **结论**：老端点彻底不可路由（与 8-05 model.yaml 事故同源）；国内址可用

### ✅ 配置：compaction 切换到 agnes-2.5-flash（修静默丢数据隐患）
- **时间**：2026-08-06 07:56 CST
- **变更**：`compaction.model` + `compaction.memoryFlush.model`：`litellm/agnes-2.0-flash` → `litellm/agnes-2.5-flash`
- **真正原因**：不是版本升级。agnes-2.0-flash 实测 HTTP 200 但 `content` 为空、`finish_reason=length`、token 全烧在 `reasoning_content`、`text_tokens: 0`。挂在 compaction 上 = 压缩结果为空、上下文静默丢失且不报错
- **形态参考**：CASE-20260706-004（stopReason=length 死锁）
- **是否成功**：✅ validate 通过，待重启生效

---

## 2026-08-03

### ✅ 安装：cyclonedx-bom (SBOM 生成工具)
- **时间**：2026-08-03 11:15 CST
- **触发**：Mark42 接入 SBOM（软件物料清单）生成能力
- **来源**：PyPI (`pip install cyclonedx-bom`)
- **安装命令**：`pip3 install --break-system-packages cyclonedx-bom`
- **版本**：7.3.1（cyclonedx-python-lib 11.11.0）
- **安装路径**：`~/.local/lib/python3.12/site-packages/`（用户安装）
- **依赖**：cyclonedx-python-lib, packageurl-python, pip-requirements-parser, jsonschema, lxml, license-expression 等
- **是否成功**：✅ 已验证，SBOM 生成成功（147 个组件，CycloneDX 1.6 JSON）
- **备注**：
  - CLI 命令为 `cyclonedx-py`，子命令式语法（environment / requirements / pipenv / poetry）
  - 安装时 lxml 下载较大（5.2MB），首次 OOM 被杀，第二次成功
  - 已创建 `mark42-pkg/scripts/generate-sbom.sh` 生成脚本
  - 已在 `.github/workflows/mark42-ci.yml` 新增 `sbom` job（continue-on-error: true, 保留 30 天）
  - 已写说明文档 `mark42-pkg/docs/SBOM.md`

## 2026-07-29

### ✅ 升级：火山方舟 Agent Plan Medium -> Large
- **时间**：2026-07-29 08:05 CST
- **触发**：点点升级套餐，解锁视频生成能力
- **套餐**：Agent Plan Large（¥500/月，250,000 AFP）
- **新增能力**：
  - Seedance 2.0 全系列视频生成（标准版/Fast/Mini）
  - 火山 Supabase（AI-Native 数据库）
  - 250,000 月度 AFP
- **验证结果**：✅ 视频生成测试通过（Seedance 2.0 标准版，~2分钟出片）

### ✅ 已安装：byted-ark-seedance-skill（豆包 Seedance 视频生成）
- **时间**：2026-07-29（更早安装，Large 套餐后正式可用）
- **来源**：官方 Skill 仓库
- **安装路径**：`~/.openclaw/workspace/skills/byted-ark-seedance-skill/`
- **版本**：4.0.0，作者 volcengine/agentplan
- **视频模型**：doubao-seedance-2.0 / 2.0-fast / 2.0-mini / 1.5-pro
- **API 端点**：`https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks`
- **是否成功**：✅ 2026-07-29 测试通过

### ✅ 参数确认：Seedream 图片生成 watermark 参数
- **时间**：2026-07-29 08:16 CST
- **发现**：API 默认带「AI生成」水印，需传 `watermark: false` 关闭
- **之前记录**：误以为是套餐差异导致水印消失，实际是参数问题
- **已更新文件**：`docs/非主模型使用手册.md` + `MEMORY.md`

### ✅ 配置：Agnes 2.5 Flash（免费对话模型）
- **时间**：2026-07-29 09:06 CST
- **触发**：点点看到 Agnes 2.5 Flash 已上线，要求配置上
- **来源**：已有 Agnes API Key（`credentials/api/agnes.env`），新增模型到 openclaw.json
- **API 端点**：~~`https://apihub.agnes-ai.com/v1`~~ → **已改国内址 `https://api.agnes-ai.cn/v1`**
- **模型名**：`agnes-2.5-flash`（litellm 通道：`litellm/agnes-2.5-flash`）
- **参数**：512K 上下文 / 65536 输出 / 支持 text+image 输入
- **费用**：$0/百万 token（免费）
- **当前状态**：✅ **可用**（2026-08-06 实测追记，见下方 08-06 条目）
- ~~⚠️ Agnes API 服务器连接超时（2026-07-29 09:06 测试），配置已就绪，待服务器恢复即可用~~
- **已知问题**：老端点 `apihub.agnes-ai.com` 已彻底不可路由（解析到 Teredo 保留段），**必须用国内址**

## 2026-07-27

### ✅ 安装：自主决策器（mark42-autonomy）
- **时间**：2026-07-27 16:16 CST
- **触发**：点点提出做一个小模型，自主决定何时主动发起对话
- **来源**：自建
- **安装路径**：`scripts/autonomy/`
- **核心模块**：`autonomy.py`（7维特征加权 + sigmoid决策）
- **配置文件**：`config.json`（权重 + 阈值 + 防刷屏参数）
- **状态文件**：`state.json`（运行时状态）
- **日志文件**：`decisions.jsonl`（每次决策留痕）
- **systemd 服务**：`mark42-autonomy.timer`（每5分钟跑一次）
- **权重初始化**：从72个daily文件统计生成
- **集成方式**：触发时通过 `openclaw system event` 注入主会话
- **防刷屏**：冷却30min / 每日上限3次 / 勿扰22-7点
- **备注**：不是AI模型，是加权决策器。未来可升级为小MLP或加强化学习

---

## 2026-07-21

### ✅ 安装：byted-ark-tts-skill（豆包 Seed TTS 2.0 语音合成）
- **时间**：2026-07-21 15:30 CST
- **触发**：点点要求配置语音回复能力
- **来源**：自定义构建（官方无预构建 TTS Skill）
- **安装路径**：`~/.openclaw/skills/byted-ark-tts-skill/`
- **主脚本**：`scripts/tts.js`
- **API 端点**：`https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional`
- **鉴权方式**：`X-Api-Key` 头（复用 Agent Plan 的 ark- key）
- **资源 ID**：`seed-tts-2.0`
- **默认音色**：`zh_female_sophie_uranus_bigtts`（魅力苏菲 2.0）
- **是否成功**：✅ 已验证可正常合成
- **计费**：5 元/万字符，走 Agent Plan 额度
- **排查记录**：
  - `Authorization: Bearer` -> `app key not found`，改用 `X-Api-Key` 解决
  - `voice_type` 字段 -> `resource ID mismatched`，改用 `speaker` 字段解决
  - `seed-tts-1.0` + TTS 2.0 音色 -> `resource not granted`，必须用 `seed-tts-2.0`
  - TTS 1.0 音色（BV001_streaming 等）在 plan 套餐下不可用
- **特色功能**：支持情绪指令 `#指令#` 控制语气（温柔/吵架/哭腔/ASMR 等）
- **输出目录**：`~/.openclaw/workspace/media/tts/`

### ✅ 安装：byted-ark-seedream-skill（豆包 Seedream 5.0 lite 图片生成）
- **时间**：2026-07-21 14:00 CST
- **触发**：点点要求配置生图能力
- **来源**：官方 Skill 仓库 `https://skills.volces.com/skills/volcengine/agentplan`
- **安装路径**：`~/.openclaw/skills/byted-ark-seedream-skill/`
- **版本**：3.0.0，作者 volcengine/agentplan
- **生图模型**：doubao-seedream-5.0-lite
- **API 端点**：`https://ark.cn-beijing.volces.com/api/plan/v3/images/generations`
- **默认保存路径**：`~/.openclaw/workspace/media/Seedream-Images/`
- **是否成功**：✅ 已验证可正常生图
- **排查记录**：
  - 直接调用 API -> `AuthenticationError (API key format is incorrect)`，需通过 Skill 处理认证
  - 默认保存到桌面 -> OpenClaw webchat 无法显示（`Outside allowed folders`），已修改脚本保存到 workspace/media/

---

## 2026-07-20

### ✅ 升级：OpenClaw v2026.7.1 -> v2026.7.1-2 + Branding 脚本适配
- **时间**：2026-07-20 08:20 CST
- **触发**：点点看到系统提示可升级
- **操作**：升级 + branding 脚本修复
- **方式**：`systemd-run --user --collect --wait openclaw update --yes`（通过 systemd-run 绕过 gateway 自身重启冲突）
- **旧版本**：`2026.7.1 (2d2ddc4)`
- **新版本**：`2026.7.1-2 (0790d9f)`
- **安装路径**：`~/.npm-global/lib/node_modules/openclaw/`
- **是否成功**：✅ 升级成功

**升级后发现问题：**

1. **Brandig 脚本 ExecStartPre 失败**：`apply-openclaw-control-ui-branding.py` 报 "未能定位聊天页补丁入口"
   - **根因**：v2026.7.1-2 前端改用 Vite 代码分割，聊天逻辑从 `index-*.js` 拆到独立 `chat-page-*.js` chunk；所有函数名全变，6 个历史版本适配都匹配不上
   - **修复**：在 branding 脚本中新增 v2026.7.1 版本适配分支
     - 文件扫描：新增 `chat-page-*.js` glob 匹配
     - 函数映射：`Bl`=isHidden, `ql`=mergeHistory, `O`=roleNormalize, `G`=textExtract, `ps`=stripPrefix, `Lb`=unwrap, `Pi`=shouldSkip, `Rb`=isSending
     - 注入 Jarvis helper 函数（yielded history replay + pending reading indicator）
     - "无效重载" bug：新版本已原生修复（`hasActiveRun===!0` 时直接 return，不调 reload），不再需要补丁
   - **修复后**：ExecStartPre 退出 0 ✅

2. **Gateway 重启卡在 deactivating**：升级时 gateway 停止过程超时
   - **处理**：`systemctl --user kill --signal=SIGKILL` 强制终止后正常重启
   - **根因**：gateway 内运行中的会话/任务阻止优雅退出

**修改的文件：**
- `scripts/apply-openclaw-control-ui-branding.py`：新增 v2026.7.1 适配分支（~60 行）

---

## 2026-06-23

### ✅ 配置：trae-agent 接通 OpenRouter + GPT-OSS-120B Free
- **时间**：2026-06-23 17:21 CST
- **触发**：点点给 trae-agent 配 OpenRouter API key（刚申请的真 key）
- **关键转折**：原配置 key `sk-cf2…9fa9`（35 字符 OpenAI 格式，非 OpenRouter）→ 401 Missing Authentication header；后改 `***` → 404（:free 限流）
- **最终方案**：模型改成 `openai/gpt-oss-120b:free`（OpenAI 官方开源，120B，OpenRouter 0$/M prompt+completion，1M context）
- **备选测试**（都不限流的免费模型）：
  - ✅ `openai/gpt-oss-120b:free`（3.6s）— 选这个
  - ✅ `nvidia/nemotron-3-super-120b-a12b:free`（1.3s，但中文啰嗦）
  - ❌ `qwen/qwen3-coder:free`（41-58s 后 429 Venice 限流）
  - ❌ `meta-llama/llama-3.3-70b-instruct:free`（41s 后 429）
- **烟测结果**：`trae-cli run "写 hello.py"` → 5 步、13474 tokens、Success ✅、hello.py 真写出来
- **配置位置**：`~/trae-agent/trae_config.yaml`（api_key 73 字符 sk-or-v1-... 完整真 key，未 mask）+ `~/trae-agent/.env`（chmod 600 备份）
- **.gitignore**：`.env` 已在 ignore 列表，trae_config.yaml 未 tracked（untracked 状态）
- **备注**：trae-agent 启动命令 `source ~/trae-agent/.venv/bin/activate && trae-cli run "任务"`；总费用 = $0；OpenRouter 控制台 `https://openrouter.ai/activity` 实时看

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


### trae-agent-engineering（2026-06-23 提案）

- **名称**：trae-agent-engineering
- **状态**：✅ applied（`trae-agent-engineering-20260623-17dd43031d`），贾维斯工程任务默认加载
- **Skill 来源**：贾维斯自创（skill_workshop → create）
- **关联工具**：`bytedance/trae-agent` v0.1.0（已装好：`~/trae-agent/`）
- **用途**：封装 trae-cli 标准调用流程，贾维斯工程任务默认走这条
- **触发**："让 trae 改"、"调 trae"、"用 trae 重构"、"修这个 bug"、"加这个功能"、"跑测试"、大型多文件项目
- **不触发**：单文件一句话改、聊天、查状态
- **核心流程**：检查 trae 就位 → `trae-cli show-config` 验证 → 用 `~/trae-agent/jarvis-trae.sh` 调 → 看轨迹 → 验证改动 → 报告
- **3 个坑固化**：401（占位 key）/ 404（provider: openai 改 openrouter）/ 缺字段（top_k + parallel_tool_calls）
- **配套**：trae_config.yaml 标准模板走 DeepSeek V4 Flash
- **备注**：✅ 已于 2026-06-23 11:53 apply。贾维斯以后遇到工程任务自动走这套流程。

## 2026-07-16

### ✅ 配置：火山方舟 Agent Plan 接入 GLM-5.2
- **时间**：2026-07-16 08:49 CST
- **触发**：点点买了火山方舟 Agent Plan 套餐，给新 key
- **endpoint**：`https://ark.cn-beijing.volces.com/api/plan/v3`（注意：不是 `coding/v3`，也不是 `/v3`）
- **key**：`ark-4c81407d-…-6a338`（46 字符）
- **模型**：`glm-5.2`（真实版本 `glm-5-2-260617`，1M 上下文，支持 thinking）
- **接入方式**：openclaw.json -> models.providers.`volcengine-agent` -> baseUrl + apiKey
- **OpenClaw fallback**：#4 (`ark-code-latest`) + #5 (`glm-5.2`)
- **Mark42 advisor**：model.yaml -> advisor.enabled=true, model=glm-5.2
- **备份**：`~/.openclaw/credentials/.volcengine-agent.key`（chmod 600）
- **备注**：另有 Coding Plan key `ark-482b…4975d`，但 Coding Plan 不允许通用 API 调用（违规封号），暂存不用

### ✅ 配置：Mark42 model.yaml 从 stub 切到 api
- **时间**：2026-07-16 09:51 CST
- **改动**：consciousness.runtime: stub -> api, model: agnes-2.0-flash
- **原因**：本机 7.7G 内存跑不了 Qwen3-4B，先用 Agnes 2.0 flash 云端 API 替代
- **可插拔**：以后换回本地模型改 1 行配置（runtime: ollama），代码不用动

---

## AIRI (moeru-ai/airi) - 2026-07-21 收藏

- **仓库**: https://github.com/moeru-ai/airi
- **Stars**: 42,899
- **描述**: 自托管 AI 虚拟伴侣，实时语音 + Minecraft/Factorio 游戏 + Live2D/VRM 形象
- **技术栈**: TypeScript / Vue.js / ONNX Runtime / WebGPU
- **仓库大小**: ~507 MB
- **状态**: 收藏待装。本机内存 7.7G 偏紧，clone 时 OOM。等硬件升级或换机后再装
- **日期**: 2026-07-21

---

## compaction-notifier 中文 Hook - 2026-07-29 启用

- **时间**: 2026-07-29 12:05 CST
- **类型**: OpenClaw Hook（managed，覆盖内置）
- **位置**: `~/.openclaw/hooks/compaction-notifier/`（HOOK.md + handler.js）
- **事件**: `session:compact:before` / `session:compact:after`
- **功能**: compact 开始/结束时发送中文聊天通知，纯脚本不经过模型
- **消息**: `🧹 正在压缩对话～！一会说～！` / `✅ 压缩完成（X -> Y tokens），继续聊～！`
- **覆盖**: 内置英文版 compaction-notifier
- **状态**: 已启用，已验证

## Mark42 v2.8.1 四大可用性修复 - 2026-07-29

- **时间**: 2026-07-29 14:30 CST
- **类型**: Mark42 包修复
- **提交**: 5c8131ae
- **变更**:
  1. **安装器**: 同步 44->75 .py 文件, 新增 audit/interfaces/plugins 子包, pip install -e . 成功
  2. **配置向导**: user_config.py 新增 interactive_init(), CLI --init 接入
  3. **用户文档**: QUICKSTART.md + TUTORIAL.md + INDEX.md + README.md 导航
  4. **错误处理**: 6 模块加 logging + openclaw.json 写入加备份回滚
- **安装方式**: `cd mark42-pkg && pip install -e . --break-system-packages`
- **验证**: mark42 --version -> v2.7.0, 80 测试全过, openclaw.json 未变
- **状态**: 已安装, 已推送 master

## 2026-08-03（补充）

### ✅ 安装：opentelemetry-api / opentelemetry-sdk / opentelemetry-exporter-otlp-proto-http / prometheus-client
- **时间**：2026-08-03 11:21 CST
- **触发**：Mark42 接入可观测性（OpenTelemetry + Prometheus）
- **来源**：PyPI（清华镜像源）
- **安装命令**：`pip install --user --break-system-packages opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http prometheus-client`
- **版本**：opentelemetry 1.44.0 / prometheus-client 0.26.0 / protobuf 7.35.1
- **安装路径**：`~/.local/lib/python3.12/site-packages/`
- **是否成功**：✅ 已验证，Prometheus 指标在 :9471/metrics 正常暴露
- **备注**：
  - Mark42 核心仍为零第三方依赖，这些是可选依赖（pyproject.toml optional-dependencies）
  - 未安装时 telemetry 模块自动降级为空操作，不影响运行
  - 启用方式：`MARK42_METRICS_ENABLED=1` / `MARK42_TRACING_ENABLED=1`

## 2026-08-05 卸载：openclaw-embed-venv312（Python 3.12 遗留 venv）

- **路径**：`/mnt/data/openclaw/openclaw-embed-venv312`
- **大小**：5.1G（nvidia 2.7G + torch 1.2G + triton 700M 等纯依赖库）
- **创建**：2026-06-12，创建后从未被任何服务引用
- **删除原因**：Python 3.12 环境搭建遗留物。实际在用的是 `embed-venv311`（1.3G，经 `~/.local/share/openclaw-embed-venv311` 软链被 embed-sidecar 引用）
- **零引用核查**（全部无命中）：systemd 系统级+用户级单元 / openclaw.json / workspace scripts / mark42 / shell rc / crontab / 反向软链扫描 / 运行进程 / lsof。唯一命中项为当日会话记录本身，非代码引用
- **无独有资产**：目录内无 .bin/.safetensors/.pt/.onnx 大模型文件，模型权重位于 `/mnt/data/openclaw/huggingface`，不受影响
- **删除流程**：先 `mv` 改名隔离 → 重启 embed-sidecar 验证 → healthz/encode/search 三项功能验证 → 确认无误后 `rm -rf`
- **验证结果**：sidecar active、model_loaded true、index_segments 10748（与删除前一致）、encode 正常、语义 search 正常（记忆检索链路通）
- **磁盘**：/mnt/data 由 13G/27% 降至 7.4G/16%，释放 5.1G
- **注**：health-collector / lifecycle-maintainer 两单元 failed 属当日既有状态（今日已失败 52 次 / 9 次，最早失败早于本次操作），经 grep 确认不引用该 venv，与本次删除无关

## 2026-08-05 修复：两个 systemd 单元长期 failed（3 个独立根因）

### 根因 1：lifecycle-maintainer 调用已删除的 ChatTTS 清理脚本（真凶）
- **现象**：`openclaw-lifecycle-maintainer.service` exit 1 → failed，当日已失败 9 次
- **根因**：`tools/chattts-on-demand/cleanup-old-audio.sh` 不存在。ChatTTS 下线换豆包 TTS 时目录被删，但 lifecycle-maintainer 里的调用未同步移除
- **副作用**：现役 `tools/cleanup-tts.sh` 未被任何调度调用 → media/tts 过期音频长期无人清理
- **修复**：`scripts/openclaw-lifecycle-maintainer.py` 中 `chattts-cleanup` 改为 `tts-cleanup`，指向 `tools/cleanup-tts.sh`（清理 media/tts 下超 4 小时 wav/mp3）

### 根因 2：embed-sidecar 裸 socket 短读 → 向量索引增量更新长期失败
- **现象**：`embed-index` 子检查每次报 `sidecar unavailable: HTTP Error 400`
- **误判排除**：报错栈顶是 `urlopen(timeout=120)`，看似超时；实际响应体是 `{"ok":false,"error":"invalid JSON"}`
- **根因**：`scripts/embed-sidecar.py` 用 `makefile('rb', buffering=0)` 裸 socket，`rfile.read(content_len)` 不保证一次读满。请求体超过约 128KB（TCP 缓冲区边界）被截断成非法 JSON。memory-embed-index 按 100 段/批发送，中文段落常达 190KB+，故**每次必中**
- **阈值实测**：170 条/120KB 通过，184 条/130KB 失败（非固定上限，随 TCP 缓冲抖动）
- **修复**：改为 `while remaining > 0` 循环读满，遇连接提前关闭 break
- **顺带**：413 报错文案 "max 500 texts" 与实际上限 200 不符，已订正为 "max 200"
- **影响**：此 bug 导致向量索引长期停在 10748 段，近期记忆未进语义索引。修复后增量重建成功，**10748 → 15194 段（新增 4446）**，耗时 136s

### 根因 3：health-collector 的 stuck-session-detect 超时被判 failed（告警噪声）
- **现象**：`TIMEOUT(20s)` → exit 1 → failed，当日已失败 52 次
- **实测**：脚本单独运行仅 **45ms**，exit 0。超时仅发生在主会话被长任务占用、读会话状态被拖慢时
- **逻辑矛盾**：该检查职责就是"检测主会话阻塞"，却因被检测现象本身而判定整个采集器崩溃
- **修复**：`scripts/openclaw-health-collector.py` 新增 `TIMEOUT_TOLERANT_CHECKS = {"stuck-session-detect"}` 白名单，命中者超时降级为 degraded（同 exit 2 语义）——仍记日志、仍反映在 overall=⚠，但不再让单元 exit 1；超时预算 20s→30s

### 验证结果
- 三脚本 py_compile 通过
- 大请求体验证：130KB/184条、140KB/199条 均 OK（修复前 400）
- lifecycle-maintainer 手动运行 exit 0，7 项检查全 OK
- health-collector 手动运行 exit 0，stuck-session-detect 耗时 137ms
- systemd 启动两单元 ExecMainStatus 均为 0
- **failed 单元数：2 → 0**
- sidecar 重启后 index_segments=15183，语义检索可命中当日内容
- **注**：sidecar 无 reload 接口，索引在启动时一次性载入，重建索引后需 restart 才生效

## 2026-08-05 排查修复：冷启动 Gateway 长时间不可达（用户侧表现「启动不了」）

### 现象（用户描述）
关机做备份 → 开机 → 打开 Control UI 连不上 → 手动 `openclaw gateway restart` 后恢复正常。

### 根因：不是故障，是冷启动过慢（机械盘 + 开机 I/O 争抢）
- `sda` / `sdb` 均为**机械盘**（`rotational=1`），调度器 mq-deadline
- OpenClaw 包 **371M**（dist 97M），冷启动需大量随机读
- 开机 2 分钟内有 **322 个** systemd 启动事件同时争抢磁盘
- **稳定复现规律**（node fork 后到首行日志的静默时长）：

| 冷启动 | systemd Started | node 首行日志 | 静默 |
|---|---|---|---|
| 8-04 07:36 | 07:36:51 | 07:38:40 | **109s** |
| 8-05 12:09 | 12:09:32 | 12:10:54 | **82s** |
| 8-05 13:18 | 13:18:57 | 13:20:45 | **108s** |

- 对照：缓存热后的重启仅 **0.9~3s**（相差 50~70 倍）→ 瓶颈确定为冷态磁盘 I/O
- **误导性关键点**：单元为默认 `Type=simple`，systemd 在 13:18:57 即报 "Started"，
  但那只代表 fork 成功，此时端口未 listen。这是「看起来启动不了」的直接原因
- 本次时间线巧合：Gateway 13:20:56 listen，用户 13:21:02 敲 restart（仅差 6 秒），
  restart 之所以 0.9s 完成，是因前 108s 已把文件缓存烧热

### 排除项（均已实测，非本次原因）
- compile-cache 未被开机清理（`/var/tmp/openclaw-compile-cache` 7-31 建，238M/41163 文件）
- 无端口冲突（无 EADDRINUSE）
- 无 OOM（内存峰值 578M / 上限 4.5G）
- `NRestarts=0`，服务本身未崩溃
- resume-watch 未参与（今日最后动作 07:46）
- journal 中大量 `error|timeout` 命中行均为 `timeoutMs=600000` 参数名误匹配

### 修复 1：boot-health-check 启动注入必然失败（真 bug）
- **现象**：13:19:20 报 `[boot] 启动事件注入失败: ... timed out after 15 seconds`
- **根因**：脚本 13:18:57 启动、13:19:20 就调 `chat.inject`，比 gateway 就绪（13:20:56）**早 96 秒**；
  原 `timeout=15` 在冷启动场景下必然超时 → **开机启动消息从未成功送达**
- 原有 `check_gateway_port()` 只探 TCP 连通，不足以判定会话层就绪
- **修复**：新增 `wait_gateway_ready()` 双探针
  - 第一道 HTTP `/health`（实测 **23ms**，比 `config.get` 的 4458ms 轻两个数量级）
  - 第二道 `openclaw gateway status --json`（实测 1444ms，给 30s 余量）确认会话层可用
  - 最长等 240s，interval 5s；inject 自身 timeout 15s → 60s
- **实测**：就绪判定耗时由 9.8s 降至 **1.2s**，返回 `ready=True, waitedSeconds=0`
- **配套**：原单元 `TimeoutStartSec=60` 会在 60s 掐死等待逻辑，
  新增 drop-in `openclaw-boot-health-check.service.d/cold-boot-wait.conf` 放宽至 **300s**（已验证 TimeoutStartUSec=5min）

### 修复 2：提高 Gateway 冷启动 I/O 优先级
- 新增 drop-in `openclaw-gateway.service.d/cold-boot-io-priority.conf`
- `IOSchedulingClass=best-effort` + `IOSchedulingPriority=0`（默认为 4），在开机争抢中优先拿磁盘
- realtime 类（class 1）需 root，用户级 systemd 不可用（`ionice -c 1` → Operation not permitted），故取 best-effort 最高档
- **已验证生效**：`IOSchedulingPriority=0`
- **未重启 Gateway**（遵守 CASE-20260706-003：不得从主会话内 restart gateway）

### ⚠️ 过程中自查拦下的一个风险（重要）
初版 drop-in 曾写入 `Nice=-5`，随后实测发现：
本机 `ulimit -e = 0`，普通用户**无权设置负 nice**（`nice -n -5` → Permission denied），
`/etc/security/limits.conf` 未配置 nice 提升。若保留该行，**下次开机 Gateway 会因无权限直接启动失败**——
把「启动慢」升级成真正的「启动不了」。已在写入后立即移除并 daemon-reload 验证（`Nice=0`）。
如需 CPU 优先级提升，须先配 `missyouangeled - nice -5` 并重新登录验证。

### 遗留与建议
- I/O 优先级只能**缩短**、无法消除静默期，受机械盘物理限制
- 彻底解决方向：换 SSD；或将 gateway 单元改 `Type=notify` 让依赖单元准确等待就绪（改动较大，未做）
- 下次冷启动应观察：静默时长是否下降、是否能正常收到「系统已就绪」消息

### 排查中的一次误判（自我记录）
最初把 13:21:02 那次重启归因于 mark42-bootstrap 连带停止 gateway，并据此解读为「重启问题」。
用户指出实际是「冷启动起不来、手动 restart 才恢复」后才修正方向。
教训：日志里 `Stopping mark42-* → Stopping openclaw-gateway` 的相邻关系是**手动 restart 触发的连带停止**，
不能仅凭时间相邻就推断因果；应优先向用户确认操作序列，再定因果方向。
