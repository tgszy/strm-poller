# Docker Hub 使用指南

本指南介绍如何将 STRM Poller 镜像推送到 Docker Hub 并使用。

## 🚀 快速开始

### 1. 构建并推送镜像

使用提供的构建脚本进行amd64架构构建：
```bash
# 给脚本执行权限
chmod +x build-dockerhub.sh

# 运行amd64架构构建
./build-dockerhub.sh

# 或者指定版本
./build-dockerhub.sh v1.0.0
```

### 2. 使用 Docker Hub 镜像

#### 使用 Docker Compose（推荐）
```bash
# 使用标准的 docker-compose 文件
docker-compose up -d
```

#### 使用 Docker 命令
```bash
# 拉取并运行镜像
docker pull tgszy/strm-poller:latest

docker run -d \
  --name strm-poller \
  -p 8080:8080 \
  -v ./media:/media \
  -v ./config:/app/config \
  -v ./logs:/app/logs \
  -e LOG_LEVEL=INFO \
  -e PROXY_ENABLED=true \
  -e MEMORY_LIMIT_MB=1024 \
  --restart unless-stopped \
  tgszy/strm-poller:latest
```

## 📋 前提条件

### 1. Docker Hub 账号
确保你已有 Docker Hub 账号，如果没有：
1. 访问 [https://hub.docker.com](https://hub.docker.com)
2. 注册免费账号
3. 创建仓库 `strm-poller`

### 2. 登录 Docker Hub
```bash
# 在终端登录
docker login

# 输入你的 Docker Hub 用户名和密码
```

### 3. 安装 Docker Buildx（构建需要）
```bash
# 检查是否已安装
docker buildx version

# 如果未安装，参考官方文档安装
# https://docs.docker.com/buildx/working-with-buildx/
```

## 🔧 构建脚本说明

### build-dockerhub.sh（amd64架构）
- ✅ 仅支持 AMD64/x86_64 架构
- ✅ 自动登录检查
- ✅ 自动创建 buildx 构建器
- ✅ 同时推送 `latest` 和版本标签
- ✅ 构建结果检查

## 📊 镜像标签说明

| 标签 | 说明 |
|------|------|
| `latest` | 最新稳定版本 |
| `v1.0.0` | 具体版本号 |
| `dev` | 开发版本 |

## 🔄 自动更新

使用 Watchtower 自动更新镜像：
```bash
# 在 docker-compose-dockerhub.yml 中已经配置
# 会自动检查并更新到最新版本
docker-compose -f docker-compose-dockerhub.yml up -d
```

## 🐛 常见问题

### 1. 构建失败
```bash
# 检查 Docker Buildx 是否安装
docker buildx version

# 清理构建缓存
docker buildx prune

# 重新创建构建器
docker buildx rm strm-poller-dockerhub
docker buildx create --name strm-poller-dockerhub --use
```

### 2. 推送失败
```bash
# 检查登录状态
docker info | grep Username

# 重新登录
docker login

# 检查网络连接
ping hub.docker.com
```

### 3. 权限问题
```bash
# 给脚本执行权限
chmod +x build-dockerhub.sh
```

## 📚 相关链接

- [Docker Hub 仓库](https://hub.docker.com/r/tgszy/strm-poller)
- [Docker Buildx 文档](https://docs.docker.com/buildx/working-with-buildx/)

- [STRM Poller 主文档](./README.md)

## 📞 支持

如有问题，请通过以下方式联系：
- 💬 [GitHub Issues](https://github.com/tgszy/strm-poller/issues)
- 📧 Docker Hub 讨论区

---

**Happy Dockerizing!** 🐳✨