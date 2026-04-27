# 🛑 ERROR_LOG.md - Persistence Error Log

## 记录准则
- 任何反复出现 3 次以上的 Bug 或未解决痛点必须记录。
- 只有在方案被验证通过并彻底解决后，才允许删除。

---

## 记录条目

### [2026-04-24] 首页板块纵向间距不生效问题
- **现象**：修改 `mt-` 类名或全量重写 `page.tsx` 后，浏览器刷新页面依然显示旧布局（板块紧挨着）。
- **触发场景**：在 `dev` 模式下频繁修改 CSS/布局类名。
- **尝试方案**：
    - 尝试局部 `edit` $\rightarrow$ 失败。
    - 尝试全量重写文件 $\rightarrow$ 失败。
    - 尝试 `Ctrl + F5` $\rightarrow$ 失败。
- **最终解决方案**：
    - 彻底杀掉所有 Node 进程 $\rightarrow$ 删除 `.next` 缓存目录 $\rightarrow$ 重新运行 `npm run dev` $\rightarrow$ 使用 `Ctrl + Shift + R` 硬刷新。
- **状态**：✅ 已解决 (需警惕 Next.js 的构建快照缓存)
