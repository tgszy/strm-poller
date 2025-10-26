# STRM Poller Docker Run 命令示例

本文档提供多种场景下的Docker run命令示例，方便用户快速部署。

## 🚀 快速开始（推荐）

### 基础命令（使用相对路径）
```bash
docker run -d \
  --name=strm-poller \
  -p 35455:35455 \
  -v ./config:/config \
  -v ./src:/src:ro \
  -v ./dst:/dst \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

### Windows PowerShell
```powershell
docker run -d `
  --name=strm-poller `
  -p 35455:35455 `
  -v "./config:/config" `
  -v "./src:/src:ro" `
  -v "./dst:/dst" `
  --restart=unless-stopped `
  ghcr.io/tgszy/strm-poller:latest
```

## 📁 常见部署场景

### 1. NAS/服务器部署
```bash
docker run -d \
  --name=strm-poller \
  -p 35455:35455 \
  -v /mnt/user/appdata/strm-poller:/config \
  -v /mnt/user/aliyun:/src:ro \
  -v /mnt/user/emby:/dst \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Shanghai \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

### 2. Windows本地部署
```powershell
docker run -d `
  --name=strm-poller `
  -p 35455:35455 `
  -v "D:\Docker\strm-poller\config:/config" `
  -v "D:\Media\Source:/src:ro" `
  -v "D:\Media\Target:/dst" `
  -e TZ=Asia/Shanghai `
  --restart=unless-stopped `
  ghcr.io/tgszy/strm-poller:latest
```

### 3. 多源目录配置
```bash
docker run -d \
  --name=strm-poller \
  -p 35455:35455 \
  -v ./config:/config \
  -v /path/to/source1:/src:ro \
  -v /path/to/source2:/src2:ro \
  -v /path/to/source3:/src3:ro \
  -v /path/to/destination:/dst \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

### 4. 带代理配置
```bash
docker run -d \
  --name=strm-poller \
  -p 35455:35455 \
  -v ./config:/config \
  -v ./src:/src:ro \
  -v ./dst:/dst \
  -e PROXY_ENABLED=true \
  -e PROXY_TYPE=http \
  -e PROXY_HOST=192.168.1.100 \
  -e PROXY_PORT=7890 \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

### 5. 内存限制配置
```bash
docker run -d \
  --name=strm-poller \
  -p 35455:35455 \
  -v ./config:/config \
  -v ./src:/src:ro \
  -v ./dst:/dst \
  -e MAX_MEMORY=2048 \
  --memory=2g \
  --memory-swap=2g \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

## 🔧 高级配置

### 仅本地访问（提高安全性）
```bash
docker run -d \
  --name=strm-poller \
  -p 127.0.0.1:35455:35455 \
  -v ./config:/config \
  -v ./src:/src:ro \
  -v ./dst:/dst \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

### 使用Host网络模式
```bash
docker run -d \
  --name=strm-poller \
  --network=host \
  -v ./config:/config \
  -v ./src:/src:ro \
  -v ./dst:/dst \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

### 自定义配置路径
```bash
docker run -d \
  --name=strm-poller \
  -p 35455:35455 \
  -v /custom/config/path:/config \
  -v /custom/source/path:/src:ro \
  -v /custom/destination/path:/dst \
  -e CONFIG_PATH=/custom/config/path \
  -e SRC_PATH=/custom/source/path \
  -e DST_PATH=/custom/destination/path \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

## 📋 命令参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `-p 35455:35455` | 端口映射 | 将容器35455端口映射到主机35455端口 |
| `-v ./config:/config` | 配置目录映射 | 将本地config目录映射到容器/config |
| `-v ./src:/src:ro` | 源目录映射（只读） | 源目录设置为只读权限 |
| `-v ./dst:/dst` | 目标目录映射 | 目标目录需要读写权限 |
| `-e PUID=1000` | 用户ID | 确保文件权限正确 |
| `-e PGID=1000` | 组ID | 确保文件权限正确 |
| `-e TZ=Asia/Shanghai` | 时区设置 | 根据实际时区调整 |
| `--restart=unless-stopped` | 重启策略 | 容器异常退出时自动重启 |

## 🎯 使用建议

1. **首次部署**：使用基础命令，确保服务正常运行
2. **生产环境**：配置PUID/PGID确保文件权限正确
3. **多源场景**：使用多源目录配置支持多个源目录
4. **安全要求**：使用仅本地访问模式提高安全性
5. **性能优化**：根据实际需求调整内存限制

## 🔄 管理命令

```bash
# 查看容器状态
docker ps -a --filter "name=strm-poller"

# 查看容器日志
docker logs strm-poller

# 实时查看日志
docker logs -f strm-poller

# 停止容器
docker stop strm-poller

# 启动容器
docker start strm-poller

# 重启容器
docker restart strm-poller

# 删除容器
docker rm strm-poller
```

访问地址：http://localhost:35455