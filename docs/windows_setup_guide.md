# Windows 环境安装指南

本文档提供在 Windows 环境下运行 strm-poller 的详细指南，特别关注路径映射问题的解决方案。

## 前提条件

1. 安装 Docker Desktop for Windows
2. 确保 Docker Desktop 已启用 WSL 2 后端（推荐）或 Hyper-V 后端
3. 确保您要映射的文件夹已在 Docker Desktop 中共享

## Docker Desktop 文件夹共享配置

1. 打开 Docker Desktop 设置
2. 导航到 `Resources > File Sharing`
3. 点击 `+` 按钮添加您需要映射的驱动器或文件夹
4. 点击 `Apply & Restart` 应用更改

## Windows 路径映射规则

### 路径格式转换

在 Windows 环境中使用 Docker 时，路径映射需要遵循以下规则：

1. **使用正斜杠**：Docker 容器内部使用正斜杠 `/` 作为路径分隔符
2. **驱动器号**：Windows 路径必须包含驱动器号，如 `C:`、`D:` 等
3. **路径转换示例**：
   - Windows 路径：`D:\media\strm-files`
   - Docker 映射格式：`D:/media/strm-files:/src`

### PowerShell 中的路径变量

在 PowerShell 中，可以使用以下变量来简化路径映射：

```powershell
# 当前目录
${pwd} 或 $PWD

# 例如：映射当前目录下的 config 文件夹
-v ${pwd}\config:/config
```

### CMD 中的路径变量

在 CMD 中，使用 `%cd%` 表示当前目录：

```cmd
# 映射当前目录下的 config 文件夹
-v %cd%\config:/config
```

## Windows 特定的 docker run 命令示例

### PowerShell 完整示例

```powershell
docker run -d `
  --name strm-poller `
  -p 3456:3456 `
  -v ${pwd}\config:/config `
  -v D:/media/strm-files:/src:ro `
  -v D:/media/organized:/dst `
  -e PUID=1000 `
  -e PGID=1000 `
  -e TZ=Asia/Shanghai `
  -e MAX_MEMORY=1024 `
  -e LOG_LEVEL=INFO `
  --restart unless-stopped `
  ghcr.io/tgszy/strm-poller:latest
```

### CMD 完整示例

```cmd
docker run -d ^
  --name strm-poller ^
  -p 3456:3456 ^
  -v %cd%\config:/config ^
  -v D:/media/strm-files:/src:ro ^
  -v D:/media/organized:/dst ^
  -e PUID=1000 ^
  -e PGID=1000 ^
  -e TZ=Asia/Shanghai ^
  -e MAX_MEMORY=1024 ^
  -e LOG_LEVEL=INFO ^
  --restart unless-stopped ^
  ghcr.io/tgszy/strm-poller:latest
```

## Windows 特定的 docker-compose 配置

### docker-compose.yml 示例（Windows 优化版）

```yaml
version: '3.8'

services:
  strm-poller:
    image: ghcr.io/tgszy/strm-poller:latest
    container_name: strm-poller
    restart: unless-stopped
    ports:
      - "3456:3456"
    volumes:
      # Windows 路径格式示例
      - ${pwd}\config:/config  # PowerShell 中使用
      # 或使用绝对路径
      # - C:/path/to/config:/config
      
      # 源目录 - 包含.strm文件
      - D:/media/strm-files:/src:ro
      
      # 目标目录 - 整理后的媒体文件
      - D:/media/organized:/dst
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Asia/Shanghai
      - MAX_MEMORY=1024
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3456/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 使用 docker-compose 的注意事项

1. **在 PowerShell 中运行**：
   ```powershell
   docker-compose up -d
   ```

2. **在 CMD 中运行**：
   ```cmd
   docker-compose up -d
   ```

3. **路径变量**：在 docker-compose.yml 中，Windows 下可以使用以下变量：
   - `./config` - 相对于 docker-compose.yml 文件的路径
   - `${pwd}\config` - PowerShell 中的当前目录
   - 绝对路径，如 `D:/media/config`

## 多路径映射示例（Windows）

### docker run 多路径映射

```powershell
docker run -d `
  --name strm-poller `
  -p 3456:3456 `
  -v ${pwd}\config:/config `
  -v D:/media/source1:/src:ro `
  -v D:/media/source2:/src2:ro `
  -v D:/media/source3:/src3:ro `
  -v D:/media/dest1:/dst `
  -v D:/media/dest2:/dst2 `
  -e PUID=1000 `
  -e PGID=1000 `
  -e TZ=Asia/Shanghai `
  --restart unless-stopped `
  ghcr.io/tgszy/strm-poller:latest
```

## Windows 路径问题排查

### 常见错误及解决方案

1. **路径未共享**
   - **错误信息**：`Error response from daemon: invalid mount config for type "bind": bind source path does not exist`
   - **解决方案**：确保该路径已在 Docker Desktop 的 File Sharing 设置中添加

2. **路径格式错误**
   - **错误信息**：各种路径相关错误
   - **解决方案**：使用正斜杠 `/` 而不是反斜杠 `\`，确保包含驱动器号

3. **权限问题**
   - **错误信息**：权限被拒绝或无法访问文件
   - **解决方案**：
     - 确保使用正确的 PUID/PGID 值
     - 对于源目录，使用 `:ro` 只读模式
     - 检查 Windows 文件权限设置

4. **驱动器字母大小写**
   - **注意事项**：在路径映射中，驱动器字母的大小写（如 `D:` 和 `d:`）通常不敏感，但保持一致性更好

## 性能优化（Windows）

1. **使用 WSL 2 后端**：相比 Hyper-V，WSL 2 提供更好的文件系统性能

2. **避免映射大量小文件的目录**：这可能导致性能下降

3. **考虑使用 Docker 卷**：对于频繁访问的数据，考虑使用 Docker 管理的卷而不是绑定挂载

## 访问后台页面

在 Windows 环境中，启动容器后，可以通过以下地址访问后台页面：

```
http://localhost:3456
```

## 检查容器状态（Windows）

### PowerShell 命令

```powershell
# 查看容器状态
docker ps -a --filter "name=strm-poller"

# 查看容器日志
docker logs strm-poller

# 访问健康检查端点
curl http://localhost:3456/api/health
```

## 停止和删除容器（Windows）

### PowerShell 命令

```powershell
# 停止容器
docker stop strm-poller

# 删除容器
docker rm strm-poller
```

## 注意事项

1. **反斜杠转义**：在某些情况下，您可能需要对反斜杠进行转义，使用 `\\` 代替 `\`

2. **UNC 路径**：不建议直接映射 UNC 路径（如 `\\server\share`），建议先映射为网络驱动器

3. **长路径**：Windows 有路径长度限制，考虑使用较短的路径或启用长路径支持

4. **文件锁定**：Windows 文件锁定机制与 Linux 不同，可能导致某些文件操作问题

5. **符号链接**：容器内可能无法正确处理 Windows 符号链接