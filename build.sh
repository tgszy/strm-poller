#!/bin/sh
# Docker构建脚本，支持多架构构建

set -e

# 镜像名称和标签
IMAGE_NAME="ghcr.io/yourname/strm-poller"
VERSION="${1:-latest}"
PLATFORMS="linux/amd64,linux/arm64"

# 检查是否安装了buildx
if ! docker buildx version > /dev/null 2>&1; then
    echo "错误: 需要安装Docker Buildx才能进行多架构构建"
    echo "请参考: https://docs.docker.com/buildx/working-with-buildx/"
    exit 1
fi

# 创建或使用现有的buildx构建器
BUILDER_NAME="strm-poller-builder"
if ! docker buildx ls | grep -q "$BUILDER_NAME"; then
    echo "创建新的buildx构建器: $BUILDER_NAME"
    docker buildx create --name "$BUILDER_NAME" --use
else
    echo "使用现有的buildx构建器: $BUILDER_NAME"
    docker buildx use "$BUILDER_NAME"
fi

# 启动构建器
echo "启动buildx构建器..."
docker buildx inspect --bootstrap

# 构建多架构镜像
echo "开始构建多架构镜像..."
docker buildx build \
    --platform "$PLATFORMS" \
    --tag "$IMAGE_NAME:$VERSION" \
    --tag "$IMAGE_NAME:latest" \
    --push \
    --file Dockerfile \
    .

echo "构建完成！镜像已推送到: $IMAGE_NAME:$VERSION"
echo "支持的架构: $PLATFORMS"

# 清理构建器（可选）
# docker buildx rm "$BUILDER_NAME"