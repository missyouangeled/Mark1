# PLANS.md — 方案存档

各类方案、调研结论、技术决策的归档。每次有新方案，先写到这里，再在 MEMORY.md 挂索引。

---

## 2026-04-29：云服务器部署方案

### 用途
让 OpenClaw（贾维斯）24小时在线，随时可访问。

### 推荐服务商对比

| 服务商 | 推荐配置 | 新用户最低价 | 续费参考价 | 特点 |
|--------|---------|------------|-----------|------|
| **腾讯云** | 轻量 2核2G 3M/40G | **68元/年**（1.4折） | ≈99元/年 | 微信登录方便，活动多 |
| **腾讯云** | 轻量 2核2G 4M/50G | **99元/年**（续费同价） | 99元/年 | **推荐：新老用户同价，续费不涨价** |
| **阿里云** | ECS 2核2G 3M/40G | **99元/年** | 99元/年 | 新老用户都能买，续费不涨价 |
| **阿里云** | 轻量 2核2G 3M/50G | **61元/年** | ≈99元/年 | 新用户轻量版 |
| **腾讯云** | 秒杀 4核4G 3M/40G | **38元/年**（0.5折） | 约99-188元/年 | 新用户限一台，配置翻倍 |

> ⚠️ 以上价格来自2026年4月腾讯云、阿里云官方活动页面。实际价格以购买时为准。

### 推荐方案（按情况）

**如果你是腾讯云新用户：**
→ 先抢 4核4G 38元/年 秒杀（0.5折），配置翻倍，一年才38块。
→ 或者直接选 2核2G 68元/年，如果觉得4核用不上。

**如果你不是新用户（阿里云/腾讯云都行）：**
→ 选 **99元/年 续费同价** 的套餐，两家的差别不大。
→ 阿里云：ECS 2核2G 3M/40G，99元/年，续费不涨。
→ 腾讯云：轻量 2核2G 4M/50G，99元/年，续费同价。

### 配置建议
- **CPU**：2核足够（OpenClaw不重，模型调远程API）
- **内存**：2GB（已够用，4核4G的秒杀套餐更富余）
- **系统盘**：40-60GB SSD
- **带宽**：3-4Mbps（够用了）
- **流量**：300-500G/月（日常聊天用不完）
- **系统**：Ubuntu 22.04 / 24.04
- **不需要 GPU**：所有模型调远程 API，不需要显卡

### 部署步骤
```bash
# 1. 服务器上装 Node.js
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt install -y nodejs

# 2. 安装 OpenClaw
npm install -g openclaw

# 3. 创建配置目录
mkdir -p ~/.openclaw

# 4. 从旧机器传导出包过来（scp / U盘 / 任何安全方式）
scp openclaw-setup-export-20260429.tar.gz 服务器IP:~/

# 5. 解压还原
tar xzf openclaw-setup-export-*.tar.gz -C ~/
cp config/openclaw.json ~/.openclaw/
cp -r credentials/* ~/.openclaw/credentials/

# 6. 克隆 workspace
git clone git@github.com:missyouangeled/test-git.git ~/.openclaw/workspace

# 7. 启动并设置开机自启
openclaw gateway start
openclaw gateway enable  # 开机自启
```

### 访问方式
- **WebChat**：浏览器打开 `http://服务器IP:18789`
- **微信通道**：配置好微信后，手机微信直接聊
- **手机浏览器**：和电脑一样

### 每月成本
- 新用户第一年：**最低38元（腾讯云秒杀）或61-68元**
- 平均年成本：**99元/年 ≈ 8元/月**
- 日常耗电：**0元（云服务器电费包含在套餐内）**

### 迁移保障
换机器后 workspace 从 GitHub 同步，我用 AGENTS.md → MEMORY.md → PLANS.md 的链路找回所有方案和记忆。

---

## 2026-04-29：ROG 掌机（Windows）部署方案

### 用途
在 ROG 掌机的 Windows 系统上运行 OpenClaw，通过手机热点联网，实现随身携带、随时在线。

### 方案选择

| 方案 | 说明 | 推荐度 |
|------|------|:----:|
| **方案A：原生 Windows+PowerShell** | 直接 Windows 上装，简单轻量 | ⭐ 推荐 |
| **方案B：WSL2 子系统** | 开 Linux 虚拟机跑，更稳定但耗电 | 可选 |

> 对于 ROG 掌机，建议走方案A（原生），不需要额外开虚拟机拖累续航。

### 方案A：原生 Windows 部署步骤

#### 第一步：安装 Node.js
1. 打开浏览器，访问 https://nodejs.org
2. 下载 **Node.js 22.x LTS**（Windows .msi 安装包）
3. 双击安装，一路下一步（全部默认勾选即可）
4. 安装完成后，打开 **PowerShell**（右键开始菜单 → Windows PowerShell）
5. 验证安装：
```powershell
node --version   # 应该显示 v22.x.x
npm --version    # 应该显示 10.x.x
```

#### 第二步：安装 OpenClaw
```powershell
npm install -g openclaw@latest
```

#### 第三步：同步 workspace 和配置
先配好 GitHub SSH 密钥：
```powershell
# 1. 检查是否有 SSH 密钥
ls ~\.ssh\id_ed25519*

# 2. 如果没有，生成一个
ssh-keygen -t ed25519 -C "你的GitHub邮箱"

# 3. 查看公钥，添加到 GitHub
cat ~\.ssh\id_ed25519.pub
# → 复制输出，去 GitHub → Settings → SSH and GPG keys → New SSH key
```

然后克隆 workspace：
```powershell
# 克隆记忆库
git clone git@github.com:missyouangeled/test-git.git %USERPROFILE%\.openclaw\workspace
```

#### 第四步：恢复配置
从旧机器通过 `scripts/export-setup.sh` 导出 tar.gz，传到 ROG 掌机解压：
```powershell
# 将 openclaw-setup-export-20260429.tar.gz 放到 C:\ 下
# 在 PowerShell 中：
cd $env:USERPROFILE\.openclaw
# 解压（Windows 可以用 7-Zip 或 tar 命令）
tar -xzf C:\openclaw-setup-export-20260429.tar.gz
# 然后复制配置和凭据
Copy-Item config\openclaw.json .\
Copy-Item credentials\* .\credentials\ -Recurse
```

#### 第五步：启动
```powershell
openclaw gateway start
```

#### 第六步：设置开机自启
1. 创建一个 `.bat` 或 `.ps1` 脚本，内容：
```powershell
start /B openclaw gateway start
```
2. 按 `Win + R`，输入 `shell:startup`
3. 把脚本放进启动文件夹

### 手机热点联网方案

**问题**：手机热点的 IP 是动态的，且 ROG 掌机在手机内网下。

**方案一（推荐）：Tailscale（免费）**
1. 在 ROG 掌机装 Tailscale：https://tailscale.com/download
2. 在手机也装 Tailscale
3. 两台设备登录同一个账号 → 组成虚拟局域网
4. ROG 掌机的 Tailscale IP 固定，手机通过那个 IP:18789 访问

**方案二（简单）：局域网直连**
- 手机开热点，ROG 掌机连上
- 在 ROG 掌机上运行 `ipconfig` 查看 IP
- 其他设备（或你自己）通过 `http://ROG-IP:18789` 访问
- 但手机热点断开后 IP 会变

**方案三（稍复杂）：内网穿透（frp/ngrok）**
- 适合需要在外网长期稳定访问的场景
- 需要一个有公网IP的服务器做跳板

### 续航建议
- ROG 掌机插电时跑 OpenClaw 最合适
- 电池模式下 OpenClaw 本身负载低，几乎不影响续航
- 需要长时间外出时，可以用手机远程连接

### 和云服务器方案的对比
| | ROG 掌机方案 | 云服务器方案 |
|------|------------|------------|
| 成本 | 0元（已有硬件） | 约99元/年 |
| 续航 | 需插电或省电模式 | 24小时在线 |
| 便携 | 随身带 | 固定节点 |
| 网络 | 依赖手机热点 | 固定公网IP |
| 部署门槛 | 需 Windows 操作 | 需 Linux 基础 |
