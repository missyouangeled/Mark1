## 2026-05-08:ChatTTS encoder 补全与 zero-shot 恢复方案

### 用途
在当前公司 Linux 机器上,确认 ChatTTS 能否从"已能出中文但仍缺编码侧"的候选方案,补成支持参考音频编码 / 更完整 zero-shot 的可验证方案;并给出一条明天或后天可以直接接着做的可靠路径。

### 当前已确认现状

#### 1. 当前 hybrid 方案已经能出中文
- 复现脚本:`tmp/voice-replies/chattts-run-hybrid.py`
- 当前样本:`tmp/voice-replies/chattts-hybrid-infer.wav`
- 用户试听反馈:**"效果相当真实。可以。"**
- 但这条线当前只证明"基础文转语音可用",还没有证明 sample audio / zero-shot 路径完整恢复。

#### 2. 当前本地 `DVAE_full.pt` 实际并不完整
已本地实测:
- 文件:`tmp/voice-replies/chattts-hybrid/asset/DVAE_full.pt`
- 大小:约 `27 MB`
- 关键键分布:
  - `encoder.* = 0`
  - `downsample_conv.* = 0`
  - `preprocessor_mel.* = 0`
  - `decoder.*` 大量存在
  - `vq_layer.*` 有少量存在

这说明:
- 当前这份文件虽然名叫 `DVAE_full.pt`,但**缺失编码侧关键权重**
- 当前能说话,靠的是 **decoder 路径**,不是完整的 `sample_audio -> encode -> infer -> decode` 路径

#### 3. 当前本地 `Decoder.pt` 是单独解码器资产
- 文件:`tmp/voice-replies/chattts-hybrid/asset/Decoder.pt`
- 大小:约 `99 MB`
- 键分布表现也印证它本质是 decoder-only 资产

#### 4. 当前磁盘空间够做这次验证
- 当前工作盘剩余空间:约 `6.6 GB`
- 当前 `chattts-hybrid/` 目录总大小:约 `1.2 GB`
- 以公开资产体量估算,再增加一份官方完整 DVAE 资产做验证,**空间不是主阻塞**

### 本地源码层面的结论

#### A. ChatTTS 运行时本来就支持"完整 DVAE + 单独 Decoder"两条路
当前本机安装的 ChatTTS 代码显示:
- 配置里同时存在:
  - `asset/DVAE_full.pt`
  - `asset/Decoder.pt`
- `infer(..., use_decoder=True)` 默认走 decoder 路径
- `sample_audio_speaker()` 会调用 `self.dvae.sample_audio(wav)`
- `dvae.sample_audio()` 进一步走 `mode='encode'`
- 而 `encode` 路径要求至少具备:
  - `encoder`
  - `downsample_conv`
  - `preprocessor_mel`
  - `vq_layer`

因此,**当前缺的不是"调个参数",而是 sample audio / zero-shot 所需的编码侧权重本体。**

#### B. 当前本地资产不足以恢复 sample-audio 编码
即使 `vq_layer.*` 部分存在,只要缺了:
- `encoder.*`
- `downsample_conv.*`
- `preprocessor_mel.*`

就无法把参考音频稳定编码成后续所需表示,也就无法把"能说话"升级为"能稳定做 sample audio / zero-shot"。

### 互联网核实结果

#### 1. 官方公开描述本身支持 zero-shot / DVAE encoder
外部公开资料显示,`2noise/ChatTTS` README 摘要中明确写有:
- `Open-source DVAE encoder and zero shot inferring code`
- 同时还提到 streaming / multi-emotion 等能力

这说明:**从项目设计目标上,encoder + zero-shot 不是旁门玩法,而是官方公开过的能力。**

#### 2. 官方公开资产列表里存在完整 DVAE 相关文件
外部公开资料显示,`2Noise/ChatTTS` Hugging Face 资产树包含:
- `DVAE.safetensors`(约 `60.4 MB`)
- `Decoder.safetensors`(约 `104 MB`)
- `Embed.safetensors`
- `spk_stat.pt`

这说明:**公开世界里确实存在比本地这份 `27 MB` 的 `DVAE_full.pt` 更像完整体的 DVAE 资产。**

#### 3. 官方公开提交记录里存在"add DVAE with encoder"
外部公开资料显示,Hugging Face 提交 `45e8f23` 的标题就是:
- `feat: add DVAE with encoder (#26)`
- 摘要里还能看到:`asset/DVAE_full.pt ADDED`

这说明:**"带 encoder 的 DVAE" 不是猜测,而是官方公开历史里真实存在过的资产方向。**

#### 4. 社区 issue 也证明 sample audio / zero-shot 这条链路确实被实际使用过
外部公开 issue 摘要里可以看到:
- 有用户直接调用 `chat.sample_audio_speaker(load_audio(audio_path, 24000))`
- 有关于 `Sample Audio` / `Sample Text` 的实际问答
- 有关于 zero-shot 功能本身报错、相似度、设备兼容的讨论

这说明:**sample audio / zero-shot 在社区层面不是纸面功能,而是有人真实跑过,只是稳定性和环境兼容存在坑。**

### 现实阻塞:当前机器对官方源直连不通
虽然搜索侧能检索到外部公开资料,但本机 shell 直连验证显示:
- 访问 GitHub:`Connection reset by peer`
- 访问 Hugging Face:`Network is unreachable`

这带来一个非常关键的现实判断:

> **从"理论可行性"看,这件事能做;**
> **但从"当前机器能否自主在线拉取官方资产"看,暂时不能直接依赖 shell 自己下载。**

所以后续落地必须二选一:
1. **恢复当前机器到 GitHub / Hugging Face 的可访问状态**
2. **继续沿用已验证过的"宿主机浏览器下载 → 临时上传页传到当前机器"路径,把官方资产人工送进来**

### VMware 虚拟机使用宿主 GPU 的核实结论

#### 先说结论
- **如果说的是当前这台 VMware 虚拟机(桌面虚拟化形态)**:**现在不能把它当成"已经能可靠使用宿主机 GPU 做 ChatTTS / CUDA 计算"**。
- **如果说的是 VMware 整个生态里"虚拟机能不能用宿主 GPU"**:**能,但要分场景**。
  - **VMware Workstation / Fusion 这类桌面虚拟化**:通常只有 **3D 图形加速 / 虚拟显卡加速**,**不等于**把宿主真实 GPU 直接交给客体做 CUDA / PyTorch 计算。
  - **VMware vSphere / ESXi**:可以通过 **VMDirectPath I/O(GPU passthrough)** 或 **NVIDIA vGPU** 把 GPU 能力提供给虚拟机,这条路对 AI / 机器学习工作负载是官方支持过的。

#### 当前这台 VM 的本地实测结果
已直接检查当前客体系统:
- `lspci` 看到的是:`VMware SVGA II Adapter [15ad:0405]`
- 当前加载驱动:`vmwgfx`
- `nvidia-smi`:不存在
- `/sys/class/drm/card0/device/vendor`:`0x15ad`(VMware)

这说明:
- 当前客体拿到的是 **VMware 虚拟显卡**,不是直通后的 NVIDIA / AMD 实卡
- 所以**当前这台 VM 不能直接指望 CUDA / PyTorch GPU 计算**
- 至少在现在这个状态下,**ChatTTS 不应把"改用 GPU"作为当前可立即落地的加速手段**

#### 公开资料核实结果

##### 1. VMware Workstation 的"3D 加速"不等于宿主 GPU 直通
Broadcom 社区关于 `VMware Workstation 17 Pro supports use of host GPU?` 的公开讨论摘要里,明确可见类似结论:
- `No, There is no Host GPU Support while Running Virtual Machines`
- `Only Guest's GPU: VMware SVGA 3D`

这与当前本机实测结果一致:
- 客体里看到的是 VMware SVGA,而不是宿主真实 GPU
- 因此即便宿主 GPU 在后台参与了图形加速,也**不等于 guest 获得了可供 CUDA 使用的真实计算卡**

##### 2. vSphere / ESXi 下,GPU passthrough 是官方明确支持过的
VMware 官方文章 `Using GPUs with Virtual Machines on vSphere - Part 2: VMDirectPath I/O` 明确写到:
- VMDirectPath I/O(passthrough)允许 GPU **directly accessed by the guest operating system**
- 性能可接近原生,文中给出的量级是 **within 4-5%**
- 但该模式下:
  - 每张 GPU 只能专属给一个 VM
  - **不能共享**
  - 并且会失去部分 vSphere 特性,如 `vMotion / DRS / Snapshots`

##### 3. vSphere / ESXi 下,NVIDIA vGPU 也支持计算型 AI 工作负载
VMware 官方文章 `Using GPUs with Virtual Machines on vSphere - Part 3: Installing the NVIDIA Virtual GPU Technology` 明确写到:
- 文章关注点就是 **compute workloads(machine learning / deep learning / HPC)**
- NVIDIA vGPU 需要:
  - ESXi 里的 `NVIDIA Virtual GPU Manager`
  - guest 里的 `NVIDIA vGPU driver`
- 并强调 **版本兼容必须匹配**
- 该路线允许:
  - 一张卡专给一个 VM
  - 或按 vGPU 方式给多个 VM 共享

##### 4. Broadcom / NVIDIA 当前 AI 文档也继续把这条路当正式方案
Broadcom 文档 `Configure NVIDIA vGPU or GPU Passthrough for AI Workloads on the ESX Hosts` 明确写到:
- 可以为 AI workload 配置 `vGPU` 或 `GPU passthrough`
- 文档直接提到:
  - `Deep learning VMs`
  - `Private AI Services`
- NVIDIA vGPU release notes 也明确写了:
  - vSphere 下需要兼容的 `vGPU Manager + guest driver`
  - 版本不兼容时 vGPU 无法加载

因此,**在 VMware 企业级虚拟化(vSphere / ESXi)里,虚拟机使用宿主 GPU 做 AI 计算是现实、官方、可行的。**

#### 关于 RX 6900 XT 本身能不能用
- **能用,但要分运行位置。**
- 这张卡本身并不是"完全不能拿来做 AI / PyTorch / ChatTTS 计算"。
- 我查到的公开线索里:
  - AMD / ROCm 文档检索结果里能看到 `RX 6900 XT` / `gfx1030` 相关条目
  - 相关 ROCm 文档摘要还提到:对 `gfx1030` 的支持存在"**only some operators are supported**"这类限制
- 这意味着:
  - **在宿主机 / 裸 Linux + ROCm 这条线上,RX 6900 XT 有现实可用性**
  - 但它不像更新的 RDNA3/专业卡那样是当前官方宣传主线,兼容性和算子覆盖往往更挑环境

因此更准确的结论不是:
> `RX 6900 XT 不能用`

而是:
> `RX 6900 XT 这张卡可以考虑拿来用,但当前这台 VMware 客体并没有真正拿到它。`

#### 对"可行、可靠、可用"的判断

##### A. 对当前这台 VM 的判断
- **可行性:低(当前状态下不成立)**
- **可靠性:低**
- **可用性:低**

原因:
- 当前没有直通 GPU
- 当前看到的是 VMware 虚拟显卡
- 当前没有 CUDA 设备 / `nvidia-smi`

**结论:不能把"当前这台 VMware VM 直接吃宿主 GPU"当成已可用方案。**

##### B. 对"未来改造成 VMware GPU 计算虚拟机"的判断
- **可行性:高**(前提是换到对的 VMware 形态)
- **可靠性:中到高**(取决于硬件、驱动、许可、版本配套)
- **可用性:高**(一旦配好,对 AI / ML 工作负载是可用的)

但前提必须满足:
1. 不是单纯依赖 Workstation 的 3D 加速
2. 需要进入 **vSphere / ESXi + GPU passthrough** 或 **vSphere / ESXi + NVIDIA vGPU** 路线
3. 宿主硬件、IOMMU/VT-d、GPU 型号、ESXi 版本、驱动版本、许可证都要匹配

#### 这对 ChatTTS 方案意味着什么

##### 当前短期结论
- **不要把"VM 里直接启用宿主 GPU"当成明天的主线**
- 对当前 ChatTTS encoder 补全任务来说,主阻塞仍然是:
  - 完整官方 DVAE 资产进机
  - 跑通 encoder / sample-audio / zero-shot 链路
- 这些步骤**即使继续在 CPU 上,也可以先完成功能性验证**

##### 中期可选增强路线
如果后续希望显著提升:
- 推理速度
- sample audio 编码速度
- 更长文本或更复杂任务的容错

那么可以把"GPU 化"作为**下一阶段的独立基础设施方案**,但应单独立项,不和明天的 encoder 补全混成一件事。

推荐的 GPU 化路线优先级:
1. **优先**:独立一台可控 Linux 实机 / 裸机直接跑 GPU
2. **次优**:vSphere / ESXi + GPU passthrough
3. **再其次**:vSphere / ESXi + NVIDIA vGPU(适合共享场景,但配置复杂、依赖许可)
4. **不建议作为 ChatTTS 计算主路线**:继续指望当前 Workstation 风格 VMware 客体直接拿到宿主 GPU 计算能力

##### 如果将来真的要走 VMware GPU 方案,最低验收标准
只有满足以下全部条件,才算"GPU 在 VM 里可用":
1. 客体 `lspci` 看到的不再是单纯 `VMware SVGA II Adapter`
2. 客体能看到真实 NVIDIA / AMD 计算卡
3. `nvidia-smi`(或对应厂商工具)能正常工作
4. `python -c 'import torch; print(torch.cuda.is_available())'` 返回 `True`
5. ChatTTS / PyTorch 实测能在 GPU 上完成一次完整推理
6. 至少连续多次运行稳定,无驱动重置 / 掉卡 / 兼容性崩溃

#### 最终拍板建议
对当前这个 ChatTTS 任务,建议明确分成两条线:

- **主线(明天/后天继续)**:继续做 `encoder 补全 + zero-shot 恢复`,先不把 VMware GPU 当阻塞前提
- **支线(以后如要提速)**:若你真想让虚拟机吃宿主 GPU 做 AI 计算,应该按 **vSphere / ESXi passthrough / vGPU** 去设计,而不是继续把当前这台 VMware 桌面虚拟机当现成 GPU VM 使用

### 缺少什么
要把当前方案补成更完整体,最少还缺下面这些东西:

#### 1. 一份真正带编码侧权重的官方 DVAE 资产
目标优先级:
1. 官方 `DVAE_full.pt`
2. 或官方 `DVAE.safetensors`

最低验收条件:
- 包含 `encoder.*`
- 包含 `downsample_conv.*`
- 包含 `preprocessor_mel.*`
- 最好同时保有 `vq_layer.*`

#### 2. 一条稳定的"资产进机"路径
当前更可靠的现实方案:
- **优先由宿主机浏览器下载官方资产**
- 再通过已验证的临时上传页传到当前 Linux 机

原因:
- 这条路径今天已经被 Kokoro 文件验证过
- 比在当前 shell 里继续硬啃 GitHub/HF 直连更稳、更可控

#### 3. 一个最小化验货工具
已提前准备:
- `tmp/voice-replies/chattts-inspect-asset.py`

作用:
- 到手任何 `.pt` / `.safetensors` 后,先检查键分布
- 先确认是不是"真 full",再决定是否接入运行时

#### 4. 一份参考音频 + 精确转写
因为社区公开问答明确提到:
- `Sample Text` 需要填写**完全对应的文本转写**
- 任何不完整 / 不准确的转写都会影响结果

所以后续验证 zero-shot 时,必须同时准备:
- 一小段干净参考音频
- 与之严格对应的文字转写

### 推荐实施方案(按可靠性排序)

#### 方案 A:官方完整资产 + 浏览器上传进机(**最推荐**)
这是当前最现实、最可靠的主路径。

步骤:
1. 在可联网的浏览器环境定位官方资产:
   - `DVAE_full.pt` 或 `DVAE.safetensors`
2. 通过宿主机浏览器把文件下载下来
3. 通过临时上传页把文件传到当前机器指定目录
4. 使用:
   - `tmp/voice-replies/chattts-inspect-asset.py`
   先检查键是否完整
5. 若是 safetensors:
   - 先转换成运行时可直接加载的格式,或写一个最小兼容加载分支
6. 先做最小加载测试,不直接跑整条 TTS
7. 若加载通过,再做三段验证:
   - 普通文转语音不回退
   - `sample_audio_speaker()` 能跑
   - `spk_smp + txt_smp` 的 zero-shot 路径能出结果
8. 若任一步失败,立即回滚到当前 decoder-only 候选方案

优点:
- 不依赖当前 shell 恢复外网直连
- 与今天已经验证过的文件上传工作流一致
- 明天继续时最不容易卡死在网络层

#### 方案 B:先修通当前机器到 GitHub / Hugging Face 的直连,再下载官方资产
理论上更自动,但不建议作为明天第一优先级。

原因:
- 当前已实测直连失败
- 先修网络再修模型,变量太多
- 容易把"模型验证任务"拖成"网络排障任务"

适用场景:
- 如果后续确定这台机器长期都要频繁拉模型资产
- 才值得把网络问题单独升级为一条系统任务去修

#### 方案 C:不补全 encoder,维持当前 decoder-only 方案
这是保守兜底路线。

适用结论:
- 如果官方完整 DVAE 资产始终拿不到
- 或者拿到了也与当前 v0.2.x 运行时不兼容
- 或者 zero-shot 成本过高、稳定性太差

那么就明确收口为:
- 当前 ChatTTS 只作为"中文短句文转语音候选方案"
- 不承担 sample audio / 真 zero-shot 目标
- 默认中文语音回复链路继续保持现有更稳方案

### 明天 / 后天的最短执行路径

#### 第一步:拿到官方完整 DVAE 候选资产
优先顺序:
1. `DVAE_full.pt`
2. `DVAE.safetensors`

#### 第二步:先验货,不急着跑模型
命令模板:
```bash
~/.local/share/openclaw-voice-venv311/bin/python3 tmp/voice-replies/chattts-inspect-asset.py <资产路径>
```

只有当输出里明确看到以下项目时,才继续:
- `encoder.*`
- `downsample_conv.*`
- `preprocessor_mel.*`

#### 第三步:做最小加载验证
目标:
- 先确认当前运行时能否接受这份资产
- 不通过就别急着继续大推理

#### 第四步:做功能性三段验证
1. **普通 TTS**:确认不会把当前已能说话的能力搞坏
2. **sample audio encode**:确认 `sample_audio_speaker()` 能跑
3. **zero-shot**:提供短参考音频 + 精准转写,验证 `spk_smp + txt_smp`

#### 第五步:明确结论并锁定状态
只允许三种收口:
1. **补全成功**:encoder 路径恢复,可继续迭代稳定性
2. **资产拿到但不兼容**:记录兼容断点,停止硬冲
3. **资产拿不到 / 网络仍阻塞**:维持 decoder-only 方案,等待下一次输入条件改善

### 成功标准
满足以下全部条件,才算"补全方案阶段成功":
- 能拿到一份真实带编码侧权重的官方 DVAE 资产
- 当前运行时能加载它
- `sample_audio_speaker()` 能完成编码
- zero-shot 路径至少能产出一段可听结果
- 不破坏当前已验证可用的普通中文 TTS 样本能力

### 风险与边界

#### 1. 资产格式不一定能直接即插即用
- 官方公开的是 `.safetensors` / `.pt` 混合生态
- 当前本地运行时偏 `.pt` 路线
- 中间可能还需要格式转换或最小加载补丁

#### 2. 即便补全成功,也不代表立即适合挂默认链路
因为 zero-shot / sample audio 这条路天然更脆:
- 对参考音频质量敏感
- 对文本转写精度敏感
- 对环境依赖也更敏感

所以就算补全成功,也应先视为:
- **"功能恢复成功"**
- 而不是立刻视为:
- **"默认生产链路可以无脑切换"**

#### 3. 当前机器网络条件是外部硬约束
在不修网络、也不走浏览器上传的前提下,这件事**无法靠当前 shell 单独完成**。

### 最终结论
这件事的结论不是"做不到",而是:

> **技术上可行,官方公开资料也能证明这条路存在;**
> **但要在当前机器上可靠完成,必须先解决"完整官方资产如何进机"这个现实前提。**

因此当前拍板建议是:

> **明天/后天优先走"官方完整资产 + 浏览器上传进机 + 本地最小化验证"这条主路径。**

这是目前可行性最高、最不依赖运气、也最容易留下可复现证据的一条路线。

---
