## 2026-05-25：tavily-key-generator — API Key 自动注册器

### 来源
用户提问 `skernelx/tavily-key-generator`，搜索评估后决定暂不安装。

### 项目
- **名称**：tavily-key-generator
- **仓库**：https://github.com/skernelx/tavily-key-generator
- **用途**：自动批量注册 Tavily / Firecrawl / Exa 免费 API Key
- **原理**：真实浏览器自动化 → 填表注册 → 过 Turnstile → 邮箱收码 → 提取 Key → 真实验证

### 当前机器审查（公司 Linux）

| 审查项 | 结果 |
|---|---|
| Python | ✅ 3.12.3 |
| Chrome | ✅ 已装 |
| 内存 | ⚠️ 可用 4.3GB，Chrome 吃内存 |
| 磁盘 | ⚠️ 根盘 74%/13GB |
| pip3 | ❌ 未装 |
| chromedriver/selenium/playwright | ❌ 未装 |
| 网络（目标服务） | ✅ firecrawl.dev / exa.ai / tavily.com / api.cloudflare.com 能通 |
| 邮箱 | ⚠️ 需配 Cloudflare Mail API 或 DuckMail |
| 可用服务 | Tavily ❌（注册入口已关）/ Firecrawl ✅ / Exa ✅ |

### 状态
⏸️ 暂不装。哪天需要批量薅 Firecrawl/Exa Key 时再说。

---
