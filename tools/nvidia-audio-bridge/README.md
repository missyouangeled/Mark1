# NVIDIA Audio Bridge（公司 Linux）

- 适用机器：公司（Linux）
- 系统 / OS：Linux
- 文档类型：本机专用运行说明

## 用途

这套 bridge 用来把 OpenClaw gateway 本身没有原生暴露好的 NVIDIA 免费语音能力，转成当前机器本地可用的 HTTP 路径：

- `POST /v1/audio/speech`
- `POST /v1/audio/transcriptions`

设计目标是：

1. 主 gateway 继续跑在 `127.0.0.1:18789`
2. bridge 单独跑在 `127.0.0.1:18890`
3. 通过 gateway 补丁把音频请求代理到 bridge
4. 出问题时优先排查 bridge / 补丁，不影响主聊天链路的定位思路

## 仓库内文件

- 服务代码：`tools/nvidia-audio-bridge/bridge.py`
- 依赖清单：`tools/nvidia-audio-bridge/requirements.txt`
- systemd 模板：`tools/nvidia-audio-bridge/openclaw-nvidia-audio-bridge.service`
- gateway 补丁：`scripts/apply-openclaw-nvidia-audio-gateway-patch.py`
- 维护总说明：`docs/公司-Linux-OpenClaw-维护说明.md`

## 当前机器已验证环境

- bridge venv：`~/.local/share/openclaw-nvidia-audio-bridge-venv`
- 当前 service 路径：`~/.config/systemd/user/openclaw-nvidia-audio-bridge.service`
- 当前 bridge 地址：`http://127.0.0.1:18890`
- 当前 gateway 地址：`http://127.0.0.1:18789`

已确认当前 venv 中至少可导入：

- `fastapi==0.136.1`
- `uvicorn==0.46.0`
- `nvidia-riva-client==2.25.1`
- `python-multipart==0.0.27`

## 前置条件

1. `~/.openclaw/openclaw.json` 中已有可用的 `models.providers.nvidia.apiKey`
2. 本机能访问 `grpc.nvcf.nvidia.com:443`
3. 本机能访问 `api.nvcf.nvidia.com`
4. 本机有可用的 ffmpeg（本脚本也支持当前用户目录下的本地 ffmpeg 兜底路径）

## 推荐落地步骤

### 1. 准备 Python 环境

如果直接复用当前约定路径，建议：

```bash
python3.11 -m venv ~/.local/share/openclaw-nvidia-audio-bridge-venv
~/.local/share/openclaw-nvidia-audio-bridge-venv/bin/python -m pip install -r tools/nvidia-audio-bridge/requirements.txt
```

如果机器上没有 `python3.11 -m venv`，也可以按本机实际 Python 3.11 方案创建等价环境，但最终要保证 `openclaw-nvidia-audio-bridge.service` 指向的解释器路径真实可用。

### 2. 安装用户态 systemd service

```bash
mkdir -p ~/.config/systemd/user
cp tools/nvidia-audio-bridge/openclaw-nvidia-audio-bridge.service ~/.config/systemd/user/openclaw-nvidia-audio-bridge.service
systemctl --user daemon-reload
systemctl --user enable --now openclaw-nvidia-audio-bridge.service
```

### 3. 给 OpenClaw 打 gateway 音频补丁

```bash
python3 scripts/apply-openclaw-nvidia-audio-gateway-patch.py
```

### 4. 重启 bridge 与 gateway

```bash
systemctl --user restart openclaw-nvidia-audio-bridge.service
openclaw gateway restart
```

## 最小验证

### 1. bridge 健康检查

```bash
curl -s http://127.0.0.1:18890/health
```

预期：返回包含 `"ok": true`。

### 2. gateway TTS 验证

```bash
python3 - <<'PY'
import json, urllib.request
from pathlib import Path
cfg=json.load(open(Path.home() / '.openclaw' / 'openclaw.json'))
token=cfg['gateway']['auth']['token']
req=urllib.request.Request(
    'http://127.0.0.1:18789/v1/audio/speech',
    data=json.dumps({
        'model':'nvidia/magpie-tts-multilingual',
        'input':'Hello from nvidia gateway bridge test.',
        'voice':'aria',
        'response_format':'mp3'
    }).encode(),
    headers={'Content-Type':'application/json','Authorization':f'Bearer {token}'}
)
with urllib.request.urlopen(req, timeout=120) as resp:
    body=resp.read()
    print(resp.status, resp.headers.get_content_type(), len(body))
PY
```

预期：`200 audio/mpeg`，并返回非空字节数。

### 3. gateway ASR 验证

可先用上一步生成的 mp3，再发到 `/v1/audio/transcriptions`。如果整链路正常，当前这台机器已验证过能回出：

```text
Hello from nvidia gateway bridge test.
```

## 常用维护命令

```bash
systemctl --user status openclaw-nvidia-audio-bridge.service
systemctl --user restart openclaw-nvidia-audio-bridge.service
journalctl --user -u openclaw-nvidia-audio-bridge.service -n 100 --no-pager
```

## 故障优先排查顺序

如果 gateway 音频接口重新变成 `404` / `502` / 超时，按这个顺序查：

1. `systemctl --user status openclaw-nvidia-audio-bridge.service`
2. `curl http://127.0.0.1:18890/health`
3. OpenClaw 升级后，补丁是否被覆盖（重跑 `python3 scripts/apply-openclaw-nvidia-audio-gateway-patch.py`）
4. `~/.openclaw/openclaw.json` 的 `models.providers.nvidia.apiKey` 是否还有效
5. 本机对 NVIDIA NVCF / gRPC 的网络是否通畅

## 注意

- 这是**公司（Linux）** 当前使用的本机补丁方案，不是 OpenClaw 官方稳定配置项。
- 不要把 NVIDIA API key 写死进 repo；bridge 会从 `~/.openclaw/openclaw.json` 读取现有 key。
- 不要提交 `__pycache__`、本地 venv、测试音频或临时产物。
