# 🔑 贾维斯中枢 — API 密钥归属清单

> 创建：2026-06-15
> 用途：记录所有已配置 API key 的归属（个人/公司/免费），统一换密钥时从这里定位。
> 原则：新密钥接入时必须同时更新此清单。

---

## 一、当前密钥总览

| 归属 | Provider ID | Base URL | Key 掩码 | 模型 |
|------|-------------|----------|---------|------|
| 🏢 **公司** | `deepseek-company` | `https://api.deepseek.com` | `sk-fd48***fb1c` | `deepseek-v4-pro`（Company-DeepSeekV4pro） |
| 👤 点点个人 | `deepseek` | `https://api.deepseek.com` | `sk-da15***912e` | `deepseek-chat`、`deepseek-reasoner`、`deepseek-v4-pro` |
| 🆓 免费 | `nvidia` | `https://integrate.api.nvidia.com/v1` | `nvapi-a12***cHxb` | nemotron / gemma 等（NVIDIA NIM 免费额度） |
| 🆓 免费 | `ollama` | `http://192.168.18.13:11434` | 无 | gemma4 等（点点老电脑本地 GPU） |
| 🔧 服务 | `litellm` | `https://apihub.agnes-ai.com/v1` | `sk-AcI8***vWio` | Agnes 图像生成/理解（LiteLLM 通道） |

## 二、当前使用策略

| 场景 | 使用 | 扣费来源 |
|------|------|---------|
| Agent 默认模型（新建会话） | `deepseek-company/deepseek-v4-pro` | 🏢 公司 |
| 当前主会话 | `deepseek-company/deepseek-v4-pro` | 🏢 公司 |
| 聊天中手动切 "DeepSeek V4 Pro" | `deepseek/deepseek-v4-pro` | ⚠️ 点点个人 |
| 聊天中手动切 "Company-DeepSeekV4pro" | `deepseek-company/deepseek-v4-pro` | 🏢 公司 |
| DeepSeek Chat / Reasoner 轻量任务 | `deepseek/deepseek-chat` | 👤 点点个人（极便宜） |
| 图像理解 | `litellm/agnes-2.0-flash` | 🔧 Agnes 服务 |
| 图像生成 | `litellm/agnes-image-2.1-flash` | 🔧 Agnes 服务 |
| 本地大模型 | `ollama/*` | 🆓 免费（点点老电脑电费） |
| NVIDIA 模型 | `nvidia/*` | 🆓 免费 |

## 三、统一换密钥操作指南

当需要把「公司买的 API」全部换成新的时：

### 3.1 修改位置（仅一处）

**文件**：`~/.openclaw/openclaw.json`

**路径**：`models.providers.deepseek-company.apiKey`

```bash
# 替换公司 DeepSeek API key
python3 -c "
import json
with open('$HOME/.openclaw/openclaw.json') as f:
    data = json.load(f)
data['models']['providers']['deepseek-company']['apiKey'] = 'sk-新的key'
with open('$HOME/.openclaw/openclaw.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print('已更新')
"
# 重启 Gateway 生效
openclaw gateway restart
```

### 3.2 验证

```bash
# 确认 agent 默认模型指向公司 provider
python3 -c "import json; d=json.load(open('$HOME/.openclaw/openclaw.json')); print(d['agents']['defaults']['model']['primary'])"
# 应输出: deepseek-company/deepseek-v4-pro
```

### 3.3 注意事项

- 个人 key（`deepseek` provider）**不要动**——那是点点自己买的，不算"公司的 API"
- 如果要新增其他公司购买的 provider（如公司买的 Claude、公司买的 Gemini），也按同样模式：单独建 provider、在此清单登记
- 换完后 `openclaw gateway restart` 生效

## 四、历史变更

| 日期 | 变更 |
|------|------|
| 2026-06-15 | 初版。修复 agent 默认模型从个人 key 切到公司 key。登记全部 5 个 provider。 |
| 2026-06-15 | 🔍 全面审计：发现 embed-sidecar 健康检查每 5 分钟用公司 key 跑一次 LLM（288次/天纯浪费），已禁用改为 systemd；早安/午餐/晚间问候从个人 deepseek-chat 切到公司 key（晚间已因个人欠费连续失败）；清理 5 个僵尸 cron jobs。 |
