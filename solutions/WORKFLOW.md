# 📚 Solution Knowledge Base - Retrieval Workflow

## 检索逻辑 (Retrieval Protocol)
当用户询问某个具体方案或寻求特定技术实现时，执行以下流程：
1. **查索引** $\rightarrow$ 首先读取 `solutions/INDEX.md`，确认方案是否存在及路径。
2. **读文件** $\rightarrow$ 根据索引路径直接读取对应的方案详细文档。
3. **对比更新** $\rightarrow$ 若方案已过时，在文档中记录更新，并同步更新 `INDEX.md`。
4. **触发调研** $\rightarrow$ 若索引中无相关记录，则启动新的调研进程，并将结果存入库中。

## 目录映射 (Directory Map)
- `/solutions/voice/` $\rightarrow$ 语音/音频相关
- `/solutions/web/` $\rightarrow$ 网页/前端/UI 方案
- `/solutions/system/` $\rightarrow$ 系统优化/架构方案
- `/solutions/ai/` $\rightarrow$ AI/模型/Prompt 方案
- `/solutions/others/` $\rightarrow$ 其他杂项
