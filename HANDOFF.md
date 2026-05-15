# HANDOFF.md - Model / Agent Handoff

如果以后更换 AI 大模型、代理、运行时，先读这个文件，再继续工作。

## 当前默认接手方式

## 当前临时高优先级接手任务（broker / infos-handle 收尾与下周续做入口）

- 任务目标：把 `broker sidecar 数据层 1.0` + `infos-handle 查询契约层` 在当前阶段收成一个稳定停点，保证下周一回来可以直接沿着 machine-readable contract 继续推，而不是重新扫仓库找口径。
- 当前机器：`missyouangeled-VMware-Virtual-Platform` / `公司（Linux）`
- 截至 2026-05-15 17:50 的收口判断：**当前阶段主体已完成，按开发主体看约 90%；现在更适合停在 handoff / 文档 / GitHub 备份前一步，而不是继续开第四刀。**

### 当前已确认结论

1. **broker 当前已可视为本阶段可交付的 sidecar 数据层 1.0**
   - 已落地：`events.jsonl` / `manifest.json` / `views/frontstage.json` / `views/health.json` / `views/tasks.json` / `views/recovery.json`
   - 前台链路真烟测已通过：
     - `frontstage-recovery -> broker -> 当前前台`：通过
     - `supervisor -> broker -> 当前前台`：通过
   - 当前 broker manifest 已在位，`schemaVersion: 1`、`contractVersion: 2`

2. **infos-handle 当前主干已经成型，且查询契约连续收紧到可直接消费的程度**
   - 当前已支持：
     - `snapshot.summary`
     - `health.summary`
     - `tasks.summary`
     - `recovery.summary`
     - `panel.inspect`
     - `panels.catalog`
     - `sources.latest`
     - `sources.catalog`
     - `source.inspect`
     - `events.recent`
     - `contract.catalog`
   - 2026-05-15 下午到 17:50 前，这条线连续完成了：
     - `sources.catalog` / `source.inspect` 稳定顶层字段收口
     - `sources.latest` 的 `count / availableSources / sourceItems[]` 收口
     - `panel.inspect` / `panels.catalog` 已纳入正式 query catalog
     - broker 事件契约正式化，`contract.catalog` 可直接带出 `contracts.recordTypes / contracts.eventFieldCatalog`
     - `events.recent` 稳定 item shape 收口，并新增 `latestBySource`
   - 当前 `QUERY_CONTRACT_VERSION = 13`
   - 当前 `brokerContractVersion = 2`

3. **这轮最后一个本地代码停点已经存在，可直接从这里续做**
   - 当前代码停点提交：`7396ede` `Tighten broker and infos-handle event contracts`
   - 其前一串关键提交：
     - `eb8aa4f` `Tighten infos-handle source query handoff contract`
     - `3aa091e` `Tighten infos-handle sources.latest contract`
     - `7fe7efd` `Tighten infos-handle source event summaries`
     - `ff07c2f` `Tighten infos-handle source inspect summaries`
     - `2575456` `Tighten infos-handle source catalog contract`
     - `4de50fb` `Add panels catalog query to infos handle`
     - `a862517` `feat: add panel inspect query to infos-handle`
     - `2f57998` `feat: add infos-handle source catalog contract`

4. **当前验证结果保持全绿**
   - `python3 scripts/test-openclaw-infos-handle.py` → `ALL PASS`
   - `python3 scripts/test-frontstage-broker.py` → `ALL PASS`
   - `python3 -m py_compile scripts/openclaw-infos-handle.py scripts/test-openclaw-infos-handle.py scripts/openclaw-frontstage-broker.py scripts/test-frontstage-broker.py` → 通过
   - live 查询也已确认：
     - `python3 scripts/openclaw-infos-handle.py query --kind events.recent --format json` → 返回 `result.latestBySource`
     - `python3 scripts/openclaw-infos-handle.py query --kind contract.catalog --format json` → 当前返回 `queryContractVersion=13 / brokerContractVersion=2`

### 还没做、但下周一最自然的下一步

按优先级建议：

1. **先做收尾文档同步，而不是继续开新 query**
   - 补齐 `events.recent.latestBySource` 在 README / 说明里的最终口径
   - 检查 `PLANS.md` / `tools/openclaw-frontstage-broker/README.md` / `HANDOFF.md` 三处描述是否完全对齐

2. **如果文档已齐，再决定要不要补有序 shape**
   - 可评估是否给 `events.recent` 增加 `latestBySourceItems[]`
   - 目的只是提供稳定顺序；不要替代现有 keyed object

3. **继续坚持小步 contract-first 路线**
   - 只收 machine-readable 输出面
   - 不碰主对话链
   - 不做 broker / renderer 大拆

### 明天/下周一继续时的最短恢复路径

1. `git log --oneline -5`
2. `git status --short`
3. 读：`PLANS.md`
4. 读：`tools/openclaw-frontstage-broker/README.md`
5. 读：`memory/daily/2026-05-15.md`
6. 跑：
   - `python3 scripts/test-openclaw-infos-handle.py`
   - `python3 scripts/test-frontstage-broker.py`
7. 再决定是先补 README 对齐，还是补 `latestBySourceItems[]`

### 当前边界与注意事项

- 当前这轮**已经有本地 commit，但还没有 push 到 GitHub**；若要满足“系统性修改后及时 GitHub 备份”的偏好，下一步应在用户确认后 push。
- 当前工作区里还存在一些与本轮无关的脏文件（如 ChatTTS 相关试验脚本、dream/memory 自动写入等）；继续提交时应继续按路径精确 add，不要一锅端。
- 2026-05-15 下午出现过一轮 dashboard transcript 锁竞争（`SessionWriteLockTimeoutError` / `session file locked`），已按最保守方式修复并归档旧 dashboard transcript 残留；后续若前台再次频繁出现同类锁超时，优先考虑切新前台会话继续，必要时再重启 gateway。

## 当前临时高优先级接手任务（ChatTTS encoder 补全 / 中文语音链路）

- 任务目标：确认当前公司 Linux 机上的 ChatTTS 是否能从“decoder-only 候选方案”补成“带 encoder 的更完整方案”，从而恢复参考音频编码 / 更完整的 zero-shot 能力。
- 当前机器：`missyouangeled-VMware-Virtual-Platform` / `公司（Linux）`
- 截至 2026-05-08 17:14 的收口判断：**18:00 前完成“补全 + 验证”概率偏低，已先做续做记录，明天继续更稳。**

### 当前已确认结论

1. **当前 hybrid 方案已经能出中文，且听感通过**
   - 复现脚本：`tmp/voice-replies/chattts-run-hybrid.py`
   - 样本产物：`tmp/voice-replies/chattts-hybrid-infer.wav`
   - 用户试听反馈：`效果相当真实。可以。`
   - 但目前仍未切成默认中文语音回复链路，只保留为“已验证可用的候选方案”。

2. **当前本地 `DVAE_full.pt` 实际并不 full，本质上仍是缺失编码侧的混合方案**
   - 已直接检查 `tmp/voice-replies/chattts-hybrid/asset/DVAE_full.pt`
   - 结果：`encoder.* = 0`、`downsample_conv.* = 0`、`preprocessor_mel.* = 0`；同时存在少量 `vq_layer.*`，但这仍不足以跑完整编码链
   - 因此当前能说话主要是因为走了 decoder 路径，不是完整 encoder→decoder / sample-audio 链路。

3. **“能不能补全”取决于是否拿到版本匹配的完整官方资产**
   - 外部公开线索显示 `2Noise/ChatTTS` 资产列表里存在 `DVAE.safetensors`、`Decoder.safetensors`，并且有 `add DVAE with encoder` 相关提交痕迹。
   - 因此：理论上**有机会补全**；但前提是拿到**与当前运行时/配置匹配**的完整 DVAE 权重。
   - 不能靠补脚本“造出” encoder；如果拿不到对版资产，只能继续维持当前 decoder-only 路线。
   - **新增现实约束（2026-05-08 晚）**：当前机器 shell 直连 GitHub 会报 `Connection reset by peer`，直连 Hugging Face 会报 `Network is unreachable`；所以后续不要默认指望本机直接在线拉模型，优先考虑“宿主机浏览器下载 → 临时上传页传入当前机器”这条已验证工作流。
   - **最新进展（2026-05-08 17:57）**：用户已通过临时上传页把 `DVAE.safetensors` 与 `Decoder.safetensors` 传入当前机器，存放于 `tmp/upload-drop/chattts-20260508/`。已本地验货确认：
     - `DVAE.safetensors`：`encoder.* = 113`、`decoder.* = 113`、`downsample_conv.* = 4`、`preprocessor_mel.* = 2`、`vq_layer.* = 8`
     - `Decoder.safetensors`：仍是 decoder-only
     - 这说明：**我们已经拿到一份真正带编码侧权重的官方 DVAE 候选资产**，明天不需要再花时间找文件，直接进入“兼容加载测试 → sample_audio/zero-shot 验证”阶段。
   - **续做结果（2026-05-09 07:53）**：方案 A 已在当前公司 Linux 机完成第一轮功能性验证：
     - 已把官方 `DVAE.safetensors` 转成新的 `tmp/voice-replies/chattts-full-attempt/asset/DVAE_full.pt`
     - 其中 24 个 `decoder_block.*.weight` 键已按当前运行时需要，改名为 `decoder_block.*.gamma`；改名后本地 `DVAE` 模型 `load_state_dict(..., strict=False)` 的结果为 `missing=0 / unexpected=0`
     - 由于文件内容被重写，本地脚本里需要绕过 ChatTTS 的 asset sha 校验；这属于“本地兼容加载补丁”，不是原始官方哈希通过
     - 当前已新增复现脚本：`tmp/voice-replies/chattts-run-plan-a.py`
     - 随后又把流程进一步收成了两段正式入口：
       - 资产准备：`tmp/voice-replies/chattts-prepare-plan-a-assets.py`
       - 运行时兼容补丁：`tmp/voice-replies/chattts_plan_a_compat.py`
       - 说明文档：`tmp/voice-replies/README-chattts-plan-a.md`
     - 此外，`Decoder.safetensors` 也已被验证只存在同类 `weight -> gamma` 命名差异；修正后可直接转成当前运行时可加载的 `Decoder.pt`，所以当前 `tmp/voice-replies/chattts-plan-a-runtime/` 已经可以使用“官方 DVAE + 官方 Decoder（经键名修正转换）+ 现有 GPT/Embed/Vocos/tokenizer 资产”的更干净组合，不再依赖 hybrid 目录里的旧 `Decoder.pt`
     - 已成功验证三段链路：
       1. 普通 TTS：`tmp/voice-replies/chattts-plan-a-normal.wav`
       2. `sample_audio_speaker()` 编码：已成功产出 `spk_smp`（长度 `720`）
       3. zero-shot 路径：已成功产出 `tmp/voice-replies/chattts-plan-a-zero-shot.wav`
     - 中途唯一新增兼容坑是：`soundfile` 读出的参考音频默认是 `float64`，传给 `sample_audio_speaker()` 会在 torchaudio mel 变换处报 `double != float`；转成 `np.float32` 后已恢复正常
     - 当前结论：**方案 A 已经不只是“理论可行”，而是“在本机 CPU 上能完成完整的 sample-audio / zero-shot 功能链验证”**
     - 仍保留的 caveat：加载 GPT 时仍会看到一组旧有 `UNEXPECTED/MISSING` 提示（`embed_tokens.weight` 等），但后续源码核对后可更准确地理解为：当前 ChatTTS 本来就是把 `emb_code.* / emb_text.weight / head_code.* / head_text.*` 这些键放在单独的 `Embed.safetensors` 里，而 `GPT.from_pretrained()` 内部又是先用 Hugging Face `LlamaModel.from_pretrained(gpt_folder)` 只加载基础主干；因此日志里的 `UNEXPECTED` 与 `embed_tokens.weight MISSING` 更像这套“主干 GPT + 独立 Embed 头”拆分资产的加载提示，而不是这轮方案A特有的失败信号。结合当前普通 TTS 与 zero-shot 产物都已成功落地，可暂视为已知噪声，而非本轮 encoder 补全的主阻塞
     - 另一个新确认点：`tmp/voice-replies/chattts-run-plan-a.py` 现在已经能直接读取外部 `mp3` 参考音频并自动重采样到 `24k`，`sample_audio_speaker()` 可成功产出 `spk_smp`；但若 `txt_smp` 不是该参考音频的**精确转写**，当前实测 zero-shot 可能会在起步阶段直接报 `unexpected end at index [0]` / `StopIteration`
     - 这个缺口随后已经被真正补上：2026-05-09 08:08 左右，我联网搜索后锁定了 `AISHELL-3 Baseline Samples`（`https://sos1sos2sixteen.github.io/aishell3/`）这组公开中文样本。该页面直接给出样本音频与对应中文文本，OpenSLR `SLR93` 页面同时确认了 `Apache License 2.0`
     - 我已从网页源码中提取并下载三条公开样本到本地：
       - `tmp/voice-replies/public-ref-samples/aishell3/raw1.wav` → `在教学楼内释放大量烟雾`
       - `tmp/voice-replies/public-ref-samples/aishell3/raw2.wav` → `不过英特尔之后不会继续接受如此大的损失`
       - `tmp/voice-replies/public-ref-samples/aishell3/raw3.wav` → `替我播放相思风雨中`
       - 转写汇总：`tmp/voice-replies/public-ref-samples/aishell3/TRANSCRIPTS.md`
     - 随后已直接用 `raw3.wav + 替我播放相思风雨中` 成功跑通真实外部参考 zero-shot，产物：`tmp/voice-replies/chattts-plan-a-aishell3-raw3-zero-shot.wav`
     - 用户接着要求按“先做2，再做1”的顺序继续。我先额外搜索了更像真实聊天口吻的公开来源，并确认三类高价值候选：
       1. `MagicHub / RAMC`：网页可直接拿到 conversational sample 音频，但网页正文未直接暴露对应文本
       2. `Hugging Face` 对话切片（例如搜索结果能看到 `Izzyzlin/CFSDD` 这类口语化文本）：文本风格非常自然，但当前机器 shell 直连 HF / datasets-server 仍然 `Network is unreachable`
       3. `Chinese Dialogues / COERLL`：对话型且带转写，但实际资源落在 Google Drive，更适合后续通过宿主机浏览器挑取
     - 然后我已补跑 AISHELL-3 另外两条公开样本：
       - `raw1.wav + 在教学楼内释放大量烟雾` → `tmp/voice-replies/chattts-plan-a-aishell3-raw1-zero-shot.wav`
       - `raw2.wav + 不过英特尔之后不会继续接受如此大的损失` → `tmp/voice-replies/chattts-plan-a-aishell3-raw2-zero-shot.wav`
     - 到此，AISHELL-3 当前已下载的三条公开样本 `raw1/raw2/raw3` 都完成了一轮真实外部参考 zero-shot 验证
     - 因此当前结论可以进一步升级为：**方案A 已经能稳定用“互联网上找到的公开中文参考样本 + 精确转写”完成多条真实外部参考 zero-shot 验证**

### 为什么今天 18:00 前不建议硬冲

- 剩余工作不只是下载一个文件，而是：
  1. 找到真正带 encoder 的官方资产
  2. 验证其内部键是否完整
  3. 与当前 v0.2.x 运行时做兼容测试
  4. 再验证普通 TTS / 参考音频编码 / zero-shot 路径
- 这一步存在网络、版本匹配、依赖兼容三层不确定性；为了避免 18:00 前仓促得出假结论，先收口记录更稳。

### 明天继续时的最短路径

> 详细方案、外部核实结果、实施顺序与风险边界，见 `PLANS.md` 新增章节：`2026-05-08：ChatTTS encoder 补全与 zero-shot 恢复方案`
> 其中已补充一节：`VMware 虚拟机使用宿主 GPU 的核实结论`

- **关于 VMware GPU 的最新拍板**：
  - 当前这台 VM 本地实测只看到 `VMware SVGA II Adapter [15ad:0405]`，驱动是 `vmwgfx`，`nvidia-smi` 不存在；因此**当前这台 VMware 客体不能视为已经具备可用的宿主 GPU 计算能力**。
  - 公开资料核实后，结论应区分：
    - `VMware Workstation/Fusion`：通常只有 3D 图形加速，不等于 guest 获得真实 CUDA 计算卡
    - `vSphere/ESXi`：可以通过 `VMDirectPath I/O` 或 `NVIDIA vGPU` 让 VM 使用 GPU，适用于 AI / ML 负载，但这是另一层基础设施方案
  - 所以：**不要把“当前 VMware VM 启 GPU”当成明天 ChatTTS 的主线前提**；主线仍是 encoder 补全与 zero-shot 验证。GPU 化如果要做，单独立项更稳。

1. 优先获取官方完整 `DVAE.safetensors` 或真正带 encoder 的 `DVAE_full.pt`
2. 先不跑大推理，先只检查权重键是否包含：
   - `encoder.*`
   - `vq.*`
   - `downsample_conv.*`
   - `preprocessor_mel.*`
3. 若键完整，再接到当前 `ChatTTS v0.2.x` 运行时做最小加载测试
4. 若加载通过，再测：
   - 文转语音
   - 参考音频编码
   - 是否恢复更完整的 zero-shot 音色能力
5. 若任一步失败，则明确收口为：
   - 当前这台机器上 **ChatTTS 维持 decoder-only 候选方案**
   - 默认中文语音回复链路继续保持现有方案，不擅自切换

## 当前临时高优先级接手任务（掌机 OpenClaw / 微信回复链路）

- 任务目标：让 `掌机（Windows）` 上的 OpenClaw 达到“稳定可用 + 微信插件能稳定回复”，而不只是“能启动”。
- 当前机器：`TABLET-EH5U3CO1` / `掌机（Windows）`
- 远程接管方式：公司 Linux 机通过 SSH 连接 `GOG@100.122.111.6`（密钥：`~/.ssh/id_ed25519_openclaw_handheld`）

### 截至 2026-05-06 晚上的当前结论

1. **启动主故障已部分收敛**
   - 原先最明显的启动卡死与 `github-copilot` 默认模型链路有关。
   - 已在掌机配置 `C:\Users\GOG\.openclaw\openclaw.json` 中改为：
     - `agents.defaults.model.primary = deepseek/deepseek-chat`
     - 移除默认模型里的 `github-copilot/gpt-5.4`
     - `plugins.entries.github-copilot.enabled = false`
     - `plugins.entries.github-copilot.config.discovery.enabled = false`
   - 对应备份：
     - `C:\Users\GOG\.openclaw\openclaw.json.bak-20260506-1505`
     - `C:\Users\GOG\.openclaw\openclaw.json.bak-20260506-1526-stability`

2. **微信插件“收消息”是通的，但“回复执行”会把 gateway 拖挂**
   - 日志已确认微信消息能进入 gateway：有 `inbound message` / `bodyLen=2 hasMedia=false`
   - 紧接着出现 `acpx staging bundled runtime deps`
   - 随后出现 `eventLoopUtilization=1`、`active=1 queued=1`
   - 然后 gateway 卡死，之前会被 watchdog 误判重启
   - 结论：当前主问题不是微信收不到，而是**收到微信后，agent / ACPX / 回复执行链路会把 gateway 卡住**

3. **watchdog 已按用户要求彻底移除**
   - 用户明确要求：先删掉 watchdog，避免它继续掩盖根因
   - 已执行：`scripts/uninstall-openclaw-gateway-watchdog.ps1`
   - 当前 `OpenClaw Gateway Watchdog` 计划任务已不存在
   - 相关记录已写入 `docs/掌机-Windows-OpenClaw-维护说明.md`

4. **当前现场状态并不稳定，且到傍晚又回到了启动失败态**
   - 17:05 之后的日志可见：
     - `loading configuration…`
     - `resolving authentication…`
     - `starting...`
   - 17:24 曾出现：`Gateway restart timed out after 180s waiting for health checks.`
   - 截至本次收口前，`openclaw gateway status --deep` 仍可能返回：
     - `Connectivity probe: failed`
     - `connect ECONNREFUSED 127.0.0.1:18789`
   - 这说明：**去掉 watchdog 后，gateway 本体仍存在独立的启动/运行异常，不是只有微信回复这一层**

### 下一步最该做的事

按优先级继续：

1. **先把“当前为什么连 gateway 都起不来”重新钉死**
   - 重点看 17:05 之后这一段日志到底停在什么阶段
   - 不要再让旧结论（下午一度能起来）覆盖晚上的新现场

2. **把“收到微信后触发 ACPX / 回复链路卡死”的问题继续往下切**
   - 重点看：session 元数据已写入，但真正 session 文件/agent run 是否在落盘前就阻塞
   - 重点源码：`selection-ABXC-aG3.js`、ACPX runtime 相关 dist 文件、bundled runtime staging 相关文件

3. **优先尝试低风险修法**
   - 配置级绕过 > 小补丁 > 大改
   - 优先考虑：把 ACPX/runtime 的初始化从“首条微信消息触发”改成“启动前预热/预展开”，避免把回复主链路卡死

### 相关文档 / 提交

- 维护说明：`docs/掌机-Windows-OpenClaw-维护说明.md`
- 相关提交：
  - `979a206` `docs: 记录掌机 GitHub Copilot discovery 启动修复`
  - `9342661` `docs: 更新掌机稳定配置与微信链路说明`
  - `2c020b2` `docs: 记录掌机 watchdog 卸载状态`

当用户说：
- 继续做
- 继续开发
- 接着上次
- 继续纳达尔星项目
- 恢复星云初始03

默认按下面顺序恢复上下文：

1. 读 `PROJECT_VERSIONS.md`
2. 读 `PROJECT_INDEX.md`
3. 读 `memory/YYYY-MM-DD.md`（今天 + 昨天）
4. 如果在主会话里，再读 `MEMORY.md`
5. 查看当前 Git 分支与最近提交
6. 再开始动代码

## 当前主项目

- 项目名：**纳达尔星项目**
- 当前主锚点版本：**星云初始03**
- 当前主要代码目录：`pulsenest-php/`
- 说明：用户已在 2026-04-03 明确要求“用目前这个版本替换星云初始03”，所以从现在开始，星云初始03 默认指向当前这版更成熟、统一、接近成品验收的结果。

## 跨机器恢复口令

以后如果用户在另一台新装好的 OpenClaw 机器上说：

- **恢复 星云初始03全量工作备份**

默认按下面语义执行：

1. 先把当前工作区 Git 仓库同步到 GitHub 最新 `master`
2. 以当前 `星云初始03` 锚点为准恢复纳达尔星项目
3. 一并恢复已进仓的工作日志与工作记忆，包括：
   - `memory/*.md`
   - `.learnings/*.md`
   - `PROJECT_VERSIONS.md`
   - `HANDOFF.md`
   - 项目代码目录 `pulsenest-php/`
4. 先应用 `openclaw-env/restore-skills.sh`，按清单恢复 Skills 本体并自动套用本仓 overlay
5. 再应用 `openclaw-env/restore-openclaw-env.sh`，安装 hooks / systemd 模板并补齐 `.learnings/`

### 这个“全量工作备份”当前不包含什么

下面这些不应默认宣称“自动同步完成”，因为它们目前没有一起进 GitHub 或依赖本机环境：

- SSH key / GitHub key / agent 状态
- `~/.openclaw/hooks/` 的启用状态本身
- `~/.openclaw/openclaw.json` 等机器本地配置
- systemd 服务、运行中的进程、端口监听状态
- 本机安装的软件包 / Node 依赖的运行态缓存

如果用户要“连机器设置都一起恢复”，那属于下一层任务：需要单独做一套**环境引导 / bootstrap 恢复包**。

## 当前已确认的版本语义

### 星云初始03

这是当前默认继续开发、验收、回退的主锚点。

并且它已经被用户在 2026-04-03 用“当前这个更成熟的版本”正式替换过一次，所以不要再把它理解成更早的星云初始03阶段状态。

如果用户说：
- 恢复星云初始03
- 回到星云初始03
- 继续星云初始03

默认以：
- `PROJECT_VERSIONS.md` 中更新后的「星云初始03」描述为准
- Git 最新已确认提交为准

## 当前系统状态（简版）

当前这套 `pulsenest-php/` 已经不只是论坛原型，而是在往可实际上线运营的论坛系统推进，且到 2026-04-03 晚些时候，已经推进到**接近终检状态**，当前继续做的主要是人工验收级微调与“认真运营中的社区产品”细节补层，已包含：

- 用户系统、登录注册、个人中心、公开用户主页
- 发帖 / 评论 / 回复 / 点赞 / 浏览量
- 帖子状态流：published / pending / hidden / draft
- 后台帖子审核队列与批量审核
- 举报系统：帖子 / 评论举报、后台举报队列、筛选、分页、批量处理、联动处置
- 通知闭环：审核结果、举报处理结果、内容状态变化
- 站点设置中心：登录 / 注册 / 举报 / 只读 / 审核 / 内容阈值
- 内容分发：最新 / 综合热度 / 最多回复 / 最多浏览 / 时间窗口热榜
- 首页运营模块：推荐作者、最高浏览、活跃版块、社区即时快照
- 创作者数据：累计获赞 / 浏览 / 回复 / 最近发帖
- 运营后台看板：新增量 / 积压量 / 活跃版块 / 活跃作者 / 举报分布 / 趋势
- 用户治理系统：治理记录、封禁联动停用、状态流转、高风险用户榜单
- staff 单用户治理档案页：`/user-governance.php?id=...`

## 当前预览方式

当前预览地址：

- 局域网访问：`http://192.168.233.130:8093/`
- 后台：`http://192.168.233.130:8093/admin.php`

当前预览服务已做成常驻：

- systemd 用户服务：`pulsenest-preview.service`
- 启动脚本：`scripts/pulsenest-preview.sh`

常用命令：

```bash
systemctl --user status pulsenest-preview.service
systemctl --user restart pulsenest-preview.service
systemctl --user stop pulsenest-preview.service
```

## 当前用户偏好（重要）

用户明确希望：

- **系统性修改后，要及时提交并推送到 GitHub 备份**

所以当一次改动已经达到“系统性修改”的程度时：

1. 先整理版本锚点 / 说明
2. 再 `git commit`
3. 再推送 GitHub

## 当前 Git 参考

后续继续前，建议先看：

```bash
git log --oneline -5
git status --short
```

## 接手时建议对用户说的话（简版）

你可以直接这么理解任务：

- 继续纳达尔星项目
- 以 `星云初始03` 为当前主锚点
- 在当前工作区和 Git 最新状态上继续开发
- 优先沿着“可实际上线运营的论坛系统”方向推进

## 最近 3 个最自然开发方向

如果用户没有指定下一步，就优先从下面 3 个方向里选一个继续：

1. **终检级真机复看与单点修正**
   - 继续按真实数据量检查首页、提醒中心、帖子详情、作者页、会员中心
   - 只修那些“已经很好但还差一点”的边角
   - 避免再做系统性结构改动

2. **认真运营中的社区产品细节补层**
   - 继续补用户成长感、创作者状态、互动承接、低打扰运营提示
   - 保持轻玻璃 / 假玻璃 / 轻阴影路线
   - 不做重功能，只做产品成熟度补层

3. **上线经营前的稳态准备**
   - 检查图片旧资产、极端数据状态、后台个别旧措辞
   - 补恢复包 / 备份清单 / 环境说明
   - 让这套东西更适合长期维护和跨机器恢复

默认优先级判断：
- 用户如果正在盯页面效果 → 优先做终检级真机复看与单点修正
- 用户如果正在盯‘社区像不像在认真运营’ → 优先做社区产品细节补层
- 用户如果在问备份、恢复、长期维护 → 优先做上线经营前的稳态准备

## 注意

- 除非用户明确要求，不要擅自覆盖 `PROJECT_VERSIONS.md` 里旧版本的历史含义
- 如果用户说“用当前版本替换星云初始03”，才更新对应锚点定义
- 做大改前，优先保留可回退路径
