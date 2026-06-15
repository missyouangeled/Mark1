# 贾维斯中枢 Mark2 — 部署启动手册 v2.2

> 定位：部署的总入口。本文档是第一份要读的东西。
> 设计日期：2026-06-15
> 最后修订：2026-06-15（外部审查建议整合，v2.1→v2.2）
> 适用范围：中枢服务器（Ubuntu 24.04）

---

## 零、实际部署第一步：目标设备摸底扫描

> ⚠️ **本章是整个部署流程的真正起点。任何跳过本章的部署都是盲飞。**

正式开始部署之前，必须先对目标设备做一次完整的摸底扫描。不要假设「8核32G 就是 8核32G」——实际到手可能是虚拟化缩水的 vCPU、磁盘 IOPS 不如预期、系统预装了奇怪的服务。**先看再动。**

### 扫描目标（五项必须拿到）

| 类别 | 要搞清楚什么 | 为什么重要 |
|------|-------------|-----------|
| **设备性能** | CPU 型号/核心数/频率、内存总量/可用、磁盘容量/类型/IOPS、网卡带宽 | 决定 Docker 资源上限、服务数量、ZFS 是否可行 |
| **操作系统** | 发行版+版本号、内核版本、架构（x86_64/arm64）、已运行时间 | 决定包管理方式、内核特性可用性（如 eBPF/AppArmor） |
| **已有服务** | 哪些端口被占用、哪些服务在跑、哪些用户存在 | 避免端口冲突、清理不需要的预装服务 |
| **依赖现状** | curl/wget/git/docker 等是否已装、版本是否达标 | 决定从哪一层开始安装，省掉重复劳动 |
| **网络环境** | 出站是否通畅、DNS 是否正常、镜像拉取速度、IPv4/IPv6 | 国内云厂商差异巨大，提前知道免得后面卡住 |

### 一键摸底脚本

把以下脚本保存为 `scan-target.sh`，上传到目标设备，`bash scan-target.sh` 一次性跑完。

```bash
#!/bin/bash
# Mark2 目标设备摸底扫描脚本
# 用途：在任何部署动作之前，先搞清楚这台机器到底是什么情况

OUT="target-scan-$(date +%Y%m%d-%H%M%S).txt"
exec > >(tee "$OUT") 2>&1

echo "========================================="
echo "  Mark2 目标设备摸底扫描"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "========================================="

# ── 1. 设备性能 ──
echo ""
echo "========== 1. 设备性能 =========="
echo "--- CPU ---"
nproc
echo "CPU 型号:"
lscpu | grep "Model name" | sed 's/Model name:[[:space:]]*//'
lscpu | grep -E "^CPU\(s\)|Thread|Core|Socket|MHz"
echo "虚拟化类型:"
systemd-detect-virt 2>/dev/null || cat /sys/hypervisor/type 2>/dev/null || echo "未知"

echo ""
echo "--- 内存 ---"
free -h

echo ""
echo "--- 磁盘 ---"
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,ROTA
# ROTA=1=机械盘, ROTA=0=SSD
df -h
echo "磁盘 IOPS 粗略测试（100MB dd）:"
dd if=/dev/zero of=/tmp/mark2-scan-test bs=1M count=100 oflag=dsync 2>&1 | grep -E "copied|MB/s"
rm -f /tmp/mark2-scan-test

echo ""
echo "--- 网卡 ---"
ip -br addr 2>/dev/null || ip addr | grep -E "^[0-9]:"
echo "带宽探测（如有 speedtest-cli）:"
speedtest-cli --simple 2>/dev/null || echo "speedtest-cli 未安装，跳过"

# ── 2. 操作系统 ──
echo ""
echo "========== 2. 操作系统 =========="
echo "--- 发行版 ---"
cat /etc/os-release 2>/dev/null || cat /etc/*release 2>/dev/null | head -10
echo ""
echo "--- 内核 ---"
uname -a
echo "--- 架构 ---"
uname -m
echo "--- 已运行时间 ---"
uptime

# ── 3. 已有服务 ──
echo ""
echo "========== 3. 已有服务与端口 =========="
echo "--- 监听端口 ---"
ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null
echo ""
echo "--- 运行中的 systemd 服务（非系统级） ---"
systemctl list-units --type=service --state=running | grep -vE "systemd|dbus|polkit|cron|journal|logind|networkd|resolved|timesyncd" | head -20
echo ""
echo "--- 现有用户 ---"
awk -F: '$3>=1000 && $3<65534 {print $1, "UID="$3, "HOME="$6}' /etc/passwd

# ── 4. 依赖现状 ──
echo ""
echo "========== 4. 依赖现状 =========="
check_cmd() {
    if command -v "$1" &>/dev/null; then
        ver=$("$@" --version 2>/dev/null | head -1)
        echo "✅ $1: 已安装 → $ver"
    else
        echo "❌ $1: 未安装"
    fi
}
check_cmd curl
check_cmd wget
check_cmd git
check_cmd node
check_cmd npm
check_cmd python3
check_cmd pip3
check_cmd docker
check_cmd caddy
check_cmd cloudflared
check_cmd fail2ban-server
check_cmd ss
check_cmd nft
check_cmd ufw

# Docker 详情（如有）
if command -v docker &>/dev/null; then
    echo ""
    echo "Docker 详细信息:"
    docker version --format '{{.Server.Version}}' 2>/dev/null || echo "Docker daemon 未运行"
    docker info --format 'Docker Root: {{.DockerRootDir}}, Storage: {{.Driver}}' 2>/dev/null
fi

# ── 5. 网络环境 ──
echo ""
echo "========== 5. 网络环境 =========="
echo "--- DNS ---"
cat /etc/resolv.conf | grep -v "^#"
echo ""
echo "--- 出站连通性 ---"
for target in "google.com" "github.com" "registry-1.docker.io" "hub.docker.com"; do
    if timeout 5 curl -sI "https://$target" >/dev/null 2>&1; then
        echo "✅ $target 可达"
    else
        echo "❌ $target 不可达"
    fi
done
echo ""
echo "--- Docker 镜像拉取速度测试 ---"
timeout 30 docker pull alpine:latest 2>&1 | tail -3 || echo "Docker 未安装或拉取超时"
echo ""
echo "--- 公网 IP ---"
curl -s4 ifconfig.me 2>/dev/null && echo " (IPv4)" || echo "IPv4 获取失败"
curl -s6 ifconfig.me 2>/dev/null && echo " (IPv6)" || echo "IPv6 不可用或未配置"

# ── 6. 安全现状 ──
echo ""
echo "========== 6. 安全现状 =========="
echo "--- 防火墙 ---"
sudo ufw status 2>/dev/null || echo "ufw 未安装或未启用"
echo ""
echo "--- AppArmor ---"
sudo aa-status 2>/dev/null | head -5 || echo "AppArmor 未安装"
echo ""
echo "--- SSH 配置摘要 ---"
grep -E "^(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|AllowUsers|Port)" /etc/ssh/sshd_config 2>/dev/null || echo "sshd_config 未找到"
echo ""
echo "--- 已安装的安全更新 ---"
apt list --installed 2>/dev/null | grep -i security | head -5 || echo "无法获取"

echo ""
echo "========================================="
echo "  扫描完成。结果已保存到: $OUT"
echo "========================================="

# 生成摘要 JSON（可选，方便脚本解析）
cat > "target-scan-summary.json" << JSONEOF
{
  "scan_time": "$(date -Iseconds)",
  "hostname": "$(hostname)",
  "cpu_cores": $(nproc),
  "cpu_model": "$(lscpu | grep 'Model name' | sed 's/Model name:[[:space:]]*//')",
  "memory_total_gb": "$(free -g | awk '/^Mem/{print $2}')",
  "disk_root_gb": "$(df -BG / | awk 'NR==2{print $2}' | tr -d 'G')",
  "arch": "$(uname -m)",
  "os": "$(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)",
  "kernel": "$(uname -r)",
  "virt": "$(systemd-detect-virt 2>/dev/null || echo 'unknown')",
  "public_ipv4": "$(curl -s4 ifconfig.me 2>/dev/null || echo 'N/A')"
}
JSONEOF
echo "JSON 摘要已保存到: target-scan-summary.json"
```

### 扫描后做什么

1. **对照本手册第二节「环境预检清单」**，逐项确认扫描结果是否符合预期
2. **如有偏差**：
   - CPU/内存缩水 → 调整 Docker Compose 中的资源限制（`cpus`/`mem_limit`）
   - 磁盘是机械盘（ROTA=1）→ 放弃 ZFS，用 ext4；调整 IO 密集型服务
   - 出站不通 GitHub/Docker Hub → 先配镜像加速器，再继续
   - 端口被占用 → `sudo ss -tlnp` 查是谁，确认能否关掉
   - 已有 Docker 旧版本 → 先 `sudo apt purge` 干净再装新版
3. **确认全部满足后**，才进入下一节「前置确认」和「环境预检清单」

> 📋 扫描结果文件 `target-scan-*.txt` 和 `target-scan-summary.json` 应随部署日志一起归档到 `/mnt/data/backups/deploy-logs/`

---

## ⚠️ 部署前重要声明

**本手册是设计蓝图，不是一成不变的教条。**

正式开始项目部署时，必须以以下原则为准：

1. **以实际硬件为准**：服务器到手后先跑预检脚本，确认 CPU/内存/磁盘/带宽与预期一致；如有偏差，根据实际情况调整 Docker 资源限制和服务数量
2. **以实际网络环境为准**：国内云厂商的网络策略、镜像拉取速度、出站限制各不相同；如遇镜像拉取超时，优先配置厂商提供的镜像加速器
3. **以当时软件版本为准**：Docker/Caddy/code-server/cloudflared 等组件在部署时可能已有新版本；本手册中写死的最低版本号是**安全基线**，实际部署时应使用当时的最新稳定版
4. **持续优化**：Mark2 上线不是终点——上线后根据监控数据（资源占用、告警频率、响应延迟）持续调整资源分配、回收策略和安全规则
5. **文档随动**：部署过程中发现的任何与手册不符的情况，记录下来并同步更新本手册，确保下一次部署或回滚时有据可查

---

## 阅读顺序

```
你在这里  →  📋 本手册（预检 + 依赖）
                │
                ├─ 0. 先跑目标设备摸底扫描（零章）
                ├─ 1. 前置确认通过
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
            🧹 贾维斯中枢回收机制设计 v2.0（七层智能回收）
            docs/贾维斯中枢-Mark2-回收机制设计.md
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

**文件系统选择建议**：

| 场景 | 推荐 | 原因 |
|------|------|------|
| 单盘（当前方案） | ext4 / XFS | 最简单、最稳定、Ubuntu 原生支持 |
| 多盘 RAID | ZFS | 快照、checksum、透明压缩、去重 |
| 根分区 | ext4（默认） | Ubuntu 原生、启动快、内核内建 |

> 当前单盘云服务器保持 ext4/XFS 即可。未来如果加挂多块数据盘做 RAID，考虑 ZFS。

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
  libssl-dev ffmpeg pandoc \
  libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
```

### 第 2 层：安全包

```bash
sudo apt install -y \
  ufw fail2ban auditd \
  unattended-upgrades
```

#### 第 2-A 层：Ubuntu CIS 安全审计（可选但强烈推荐）

Ubuntu 24.04 提供官方 CIS Benchmark 硬化工具 `usg`（Ubuntu Security Guide），可自动化 200+ 项安全检查。需要 Ubuntu Pro（个人免费 5 台）。

```bash
# 安装审计工具
sudo apt install ubuntu-security-guide

# 仅审计（不自动修复，避免破坏现有配置）
sudo usg audit cis_level1_server

# 手动审查报告后逐项修复
# 注意：某些 CIS 规则可能与 self-hosted 场景冲突（如某些内核参数），
# 不要盲目 apply，逐条判断后再修
```

> 如果未启用 Ubuntu Pro，可手动参考 CIS Benchmark PDF 逐项检查。

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

#### 第 4-A 层：Diun（Docker 镜像更新通知）

> ⚠️ 2025-2026 社区共识：containrrr/watchtower 已归档停止维护。不再推荐自动更新容器。
> 替代方案：Diun（只通知不自动更新）——比 Watchtower 更安全，避免半夜自动升级把服务搞挂。

```bash
# 预拉 Diun 镜像
docker pull crazymax/diun:latest

# Diun 容器的启动在迁移方案步骤 6 中与 docker-socket-proxy 一起做
# 配置要点：
#   - 通过 docker-socket-proxy 访问 Docker API（安全）
#   - 每周日检查一次镜像更新
#   - 通知接入 Gotify/ntfy/broker → Control UI 显示「有 N 个容器可更新」
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

> ⚠️ **Caddy v2.8+ Host 头行为变更**：新版 Caddy 修改了 HTTPS 后端的默认 Host 头转发行为。
> 为确保 code-server、Portainer 等后端正确识别请求来源，在 Caddyfile 中每个反代块都需要显式声明：
> ```caddy
> code.yourdomain.com {
>     reverse_proxy localhost:8080 {
>         header_up Host {host}
>     }
> }
> ```
> 详细配置见迁移方案步骤 4 的 Caddyfile。

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

### 第 11 层：Python 文档库（Web→PDF / Word / Excel / PPT）

```bash
# 文档生成三件套 + PDF 三件套 + 文档读取
pip3 install --break-system-packages \
  python-docx openpyxl pandas python-pptx \
  weasyprint reportlab pikepdf pdfplumber \
  "markitdown[pptx]"
```

### 第 12 层：.NET SDK 8.0（minimax-docx 专业文档 skill）

```bash
# 来自 Microsoft 官方仓库
wget https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb
sudo dpkg -i /tmp/packages-microsoft-prod.deb
sudo apt update
sudo apt install -y dotnet-sdk-8.0

dotnet --version
# 预期: 8.0.x
```

### 第 13 层：pptxgenjs（PPT 生成 skill）

```bash
# Node.js 22 已装，直接全局安装
sudo npm install -g pptxgenjs
```

### 第 14 层：LibreOffice headless（格式转换桥，按需装）

```bash
# ≈500MB，按需装。不装也能用 WeasyPrint + Pandoc 覆盖 90% 场景
sudo apt install -y libreoffice-impress libreoffice-calc

# 验证
soffice --headless --version
```

---

## 四、依赖安装总结表

| 序号 | 组件 | 安装方式 | 用途 | 启动时机 |
|------|------|---------|------|---------|
| 1 | 系统基础 | apt | curl/wget/git/vim/build-essential/ffmpeg/pandoc/weasyprint-devs | 立即 |
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
| 13 | Python 3 + pip3 | apt | TTS 推理 + 文档库 | 安装完 |
| 14 | docker-socket-proxy | Docker pull | Docker API 权限隔离 | 迁移方案步骤 6 |
| 15 | Diun | Docker pull | Docker 镜像更新通知（替代已归档的 Watchtower） | 迁移方案步骤 6 |
| 16 | Python 文档库 | pip3 | Word/Excel/PPT/PDF 生成与读取（含 pdfplumber/markitdown） | 安装完 |
| 17 | .NET SDK 8.0 | apt (MS repo) | minimax-docx 专业文档 | 需要时 |
| 18 | pptxgenjs | npm -g | PPT 生成 skill | 需要时 |
| 19 | LibreOffice headless | apt | 格式转换桥（≈500MB） | 按需装 |

**注意**：1-14 层属于「预检阶段」就要装好的——系统基础 + 安全 + 容器运行时。15-19 层可按需补装（Python 文档库 + Diun 建议预装，很小）。

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
for cmd in curl wget git vim htop ffmpeg pandoc; do
    command -v $cmd >/dev/null 2>&1 && green "$cmd" || red "$cmd 未安装"
done
for cmd in ufw fail2ban-client auditctl; do
    command -v $cmd >/dev/null 2>&1 && green "$cmd" || warn "$cmd 未安装（等依赖安装阶段补）"
done

check "8b. WeasyPrint 系统库"
for lib in libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0; do
    dpkg -l "$lib" 2>/dev/null | grep -q "^ii" && green "$lib" || warn "$lib 未安装"
done

check "8c. 容器非 root 运行检查"
if command -v docker >/dev/null 2>&1; then
    ROOT_CONTAINERS=$(docker ps -q 2>/dev/null | xargs docker inspect --format '{{.Name}}: User={{.Config.User}}' 2>/dev/null | grep -E 'User=$|User=root|User=0' || true)
    if [ -z "$ROOT_CONTAINERS" ]; then
        green "所有容器指定了非 root 用户"
    else
        warn "以下容器以 root 运行: $ROOT_CONTAINERS"
    fi
else
    warn "Docker 未安装（跳过容器安全检查）"
fi

check "9. 运行时依赖"
command -v node >/dev/null 2>&1 && green "Node.js $(node -v)" || red "Node.js 未安装"
command -v docker >/dev/null 2>&1 && green "Docker $(docker --version)" || warn "Docker 未安装"
command -v caddy >/dev/null 2>&1 && green "Caddy $(caddy version | head -1)" || warn "Caddy 未安装"
command -v cloudflared >/dev/null 2>&1 && green "cloudflared $(cloudflared --version 2>/dev/null | head -1)" || warn "cloudflared 未安装"
command -v tailscale >/dev/null 2>&1 && green "Tailscale 已安装" || warn "Tailscale 未安装"
command -v code-server >/dev/null 2>&1 && \
  green "code-server $(code-server --version | head -1)" || warn "code-server 未安装"
command -v python3 >/dev/null 2>&1 && green "Python $(python3 --version)" || warn "Python3 未安装"

check "9b. 文档处理依赖"
command -v dotnet >/dev/null 2>&1 && green "dotnet $(dotnet --version 2>/dev/null)" || warn ".NET SDK 未安装（minimax-docx skill 需要时补）"
command -v npx >/dev/null 2>&1 && npx pptxgenjs --version 2>/dev/null && green "pptxgenjs" || warn "pptxgenjs 未安装（按需补）"
python3 -c "import weasyprint" 2>/dev/null && green "weasyprint" || warn "weasyprint 未安装"
python3 -c "import openpyxl" 2>/dev/null && green "openpyxl" || warn "openpyxl 未安装"
python3 -c "import docx" 2>/dev/null && green "python-docx" || warn "python-docx 未安装"
command -v soffice >/dev/null 2>&1 && green "LibreOffice headless" || warn "LibreOffice 未安装（按需补，≈500MB）"

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
  libssl-dev ffmpeg pandoc python3 python3-pip python3-venv \
  libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0

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

echo "=== 第 10 层: docker-socket-proxy 镜像预拉 ==="
docker pull tecnativa/docker-socket-proxy

echo "=== 第 10-A 层: Diun 镜像预拉（替代已归档的 Watchtower） ==="
docker pull crazymax/diun:latest

echo "=== 第 11 层: Python 文档库 ==="
pip3 install --break-system-packages \
  python-docx openpyxl pandas python-pptx \
  weasyprint reportlab pikepdf pdfplumber \
  "markitdown[pptx]"

echo "=== 第 12 层: .NET SDK 8.0（minimax-docx） ==="
wget https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb \
  -O /tmp/packages-microsoft-prod.deb
sudo dpkg -i /tmp/packages-microsoft-prod.deb
sudo apt update
sudo apt install -y dotnet-sdk-8.0

echo "=== 第 13 层: pptxgenjs（PPT 生成） ==="
sudo npm install -g pptxgenjs

echo "=== 第 14 层: LibreOffice headless（格式转换，≈500MB，按需） ==="
sudo apt install -y libreoffice-impress libreoffice-calc

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
dotnet --version 2>/dev/null || echo "dotnet 未装（如需后补）"
pandoc --version | head -1
soffice --headless --version 2>/dev/null || echo "LibreOffice 未装（按需补）"
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
├─ 第 5 层：开发工作台  ← code-server + 插件 + 文档处理依赖 + 产出物目录 + 远程驱动 + 外部预览
│   (独立设计: docs/贾维斯中枢-Mark2-开发工作台设计.md v2.2)
│   产出物目录: /srv/projects/{docs,image}/outputs/ + /mnt/data/video-outputs/
│   模板目录: /srv/templates/
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
├─ 第 11 层：回收机制    ← 预防层配置 + 强制回收 + 七层智能回收脚本部署
│   (回收机制设计 v2.0 八：部署位置)
│   含开发工作台产出物保留 (L3-A): 图片500MB/视频2GB/文档200MB + 7天TTL
│
├─ 第 12 层：割接       ← 并行运行 → 主切换 → 旧机观察
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
| 容器更新后服务挂了 | 自动更新未加防护 | Diun 只通知不更新（本手册第4-A层）——手动确认后再更新 |

---

## 九、Tailscale + Cloudflare Tunnel 分工对照

两种通道**互补而非竞争**，部署后按以下规则使用：

| 场景 | 走哪条 | 原因 |
|------|--------|------|
| 公网访问 Control UI / WebChat | CF Tunnel (`jarvis.xxx.com`) | 自动 SSL + CF Access 保护 |
| 公网访问 code-server / Portainer | CF Tunnel (`code.xxx.com`) | CF Access 做 SSO 认证层 |
| 公网访问 Nextcloud / Lsky Pro | CF Tunnel (`drive.xxx.com`) | CF WAF + 速率限制 |
| SSH 远程管理服务器 | **Tailscale** (`100.x.x.x`) | 低延迟、密钥认证、不暴露公网 |
| 数据库直连（调试时） | **Tailscale** | 不走公网、不经过反代 |
| Syncthing 设备配对 | **Tailscale** | 比 CF Tunnel 更快更安全 |
| 文件传输（scp/rsync） | **Tailscale** | 大文件直传不走 CF 带宽 |
| Docker 管理 API | **Tailscale** | Portainer 通过 Caddy 走公网也行，但管理操作走私网更安全 |

> **原则**：Web 服务走 CF Tunnel（用户友好），管理操作走 Tailscale（安全私密）。
> 不要用 Tailscale IP 裸端口访问 Web 服务——统一入口，避免「A 路径能用 B 路径不行」的诡异问题。

## 十、自部署服务选型备注

### Immich（图片/视频管理）

> 2025 社区共识：Immich 已成为自托管照片管理的绝对主流（Google Photos 替代第一名）。
> Nextcloud Photos/Memories 体验差距明显。

**建议**：
- 如果手机照片/视频备份是刚需 → 部署 **Immich**（AI 人脸识别、对象检测、地图视图、移动端 App）
- 如果只是文档同步 + 偶尔看图 → Nextcloud 足够
- 两者可以共存，Immich 内存占用约 800MB（含 ML），8核32G 完全无压力

```bash
# Immich 快速安装（详见 https://immich.app/docs/install/docker-compose）
# 通过 Docker Compose 部署，与现有服务无冲突
# 数据目录: /mnt/data/docker-volumes/immich/
```

### Syncthing 配对建议

首次设备配对**通过 Tailscale IP 进行**（不走 CF Tunnel，比公网更快更安全）：

```bash
# 1. 确认两台设备都在 Tailscale 网络中
# 2. 在服务器端获取设备 ID
syncthing --device-id
# 3. 在客户端添加远程设备时使用 Tailscale IP（如 100.x.x.x），而非公网域名
```

## 十一、镜像安全建议

### 锁定镜像 Digest

所有 `docker-compose.yml` 中的镜像应固定 digest 而非使用 `:latest` 标签：

```yaml
# ❌ 不推荐（每次 pull 可能拉不同版本）
image: portainer/portainer-ce:latest

# ✅ 推荐（锁定精确版本）
image: portainer/portainer-ce:2.27.1@sha256:abc123...
```

获取 digest：
```bash
docker pull portainer/portainer-ce:2.27.1
docker inspect portainer/portainer-ce:2.27.1 --format '{{.RepoDigests}}'
```

> 定期用 trivy 扫描（安全体系 L7）确保锁定版本无已知漏洞，配合 Diun 通知有新版本可用时手动升级。

---

## 十二、文档索引

| 你要找 | 路径 |
|--------|------|
| 架构全景（Mark1） | `docs/贾维斯系统架构全景分析.md` |
| 服务器能力推演 | `docs/plans/2026-06-15-8核32G服务器能力推演.md` |
| 🛡️ 安全体系设计（独立成册） | `docs/贾维斯中枢安全体系设计.md` |
| 🧹 回收机制设计 v2.0（独立成册） | `docs/贾维斯中枢-Mark2-回收机制设计.md` |
| 🖥️ 开发工作台设计 v2.2（独立成册） | `docs/贾维斯中枢-Mark2-开发工作台设计.md` |
| 迁移方案 v3（部署指引） | `docs/plans/2026-06-15-服务器迁移方案-v3.md` |
| 📋 外部审查建议（本次修订依据） | `docs/plans/2026-06-15-Mark2外部审查建议.md` |
| 本手册（部署启动 v2.2） | `docs/贾维斯中枢-Mark2-部署启动手册.md` |
