#!/bin/sh
# 简化版Docker Hub构建脚本（单架构）

set -e

# Docker Hub 镜像名称
DOCKERHUB_IMAGE="tgszy/strm-poller"
VERSION="${1:-latest}"

echo "🚀 开始构建Docker镜像..."

# 检查Docker是否可用
if ! docker version > /dev/null 2>&1; then
    echo "❌ 错误: Docker未安装或未运行"
    exit 1
fi

# 登录Docker Hub（如果未登录）
echo "🔐 检查Docker Hub登录状态..."
if ! docker info | grep -q "Username:"; then
    echo "请登录Docker Hub:"
    docker login
fi

# 构建镜像
echo "🔨 开始构建镜像..."
docker build -t "$DOCKERHUB_IMAGE:$VERSION" -t "$DOCKERHUB_IMAGE:latest" .

# 推送到Docker Hub
echo "📤 推送到Docker Hub..."
docker push "$DOCKERHUB_IMAGE:$VERSION"
docker push "$DOCKERHUB_IMAGE:latest"

echo "✅ 构建和推送完成！"
echo "🔗 Docker Hub链接: https://hub.docker.com/r/$DOCKERHUB_IMAGE"
echo "🎉 镜像已成功推送到Docker Hub！"