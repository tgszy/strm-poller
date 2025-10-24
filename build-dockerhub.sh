#!/bin/sh
# Docker Hub 构建和推送脚本

set -e

# Docker Hub 镜像名称
DOCKERHUB_IMAGE="tgszy/strm-poller"
VERSION="${1:-latest}"
PLATFORMS="linux/amd64"

echo "🚀 开始构建 Docker Hub 镜像..."

# 检查是否安装了buildx
if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ 错误: 需要安装Docker Buildx才能进行多架构构建"
    echo "请参考: https://docs.docker.com/buildx/working-with-buildx/"
    exit 1
fi

# 登录Docker Hub（如果未登录）
echo "🔐 检查Docker Hub登录状态..."
if ! docker info | grep -q "Username:"; then
    echo "请登录Docker Hub:"
    docker login
fi

# 创建或使用现有的buildx构建器
BUILDER_NAME="strm-poller-dockerhub"
if ! docker buildx ls | grep -q "$BUILDER_NAME"; then
    echo "🏗️  创建新的buildx构建器: $BUILDER_NAME"
    docker buildx create --name "$BUILDER_NAME" --use
else
    echo "🔧 使用现有的buildx构建器: $BUILDER_NAME"
    docker buildx use "$BUILDER_NAME"
fi

# 启动构建器
echo "🚀 启动buildx构建器..."
docker buildx inspect --bootstrap

# 构建多架构镜像并推送到Docker Hub
echo "🔨 开始构建多架构镜像..."
docker buildx build \
    --platform "$PLATFORMS" \
    --tag "$DOCKERHUB_IMAGE:$VERSION" \
    --tag "$DOCKERHUB_IMAGE:latest" \
    --push \
    --file Dockerfile \
    .

echo "✅ 构建完成！镜像已推送到Docker Hub: $DOCKERHUB_IMAGE:$VERSION"
echo "📦 支持的架构: $PLATFORMS"
echo "🔗 Docker Hub链接: https://hub.docker.com/r/$DOCKERHUB_IMAGE"

# 显示构建结果
echo "📋 构建结果:"
docker buildx imagetools inspect "$DOCKERHUB_IMAGE:$VERSION"

# 清理构建器（可选）
# docker buildx rm "$BUILDER_NAME"

echo "🎉 Docker Hub推送完成！"