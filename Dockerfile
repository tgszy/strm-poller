# 使用Python 3.11 Alpine作为基础镜像
FROM python:3.11-alpine

# 设置pip镜像源为官方源（避免国内镜像源不稳定问题）
# RUN pip config set global.index-url https://pypi.org/simple/

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
    libxml2-dev \
    libxslt-dev \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    tk-dev \
    tcl-dev \
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

# 确保静态文件目录存在并复制所有静态文件
RUN mkdir -p /app/src/static/js
COPY src/static/ ./src/static/
COPY src/static/js/ ./src/static/js/

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /config && \
    chown -R appuser:appuser /app /config

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 35455

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:35455/api/health || exit 1

# 启动命令
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "35455", "--log-level", "info"]