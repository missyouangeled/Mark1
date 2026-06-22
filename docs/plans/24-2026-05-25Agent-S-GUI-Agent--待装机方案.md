## 2026-05-25：Agent-S GUI Agent — 待装机方案

### 来源
用户提问"能识别 GUI 操控桌面的方案"，搜索评估后确定 Agent-S 为当前最优解。

### 项目
- **名称**：Agent-S（Agent S3）
- **仓库**：https://github.com/simular-ai/Agent-S
- **安装**：`pip install gui-agents`
- **平台**：Linux / Windows / macOS 全支持
- **原理**：截图 → AI 视觉理解 → 坐标定位 → 鼠标键盘操作
- **战绩**：OSWorld 72.60%（超过人类），ICLR 2025 最佳论文

### 当前机器审查（公司 Linux）

| 审查项 | 结果 |
|---|---|
| GPU | ❌ VMware SVGA II 虚拟显卡，无 CUDA |
| VRAM | ❌ 无专用显存 |
| RAM | ❌ 7.7GB 总量，UI-TARS-1.5-7B 需 ~7GB |
| 磁盘 | ⚠️ 根盘 74%/13GB |
| 网络 | ❌ 公司防火墙阻断 OpenAI + HuggingFace |
| API Key | ❌ 全未配置 |
| 显示器 | ✅ GNOME+Wayland 正常 |

**结论：❌ 当前机器不能装。**

### 待装机条件
换到有 NVIDIA GPU + 足够显存/内存 + 外网直通的机器后：

```bash
pip install gui-agents
agent_s --provider openai --model gpt-5 \
  --ground_provider huggingface --ground_url http://localhost:8080 \
  --ground_model ui-tars-1.5-7b \
  --grounding_width 1920 --grounding_height 1080
```

### 状态
⏸️ 换机后直接装，无需再次调研。

---
