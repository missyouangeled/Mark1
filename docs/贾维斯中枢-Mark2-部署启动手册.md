# 贾维斯中枢 Mark2 — 部署启动手册

> 定位：部署的总入口。本文档是第一份要读的东西。
> 设计日期：2026-06-15
> 适用范围：中枢服务器（Ubuntu 24.04）

---

## 阅读顺序

```
你在这里  →  📋 本手册（预检 + 依赖）
                │
                ├─ 2. 环境预检全通过
                │
                ▼
            📐 服务器迁移方案 v3（架构 + 部署步骤）
            docs/plans/2026-06-15-服务器迁移方案-v3.md
                │
                ▼
            🛡️ 贾维斯中枢安全体系设计（七层纵深防御）
            docs/贾维斯中枢安全体系设计.md
                │
                ▼
            🚀 Mark2 上线
```

**规则**：每一层必须全绿才能进下一层。不允许跳过。

---

## 一、前置确认（租服务器之前就要想清楚的事）

| 项 | 确认内容 | 你的答案 |
|---|---------|---------|
| 云厂商 | 阿里云 / 腾讯云 / 其他 | 待定 |
| 规格 | 8核 32GB 内存 | ✅ 已定 |
| 系统盘 | ≥40GB SSD | 建议 |
| 数据盘 | ≥100GB（挂载 /mnt/data） | 建议 |
| 操作系统 | Ubuntu 24.04 LTS Server（无 GUI） | ✅ 已定 |
| 带宽 | ≥5Mbps（上行） | 最低要求 |
| 域名 | 已有一个域名（例如 yourdomain.com） | **必须先有** |
| DNS 托管 | 域名的 DNS 转到 Cloudflare 管理 | **Cloudflare Tunnel 的前提** |
| 月预算 | ¥400-800 | 待确认 |
| 迁移时间 | 工作日 / 周末 | 待定 |

### ⚠️ 关键前提

1. **域名是硬性依赖**：Cloudflare Tunnel 需要域名解析指向 CF。没有域名 = 整套方案跑不起来。
2. **DNS 必须托管到 Cloudflare**：如果域名已经在其他 DNS 服务商，需要先迁移到 CF（免费，几分钟）。
3. **服务器开通后默认只能用 root + 密码登录**——这就是为什么我们要第一步做 SSH 加固。

---

## 二、环境预检清单（服务器到手后第一件事）

### 2.1 硬件核对

```bash
echo "=== CPU ===" && nproc && lscpu | grep "Model name"
echo "=== 内存 ===" && free -h | grep Mem
echo "=== 磁盘 ===" && lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | grep -E "disk|part"
echo "=== 数据盘 ===" && df -h /mnt/data 2>/dev/null || echo "⚠️ 数据盘未挂载"
```

**预期**：CPU ≥8核、内存 ≥31GB、系统盘 ≥40G、数据盘存在。

### 2.2 系统版本

```bash
lsb_release -a
# 预期: Ubuntu 24.04.x LTS

uname -r
# 预期: 6.x
```

### 2.3 内核安全模块

```bash
echo "=== AppArmor ===" && sudo aa-status 2>/dev/null | head -3 || echo "❌ AppArmor 未安装"
echo "=== SELinux ===" && sestatus 2>/dev/null || echo "SELinux 未启用（Ubuntu 默认不用）"
```

**预期**：AppArmor 已加载且 active。如果 AppArmor 没装，后面依赖装好可以补。

### 2.4 磁盘分区方案

```
/             系统盘 (ext4/XFS)    — 系统 + 包 + 依赖
/mnt/data     数据盘 (ext4/XFS)    — Docker volumes + session-backup + scratch + 备份
```

如果数据盘没挂载，先做：

```bash
# 假设数据盘设备是 /dev/sdb（用 lsblk 确认）
sudo mkfs.ext4 /dev/sdb
sudo mkdir -p /mnt/data
sudo mount /dev/sdb /mnt/data
echo '/dev/sdb /mnt/data ext4 defaults 0 2' | sudo tee -a /etc/fstab
```

### 2.5 网络连通性

```bash
echo "=== DNS ===" && nslookup github.com 8.8.8.8 | tail -3
echo "=== 出站 443 ===" && curl -sI https://github.com 2>&1 | head -1 || echo "❌ 出站 HTTPS 不通"
echo "=== 出站 80 ===" && curl -sI http://archive.ubuntu.com 2>&1 | head -1 || echo "❌ 出站 HTTP 不通"
```

**预期**：DNS 解析正常、HTTPS/HTTP 出站畅通。如果出站被封，找云厂商提工单。

### 2.6 开放端口审计（迁移前基线）

```bash
sudo ss -tlnp
# 此时应该只有 sshd 的 22 端口
# 如果有其他端口——搞清楚是什么，不认识的先关掉
```

### 2.7 当前用户

```bash
whoami && id
```

**预期**：root（刚开通时）。第一件事就是创建 jarvis 用户。

---

## 三、依赖安装清单（按安装顺序）

### 第 1 层：系统基础

```bash
# 创建 jarvis 用户
sudo useradd -m -s /bin/bash jarvis
sudo usermod -aG sudo jarvis
sudo passwd jarvis
# ↑ 设一个强密码（虽然是临时用，SSH 后面会改成仅密钥）

# 基础包
sudo apt update
sudo apt install -y \
  curl wget git vim htop \
  ca-certificates gnupg lsb-release \
  software-properties-common apt-transport-https \
  build-essential pkg-config \
  libssl-dev ffmpeg
```

### 第 2 层：安全包

```bash
sudo apt install -y \
  ufw fail2ban auditd \
  unattended-upgrades
```

### 第 3 层：Node.js（OpenClaw Gateway 运行时）

```bash
# Via NodeSource
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node -v && npm -v
# 预期: node v22.x, npm 10.x
```

### 第 4 层：Docker + Docker Compose

```bash
# Docker
curl -fsSL https://get.docker.com | sudo bash
sudo usermod -aG docker jarvis

# Docker Compose（独立二进制）
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证
docker --version && docker-compose --version

# ⚠️ 重要：记录 Docker Engine 版本
docker version --format '{{.Server.Version}}'
# 如果版本 <29.3.0，等安全更新步骤时会处理
```

### 第 5 层：Caddy（统一网关）

```bash
sudo apt install -y debian-keyring debian-archive-keyring
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
  sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
  sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy

caddy version
# 预期: v2.8+
```

### 第 6 层：Cloudflare Tunnel（cloudflared）

```bash
# 添加 Cloudflare 仓库
curl -fsSL https://pkg.cloudflare.com/cloudflared-key.pub | \
  sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-archive-keyring.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install -y cloudflared

cloudflared --version

# ⚠️ 此时还不能登录（需要 CF Dashboard 配置，在迁移方案步骤 4 再做）
# 只先确认二进制可用
```

### 第 7 层：Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# 登录完验证
tailscale status
# 应显示本机在线
```

### 第 8 层：code-server

```bash
curl -fsSL https://code-server.dev/install.sh | sh

# ⚠️ 安装后先检查版本
code-server --version
# 必须 ≥4.99.4（修复了 CVE-2025-47269 CVSS 8.3）

# 如果版本太低
curl -fsSL https://github.com/coder/code-server/releases/download/v4.99.4/code-server_4.99.4_amd64.deb -o /tmp/code-server.deb
sudo dpkg -i /tmp/code-server.deb
```

### 第 9 层：Python + pip（TTS 推理用）

```bash
sudo apt install -y python3 python3-pip python3-venv
python3 --version && pip3 --version
```

### 第 10 层：docker-socket-proxy（替代 sock 直挂）

```bash
# 不在这一步拉镜像，但确认 Docker 已装好，可以拉取
docker pull tecnativa/docker-socket-proxy
# 容器的启动在迁移方案步骤 6 中做
```

---

## 四、依赖安装总结表

| 序号 | 组件 | 安装方式 | 用途 | 启动时机 |
|------|------|---------|------|---------|
| 1 | 系统基础 | apt | curl/wget/git/vim/build-essential/ffmpeg | 立即 |
| 2 | ufw | apt | 防火墙 | 安装后启用 |
| 3 | fail2ban | apt | SSH 防爆破 | 安装后启用 |
| 4 | auditd | apt | 关键文件变更监控 | 安装后启用 |
| 5 | unattended-upgrades | apt | 系统安全补丁自动装 | 安装后启用 |
| 6 | Node.js 22 | deb.nodesource.com | Gateway 运行时 | 安装完 |
| 7 | Docker CE | get.docker.com | 容器引擎 | 安装后启用 |
| 8 | Docker Compose | GitHub releases | 服务编排 | 需要时 |
| 9 | Caddy | apt (cloudsmith) | 统一网关 | 迁移方案步骤 4 |
| 10 | cloudflared | apt (CF repo) | CF Tunnel | 迁移方案步骤 4 |
| 11 | Tailscale | install.sh | Mesh VPN | 安装后登录 |
| 12 | code-server | install.sh | Web IDE | 迁移方案步骤 5 |
| 13 | Python 3 | apt | TTS 推理 | 安装完 |
| 14 | docker-socket-proxy | Docker pull | Docker API 权限隔离 | 迁移方案步骤 6 |

**注意**：1-8 层属于「预检阶段」就要装好的——系统基础 + 安全 + 容器运行时。9-14 层可以等预检全绿后再装，也可以一起装。

---

## 五、预检扫描脚本（一键跑完所有检查）

把这支脚本放到服务器上，一次性跑完所有前置检查：

```bash
#!/bin/bash
# preflight-check.sh — 贾维斯中枢 Mark2 部署前检查
# 用法: bash preflight-check.sh

set -e
PASS=0
FAIL=0
WARN=0

green() { echo -e "\033[32m✅ $1\033[0m"; PASS=$((PASS+1)); }
red()   { echo -e "\033[31m❌ $1\033[0m"; FAIL=$((FAIL+1)); }
warn()  { echo -e "\033[33m⚠️  $1\033[0m"; WARN=$((WARN+1)); }
check() { echo -e "\n\033[1m--- $1 ---\033[0m"; }

check "1. 硬件规格"
CPU=$(nproc)
MEM=$(free -m | awk '/Mem:/{print int($2/1024)}')
echo "  CPU 核心数: $CPU"
echo "  内存: ${MEM}GB"
[ "$CPU" -ge 8 ] && green "CPU ≥ 8 核 ($CPU)" || red "CPU 不足 ($CPU < 8)"
[ "$MEM" -ge 30 ] && green "内存 ≥ 30GB ($MEM)" || red "内存不足 ($MEM GB < 30)"

check "2. 磁盘空间"
df -h / 2>/dev/null | tail -1
ROOT_SIZE=$(df -BM / 2>/dev/null | tail -1 | awk '{print int($2)}')
[ "$ROOT_SIZE" -ge 40000 ] && green "系统盘 ≥ 40GB" || warn "系统盘可能不足"
if mountpoint -q /mnt/data 2>/dev/null; then
    df -h /mnt/data 2>/dev/null | tail -1
    DATA_SIZE=$(df -BM /mnt/data 2>/dev/null | tail -1 | awk '{print int($2)}')
    [ "$DATA_SIZE" -ge 100000 ] && green "数据盘 ≥ 100GB" || warn "数据盘可能不足"
else
    warn "/mnt/data 未挂载（强烈建议有独立数据盘）"
fi

check "3. 系统版本"
lsb_release -d 2>/dev/null
lsb_release -d 2>/dev/null | grep -q "24.04" && green "Ubuntu 24.04" || red "不是 Ubuntu 24.04"
UNAME=$(uname -r)
echo "  Kernel: $UNAME"

check "4. 安全模块"
sudo aa-status 2>/dev/null | head -1 | grep -q "loaded" && \
  green "AppArmor 已加载" || warn "AppArmor 未加载"

check "5. 网络连通性"
curl -sI https://github.com 2>&1 | head -1 | grep -q "200\|301\|302" && \
  green "HTTPS 出站 (github.com)" || red "HTTPS 出站不通"
curl -sI http://archive.ubuntu.com 2>&1 | head -1 | grep -q "200\|301\|302" && \
  green "HTTP 出站 (archive.ubuntu.com)" || red "HTTP 出站不通"

check "6. 开放端口（基线）"
sudo ss -tlnp 2>/dev/null
echo "  此时只应有 sshd:22，多余端口先关掉"

check "7. 用户"
echo "  当前用户: $(whoami)"
id | grep -q "sudo" && green "sudo 权限正常" || red "无 sudo 权限"

check "8. 已安装依赖"
for cmd in curl wget git vim htop ffmpeg; do
    command -v $cmd >/dev/null 2>&1 && green "$cmd" || red "$cmd 未安装"
done
for cmd in ufw fail2ban-client auditctl; do
    command -v $cmd >/dev/null 2>&1 && green "$cmd" || warn "$cmd 未安装（等依赖安装阶段补）"
done

check "9. 运行时依赖"
command -v node >/dev/null 2>&1 && green "Node.js $(node -v)" || red "Node.js 未安装"
command -v docker >/dev/null 2>&1 && green "Docker $(docker --version)" || warn "Docker 未安装"
command -v caddy >/dev/null 2>&1 && green "Caddy $(caddy version | head -1)" || warn "Caddy 未安装"
command -v cloudflared >/dev/null 2>&1 && green "cloudflared $(cloudflared --version 2>/dev/null | head -1)" || warn "cloudflared 未安装"
command -v tailscale >/dev/null 2>&1 && green "Tailscale 已安装" || warn "Tailscale 未安装"
command -v code-server >/dev/null 2>&1 && \
  green "code-server $(code-server --version | head -1)" || warn "code-server 未安装"
command -v python3 >/dev/null 2>&1 && green "Python $(python3 --version)" || warn "Python3 未安装"

check "10. Docker Engine 版本（CVE 检查）"
if command -v docker >/dev/null 2>&1; then
    DOCKER_VER=$(docker version --format '{{.Server.Version}}' 2>/dev/null)
    echo "  Docker Engine: $DOCKER_VER"
    # CVE-2025-68121 修复在 29.3.0+
    echo "$DOCKER_VER" | awk -F. '{if($1>29||($1==29&&$2>=3))exit 0;else exit 1}' && \
      green "Docker 版本不受 CVE-2025-68121 影响" || \
      warn "Docker 版本受 CVE-2025-68121 影响，迁移前需手动升级: sudo apt upgrade docker-ce"
else
    warn "Docker 未安装（跳过 CVE 检查）"
fi

# === 总结 ===
echo -e "\n\033[1m==========================================\033[0m"
echo -e "\033[1m预检结果: ✅ $PASS 通过 | ❌ $FAIL 失败 | ⚠️  $WARN 警告\033[0m"

if [ "$FAIL" -gt 0 ]; then
    echo -e "\n\033[31m🔴 有 $FAIL 项未通过，修复后再进入下一层\033[0m"
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo -e "\n\033[33m🟡 全部通过，但有 $WARN 项警告（可在依赖安装阶段补上）\033[0m"
    echo "确认无误后，继续阅读: docs/plans/2026-06-15-服务器迁移方案-v3.md"
else
    echo -e "\n\033[32m🟢 全部通过！继续阅读: docs/plans/2026-06-15-服务器迁移方案-v3.md\033[0m"
fi
```

保存为 `~/preflight-check.sh`，跑一次：

```bash
bash ~/preflight-check.sh
```

---

## 六、依赖安装快捷入口

如果所有预检项通过（或只有警告），一次性装完所有依赖：

```bash
# === 一键安装脚本 ===
set -e

echo "=== 第 1 层: 系统基础 ==="
sudo apt update
sudo apt install -y curl wget git vim htop ca-certificates gnupg lsb-release \
  software-properties-common apt-transport-https build-essential pkg-config \
  libssl-dev ffmpeg python3 python3-pip python3-venv

echo "=== 第 2 层: 安全包 ==="
sudo apt install -y ufw fail2ban auditd unattended-upgrades

echo "=== 第 3 层: Node.js 22 ==="
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

echo "=== 第 4 层: Docker ==="
curl -fsSL https://get.docker.com | sudo bash
sudo usermod -aG docker jarvis
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "=== 第 5 层: Caddy ==="
sudo apt install -y debian-keyring debian-archive-keyring
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
  sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
  sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy

echo "=== 第 6 层: cloudflared ==="
curl -fsSL https://pkg.cloudflare.com/cloudflared-key.pub | \
  sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-archive-keyring.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install -y cloudflared

echo "=== 第 7 层: Tailscale ==="
curl -fsSL https://tailscale.com/install.sh | sh

echo "=== 第 8 层: code-server ==="
curl -fsSL https://code-server.dev/install.sh | sh

echo "=== 第 9 层: docker-socket-proxy 镜像预拉 ==="
docker pull tecnativa/docker-socket-proxy

echo ""
echo "=========================================="
echo "依赖全装完。验证一下版本："
echo ""
node -v && npm -v
docker --version && docker-compose --version
caddy version
cloudflared --version
code-server --version | head -1
python3 --version
echo ""
echo "如果版本都正常 → 进迁移方案 v3"
```

---

## 七、全绿后——分层推进路线图

```
📋 本手册              ← 你现在在这
│
├─ 跑 preflight-check.sh → 全绿
├─ 装所有依赖          → 全绿
│
├─ 第 1 层：系统加固    ← ufw + SSH + fail2ban + auditd + unattended-upgrades
│   (安全体系第十二章 3.1-3.6)
│
├─ 第 2 层：网络层      ← Tailscale + cloudflared 认证
│   (迁移方案步骤 4 + 11)
│
├─ 第 3 层：贾维斯核心  ← Gateway + embed-sidecar + infos-handle
│   (迁移方案步骤 2)
│
├─ 第 4 层：网关层      ← Caddy + CF Tunnel + 子域名路由
│   (迁移方案步骤 3-4)
│
├─ 第 5 层：开发环境    ← code-server + 工作区 + /srv/projects
│   (迁移方案步骤 5 + 7)
│
├─ 第 6 层：Docker 服务 ← Portainer + Nextcloud + Syncthing + 其他
│   (迁移方案步骤 6 + 8)
│   含 docker-socket-proxy（安全体系 3.7）
│
├─ 第 7 层：安全防护    ← AppArmor 确认 + trivy 镜像扫描 + Docker 安全基线
│   (安全体系 3.4 + 3.8 + 3.9)
│
├─ 第 8 层：监控接入    ← Docker 健康 + 安全事件 → broker → Control UI
│   (迁移方案步骤 13 + 安全体系 3.10)
│
├─ 第 9 层：数据备份    ← docker-volumes 每日 tar + configs Git
│   (迁移方案步骤 14)
│
├─ 第 10 层：验证       ← 安全体检 + 服务冒烟 + 全量自检
│   (迁移方案步骤 16)
│
├─ 第 11 层：割接       ← 并行运行 → 主切换 → 旧机观察
│   (迁移方案步骤 17)
│
└─ 🚀 Mark2 正式上线
```

---

## 八、故障应对速查

| 症状 | 可能原因 | 看哪 |
|------|---------|------|
| preflight DNS 不通 | 云厂商出站限制 | 提工单 |
| preflight 端口有多余监听 | 云厂商预装服务 | `sudo ss -tlnp` 关掉不明的 |
| Docker 拉镜像超时 | 国内网络 | 配 Docker 镜像加速器（阿里云/腾讯云提供） |
| Caddy 起不来 | 端口冲突（80/443 被占） | `sudo ss -tlnp | grep -E "80|443"` 关掉占用者 |
| cloudflared 登录失败 | 域名 DNS 没托管到 CF | Cloudflare Dashboard → 域名 → DNS 确认 |
| code-server 版本 <4.99.4 | install.sh 拉的不是最新 | 手动下载 deb 包安装 |
| Docker socket 权限拒绝 | jarvis 不在 docker 组 | `sudo usermod -aG docker jarvis && newgrp docker` |
| fail2ban 不封 IP | sshd filter 不匹配 | `sudo fail2ban-client status sshd` 看日志 |

---

## 九、文档索引

| 你要找 | 路径 |
|--------|------|
| 架构全景（Mark1） | `docs/贾维斯系统架构全景分析.md` |
| 服务器能力推演 | `docs/plans/2026-06-15-8核32G服务器能力推演.md` |
| 迁移方案 v3（修订版） | `docs/plans/2026-06-15-服务器迁移方案-v3.md` |
| 安全体系设计（七层） | `docs/贾维斯中枢安全体系设计.md` |
| 本手册 | `docs/贾维斯中枢-Mark2-部署启动手册.md` |
