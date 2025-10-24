#!/bin/sh
# Docker构建脚本，针对amd64架构

set -e

# 镜像名称和标签
IMAGE_NAME="ghcr.io/tgszy/strm-poller"
VERSION="${1:-latest}"
PLATFORMS="linux/amd64"

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
echo "🔨 开始构建多架构镜像..."
# 添加重试逻辑，最多重试3次
RETRY_COUNT=0
MAX_RETRIES=3
BUILD_SUCCESS=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$BUILD_SUCCESS" = false ]; do
    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "尝试构建第 $RETRY_COUNT/$MAX_RETRIES 次..."
    
    if docker buildx build \
        --platform "$PLATFORMS" \
        --tag "$IMAGE_NAME:$VERSION" \
        --tag "$IMAGE_NAME:latest" \
        --push \
        --file Dockerfile \
        .; then
        BUILD_SUCCESS=true
        echo "✅ 构建成功！"
    else
        echo "❌ 构建失败，${RETRY_COUNT}秒后重试..."
        sleep $RETRY_COUNT
    fi
done

if [ "$BUILD_SUCCESS" = false ]; then
    echo "❌ 构建失败，已达到最大重试次数"
    exit 1
fi

echo "构建完成！镜像已推送到: $IMAGE_NAME:$VERSION"
echo "支持的架构: $PLATFORMS"

# 清理构建器（可选）
# docker buildx rm "$BUILDER_NAME"