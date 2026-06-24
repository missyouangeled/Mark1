# 方案：ds4 本地大模型推理引擎（antirez）

> **状态**：🟡 待硬件（不可立即部署）
> **保存日期**：2026-06-24
> **触发**：点点看到 antirez/ds4 项目后，让我调研本地化推理的可能性

## 一句话

ds4 是 Redis 作者 antirez 写的一个**单文件 C 推理引擎**（`ds4.c`，18,404 行），专门跑 **DeepSeek V4 Flash（284B MoE）** 本地模型。核心创新是 **用 SSD 当 KV cache**，让 128GB MacBook 能跑 1M token 上下文。

---

## 关键信息

| 字段 | 值 |
|---|---|
| 仓库 | https://github.com/antirez/ds4 |
| 作者 | Salvatore Sanfilippo（antirez，Redis 作者） |
| 创建时间 | 2026-05-06（1 周做出） |
| Star | 11,000+ |
| License | MIT |
| 状态 | alpha-quality（明确标注） |
| 模型仓库 | https://huggingface.co/antirez/deepseek-v4-gguf |
| 配套 UI | https://github.com/cocktailpeanut/ds4.pinokio |

## 核心特性

- **模型**：DeepSeek V4 Flash（284B MoE），2-bit 量化（**只量化 routed MoE experts**）
- **上下文窗口**：1M token
- **KV cache**：磁盘优先设计（SSD 当一等公民），session 状态可跨重启
- **API**：OpenAI / Anthropic 兼容 HTTP server
- **集成**：支持 Claude Code / opencode / Pi 等 coding agent
- **技术**：MTP speculative decoding、tool/function calling、thinking mode

## 平台支持

| 平台 | 状态 |
|---|---|
| Metal（Apple Silicon） | ✅ 主推 |
| CUDA（NVIDIA） | ✅ |
| ROCm（AMD GPU） | ✅ |
| CPU | ❌ 有 bug（macOS VM bug） |
| Windows | ❌ |

## 硬件要求（核心数字）

| 部件 | 最低要求 | 推荐 |
|---|---|---|
| **内存 / 统一内存** | 128GB（2-bit 量化下能装下 71GB 模型权重） | 192GB+ |
| **GPU** | Apple Silicon（M2+）/ RTX 4090+ | RTX 5090 / M3 Max |
| **SSD** | **NVMe SSD（3-7 GB/s）** | 高速 NVMe |
| **磁盘空间** | ~100GB（模型权重） + KV cache | 1TB+ |

## 关键设计思想（必须理解）

ds4 的"用 SSD 替代显存"**不是替代模型权重，而是替代 KV cache**：

| 项目 | 位置 | 原因 |
|---|---|---|
| **模型权重**（71GB） | 必须常驻 RAM/GPU | 推理时每次都要读，慢了就崩 |
| **KV cache**（历史上下文） | 可放 SSD | 只在生成 token 时读写一次 |

**所以"用 SSD 当 RAM"是真实的，但只针对 KV cache。模型权重这个大头还是必须 RAM/GPU。**

> antirez 推文：DeepSeek v4 小 KV cache + MacBook 快 SSD = 颠覆了"SSD 不适合做 KV cache"的传统观点。

---

## 点点的硬件 vs ds4 要求

| 部件 | 点点配置 | ds4 需要 | 能否替代 |
|---|---|---|---|
| GPU | GTX 1070 (8GB 显存) | 128GB 统一内存 / 24GB+ 显存 | ❌ 不行 |
| 内存 | 8GB RAM | 128GB+ | ❌ 不行（模型权重放不下） |
| 硬盘 | "本地硬盘空间很大" | **NVMe SSD 3-7 GB/s** | ⚠️ 未知（可能是机械盘） |
| 总可用 | 16GB (RAM+VRAM) | 128GB+ | ❌ 差 8 倍 |

**结论**：点点当前电脑**跑不了 ds4**。但 ds4 的设计思想很值得关注——以后如果升级硬件（128GB+ 内存 / Apple Silicon / 高端 NVIDIA），这是少数能完全离线跑 284B 模型的方案。

---

## 跟贾维斯的关系

| 维度 | 当前贾维斯 | ds4 化后 |
|---|---|---|
| 模型 | MiniMax-M3（云端 API） | DeepSeek V4 Flash（本地） |
| 隐私 | 走云端 | **零数据泄露** |
| 成本 | 免费（云） | 一次性硬件投入 |
| 速度 | 看网络 | 看 SSD 速度 |
| 上下文 | 受 API 限制 | 1M token |
| 部署复杂度 | 现成 | 编译 C + 70GB 模型下载 |

**触发本地化的可能场景**：
1. 公司项目要求隐私隔离（不能让对话上云）
2. 离线场景（无网络 / 隔离网）
3. 长期使用成本对比

---

## 阻塞 & 待办

- [ ] 确认点点那块老电脑的硬盘类型（NVMe / SATA SSD / 机械）
- [ ] 关注 ds4 后续发布（项目 4 天 7k star，发展很快）
- [ ] 关注反方观点：Reddit benchmark 显示 30GB KV cache 下 64k-100k token 上下文就有上限
- [ ] 如硬件到位，安装步骤：
  1. 装 Metal / CUDA / ROCm runtime
  2. `git clone https://github.com/antirez/ds4 && cd ds4 && make`
  3. 下载 GGUF：`https://huggingface.co/antirez/deepseek-v4-gguf`
  4. 启动 server：`./ds4 --model deepseek-v4-flash.gguf`

---

## 信息来源

- GitHub 仓库主 README
- 搜索结果：
  - 第一次搜索（5 条结果）：daily.dev、HN 镜像、towardsai 评测、pinokio 启动器
  - 第二次搜索（5 条）：antirez 推文（KV cache 设计）、Reddit 实际 benchmark（30GB 内存限制）、YouTube Prism Labs 视频介绍
- 评测文章："I Tested antirez's ds4 on 18 Tasks"（towardsai，作者 Chew Loong Nian）

---

**最后更新**：2026-06-24 11:08
**记录人**：贾维斯（响应点点："那把 ds4 这个方案保存"）