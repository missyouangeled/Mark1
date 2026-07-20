FROM python:3.12-slim

LABEL maintainer="missyouangeled <missyouangeled@hotmail.com>"
LABEL description="Mark42 - 模块化智能铠甲系统"

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd -m -u 1000 mark42
USER mark42
WORKDIR /home/mark42

# 复制源码（context 为 mark42-pkg 自身）
COPY --chown=mark42:mark42 . ./mark42-pkg/

# 安装 mark42（含 CLI 入口 + systemd 模板）
RUN pip install --user ./mark42-pkg

# 配置目录
RUN mkdir -p .config/mark42 .local/state/openclaw/mark42

# 健康检查
HEALTHCHECK --interval=60s --timeout=10s --start-period=15s --retries=3 \
    CMD mark42 status --json >/dev/null 2>&1 || exit 1

# 默认入口
ENTRYPOINT ["mark42"]
CMD ["status"]
