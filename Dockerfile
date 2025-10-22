# 使用Python 3.11 Alpine作为基础镜像
FROM python:3.11-alpine

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PUID=1000
ENV PGID=1000
ENV TZ=Asia/Shanghai

# 安装系统依赖
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    sqlite-dev \
    curl \
    && rm -rf /var/cache/apk/*

# 创建非root用户
RUN addgroup -g 1000 -S appuser && \
    adduser -u 1000 -S appuser -G appuser

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY src/ ./src/
COPY src/static/ ./static/

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /app/config && \
    chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 3456

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3456/api/health || exit 1

# 启动命令
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "3456", "--log-level", "info"]