# Docker Run 命令示例

本文档提供了使用 `docker run` 命令运行 strm-poller 的详细示例，确保在不同环境下都能正确映射路径并访问后台页面。

## 基本命令结构

```bash
docker run -d \
  --name strm-poller \
  -p 3456:3456 \
  -v <本地配置目录>:/config \
  -v <本地源目录>:/src:ro \
  -v <本地目标目录>:/dst \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

## Linux/macOS 环境示例

### 基本运行命令

```bash
docker run -d \
  --name strm-poller \
  -p 3456:3456 \
  -v $PWD/config:/config \
  -v /mnt/user/aliyun:/src:ro \
  -v /mnt/user/emby:/dst \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Shanghai \
  -e MAX_MEMORY=1024 \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  --health-cmd "curl -f http://localhost:3456/api/health || exit 1" \
  --health-interval 30s \
  --health-timeout 10s \
  --health-retries 3 \
  --health-start-period 40s \
  ghcr.io/tgszy/strm-poller:latest
```

### 自定义多路径映射

```bash
docker run -d \
  --name strm-poller \
  -p 3456:3456 \
  -v $PWD/config:/config \
  -v /media/source1:/src:ro \
  -v /media/source2:/src2:ro \
  -v /media/destination1:/dst \
  -v /media/destination2:/dst2 \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

## Windows 环境示例

### PowerShell 命令示例

在 Windows PowerShell 中运行以下命令：

```powershell
docker run -d `
  --name strm-poller `
  -p 3456:3456 `
  -v ${pwd}\config:/config `
  -v D:\media\aliyun:/src:ro `
  -v D:\media\emby:/dst `
  -e PUID=1000 `
  -e PGID=1000 `
  -e TZ=Asia/Shanghai `
  -e MAX_MEMORY=1024 `
  -e LOG_LEVEL=INFO `
  --restart unless-stopped `
  ghcr.io/tgszy/strm-poller:latest
```

### CMD 命令示例

在 Windows CMD 中运行以下命令：

```cmd
docker run -d ^
  --name strm-poller ^
  -p 3456:3456 ^
  -v %cd%\config:/config ^
  -v D:\media\aliyun:/src:ro ^
  -v D:\media\emby:/dst ^
  -e PUID=1000 ^
  -e PGID=1000 ^
  -e TZ=Asia/Shanghai ^
  -e MAX_MEMORY=1024 ^
  -e LOG_LEVEL=INFO ^
  --restart unless-stopped ^
  ghcr.io/tgszy/strm-poller:latest
```

## 自定义路径映射说明

### 源目录映射

您可以根据需要映射多个源目录（包含.strm文件的目录）：

```bash
# Linux/macOS 多源目录示例
docker run -d \
  --name strm-poller \
  -p 3456:3456 \
  -v $PWD/config:/config \
  -v /path/to/source1:/src:ro \
  -v /path/to/source2:/src2:ro \
  -v /path/to/source3:/src3:ro \
  -v /path/to/destination:/dst \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

### 目标目录映射

同样，您可以映射多个目标目录：

```bash
# Linux/macOS 多目标目录示例
docker run -d \
  --name strm-poller \
  -p 3456:3456 \
  -v $PWD/config:/config \
  -v /path/to/source:/src:ro \
  -v /path/to/dest1:/dst \
  -v /path/to/dest2:/dst2 \
  -v /path/to/dest3:/dst3 \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

## Windows 路径映射注意事项

1. **路径格式**：在 Docker for Windows 中，路径映射需要注意格式：
   - 使用正斜杠 `/` 而不是反斜杠 `\`（除了在 PowerShell 中使用变量时）
   - 完整路径需要包含驱动器号，如 `D:/media`

2. **共享文件夹**：确保您尝试映射的 Windows 文件夹已在 Docker Desktop 设置中被共享。

3. **文件权限**：Windows 文件权限可能与 Linux 容器不完全兼容，建议：
   - 使用 `-e PUID=1000 -e PGID=1000` 设置适当的用户权限
   - 对于源目录，使用 `:ro` 只读模式可以避免权限问题

## 检查运行状态

运行容器后，您可以通过以下命令检查容器状态：

```bash
# 查看容器状态
docker ps -a --filter "name=strm-poller"

# 查看容器日志
docker logs strm-poller

# 访问健康检查端点
curl http://localhost:3456/api/health
```

## 访问后台页面

容器启动成功后，可以通过以下地址访问后台页面：

```
http://localhost:3456
```

如果在不同机器上运行，可以使用容器所在机器的 IP 地址替换 `localhost`。

## 停止和删除容器

```bash
# 停止容器
docker stop strm-poller

# 删除容器
docker rm strm-poller
```

## 常见问题排查

1. **路径映射错误**：如果出现路径映射错误，请检查：
   - 本地路径是否存在且可访问
   - Windows 文件夹是否已在 Docker Desktop 中共享
   - 路径格式是否正确

2. **权限问题**：如果出现权限相关错误，请尝试：
   - 调整 PUID 和 PGID 值
   - 确保源目录使用 `:ro` 只读模式

3. **端口冲突**：如果 3456 端口已被占用，可以修改映射端口：
   ```bash
   -p 8080:3456  # 使用主机的 8080 端口映射到容器的 3456 端口
   ```