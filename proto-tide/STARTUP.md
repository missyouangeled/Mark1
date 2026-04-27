# Project Startup Manifest - PulseNest (proto-tide)

## 🚀 快速启动命令
```bash
cd /home/missyouangeled/.openclaw/workspace/proto-tide
npm run dev
```

## 📦 环境依赖
- **Node.js**: v18+ (Next.js 15)
- **端口**: 3000 (必须确保无占用)
- **配置文件**: `.env` (若存在，需检查 API Keys)

## ⚠️ 避坑指南 (Critical Warnings)
- **端口占用**：如果启动失败，请执行 `pkill -f node` 彻底清除所有残留进程。
- **缓存陷阱**：若修改代码后页面无变化，请尝试删除 `.next` 目录并重启服务。
- **硬刷新**：前端观察效果时，务必使用 `Ctrl + Shift + R` (硬刷新) 以绕过浏览器缓存。

## ✅ 状态验证
- **URL**: `http://localhost:3000`
- **验证点**: 首页应显示 "PulseNest" 标题且返回 200 OK。
- **验证命令**: `curl -s http://localhost:3000 | grep "PulseNest"`
