## IPTV 自动推流方案（iptv-org/iptv）

- **日期**：2026-06-18 调研
- **状态**：`方案已定，待实施`
- **标签**：`IPTV`, `视频推流`, `HLS`, `ffmpeg`, `服务器`
- **仓库**：https://github.com/iptv-org/iptv（80K+ Star，全球公开频道 M3U 列表）

### 需求

用户对 AI 助手说"放 CCTV-5"，助手自动从 iptv-org 列表中匹配频道 → ffmpeg 拉流转 HLS → 推送到用户指定观看地址。

### 技术链路

```
用户指令 → 搜索 iptv-org M3U 中对应频道
         → ffmpeg 拉 RTMP/HLS/MPEG-TS 源流
         → 转码 HLS（.m3u8 + .ts 切片）
         → Nginx 静态托管
         → 用户浏览器打开 http://服务器:端口/live/频道名.m3u8
```

### 可自动化的部分
- 解析 M3U 播放列表，匹配频道名
- ffmpeg 拉流 + 转 HLS
- Nginx 配置自动生成
- 用户指令 → 脚本调度（Mark42 engine 触发）

### 有门槛的部分

| 问题 | 说明 |
|:---|:---|
| **转码性能** | 1080p 源流 CPU 转 HLS 约 1-2 核，GPU 转码（NVENC/QSV）才不卡 |
| **带宽** | 单路 1080p HLS 3-8 Mbps，服务器上行需达标 |
| **延迟** | 拉流→转码→切片→推送，最少 5-15 秒 |
| **源流不稳** | iptv-org 免费源可能不定期失效，需定期检测切换 |

### 核心依赖

- `ffmpeg`（已有）
- `nginx`（需安装，HLS 静态托管）
- `iptv-org/iptv` M3U 播放列表
- 可选：`iptv-org/epg`（电子节目单）

### 实施触发

当服务器部署就绪后，执行：
1. 拉取 iptv-org 最新播放列表
2. 装 nginx + HLS 模块
3. 写频道搜索脚本（M3U 解析 + 模糊匹配）
4. 写 ffmpeg 拉流转 HLS 脚本
5. 集成到 Mark42 engine 作为 Loop 模板

---
