# 视频平台下载 操作规则

> 按需加载：当用户要求从抖音/其他平台搜索/下载视频时读取。
> 触发条件：用户说"去抖音下载XX" / "搜一下XX视频" / 分享视频链接

## 默认工作流

1. 判断任务类型：搜索型 vs 已有链接
2. 有链接 → 直接走 `scripts/download-platform-video.py`
3. 只有关键词/作者名：
   - 先试平台内直达
   - 被验证码/登录墙拦住 → 立刻切外部搜索
4. 多候选 URL → 用 `--pick` 代替写死第一条
5. 作者主页异常 → 报阻塞，不误选推荐视频

## 下载校验

- 下载前：容量预检
- 下载后：文件存在 + `ffprobe` 校验

## 已知事实

- 抖音站内搜索可能直接进验证码
- 作者主页可能返回"服务异常"
- `scripts/download-platform-video.py` 支持：
  - 公开视频页 URL
  - 多候选 + `--pick`
  - `--list-only` 候选整理
  - `--candidates-out` / `--report-out`
  - 输出 `next_download_command` / `replay_download_command`

## 候选整理模板

```bash
python3 scripts/download-platform-video.py --list-only --pick=first \
  --candidates-out tmp/video-downloads/candidates.txt \
  --report-out tmp/video-downloads/candidates.json '搜索片段/混合文本'
```
随后用输出里的 `next_download_command` 继续。
