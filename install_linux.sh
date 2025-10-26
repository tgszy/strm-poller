#!/bin/bash

echo "========================================"
echo "STRM Poller Linux/macOS 一键安装脚本"
echo "========================================"
echo

# 检查Docker是否已安装
echo "[1/6] 检查Docker环境..."
if ! command -v docker &> /dev/null; then
    echo "错误: 未检测到Docker，请先安装Docker"
    echo "安装方法参考: https://docs.docker.com/engine/install/"
    exit 1
fi

echo "Docker已安装，版本: $(docker --version)"

# 检查Docker服务是否运行
echo "[2/6] 检查Docker服务状态..."
if ! docker ps &> /dev/null; then
    echo "错误: Docker服务未运行，请启动Docker服务"
    echo "启动命令: sudo systemctl start docker"
    exit 1
fi

echo "Docker服务运行正常"

# 创建默认目录结构
echo "[3/6] 创建默认目录结构..."
CONFIG_DIR="$HOME/strm-poller"
if [ ! -d "$CONFIG_DIR" ]; then
    mkdir -p "$CONFIG_DIR/config"
    mkdir -p "$CONFIG_DIR/source"
    mkdir -p "$CONFIG_DIR/target"
    echo "目录创建完成:"
    echo "  - 配置目录: $CONFIG_DIR/config"
    echo "  - 源文件目录: $CONFIG_DIR/source"
    echo "  - 目标目录: $CONFIG_DIR/target"
else
    echo "使用现有目录: $CONFIG_DIR"
fi

# 检查是否已有运行的容器
echo "[4/6] 检查现有容器..."
if docker ps -a --format "table {{.Names}}" | grep -q "strm-poller"; then
    echo "发现已存在的strm-poller容器，正在停止并删除..."
    docker stop strm-poller 2>/dev/null
    docker rm strm-poller 2>/dev/null
    echo "旧容器已清理"
fi

# 拉取最新镜像并运行
echo "[5/6] 拉取最新镜像并启动容器..."
echo "正在拉取最新镜像..."
docker pull ghcr.io/tgszy/strm-poller:latest

echo "启动STRM Poller容器..."
docker run -d \
  --name=strm-poller \
  -p 35455:35455 \
  -v "$CONFIG_DIR/config:/config" \
  -v "$CONFIG_DIR/source:/src:ro" \
  -v "$CONFIG_DIR/target:/dst" \
  -e PUID=$(id -u) \
  -e PGID=$(id -g) \
  -e TZ=Asia/Shanghai \
  -e MAX_MEMORY=1024 \
  --memory=1g \
  --memory-swap=1g \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest

if [ $? -ne 0 ]; then
    echo "错误: 容器启动失败"
    exit 1
fi

echo "[6/6] 等待服务启动..."
sleep 10

# 检查容器状态
echo "检查容器运行状态..."
docker ps --filter "name=strm-poller" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo
echo "========================================"
echo "安装完成！"
echo "========================================"
echo
echo "访问地址: http://localhost:35455"
echo
echo "重要说明:"
echo "1. 首次访问会自动打开设置向导"
echo "2. 源文件请放置在: $CONFIG_DIR/source"
echo "3. 整理后的文件将输出到: $CONFIG_DIR/target"
echo "4. 配置文件和日志在: $CONFIG_DIR/config"
echo
echo "如需停止服务，运行: docker stop strm-poller"
echo "如需启动服务，运行: docker start strm-poller"
echo
echo "安装脚本执行完成！"