# STRM Poller 安装指南

本指南提供了在不同环境下安装和配置STRM Poller的详细步骤。

## 📋 系统要求

### Docker 环境要求
- Docker 19.03+ 或 Docker Desktop
- 至少 1GB 可用内存
- 至少 100MB 可用磁盘空间
- 支持 amd64/x86_64 架构

### 直接运行要求
- Python 3.8+
- pip 20.0+
- 系统依赖库（见下方详细说明）

## 🐳 Docker 安装（推荐）

### 在 NAS 和 Linux 环境下

#### 方法 1: 使用 docker-compose

1. 克隆或下载项目代码
```bash
git clone https://github.com/tgszy/strm-poller.git
cd strm-poller
```

2. 根据实际情况修改 `docker-compose.yml` 中的路径映射

3. 创建必要的目录结构
```bash
mkdir -p /mnt/user/appdata/strm-poller  # 配置目录
# 确保源目录和目标目录已存在
```

4. 启动容器
```bash
docker-compose up -d
```

#### 方法 2: 使用 docker run

```bash
docker run -d \
  --name=strm-poller \
  -p 3456:3456 \
  # 配置目录
  -v /mnt/user/appdata/strm-poller:/config \
  # 源目录（只读）
  -v /mnt/user/aliyun:/src:ro \
  # 目标目录
  -v /mnt/user/emby:/dst \
  # 环境变量
  -e PUID=1000 -e PGID=1000 -e TZ=Asia/Shanghai \
  -e MAX_MEMORY=1024 \
  # 内存限制
  --memory=1g --memory-swap=1g \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

### 在 Windows 环境下

Windows环境下需要特别注意路径映射的配置。以下是详细步骤：

#### 方法 1: 使用 Windows 版 Docker Desktop

1. 安装并启动 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)

2. 确保已启用 WSL 2 后端（推荐）

3. 创建必要的目录结构
   - 在 Windows 中创建文件夹，例如：
     - `D:\Docker\strm-poller\config`
     - `D:\Media\Source` (存放 .strm 文件)
     - `D:\Media\Target` (目标媒体库)

4. 修改 docker-compose.yml 文件中的路径映射：
```yaml
volumes:
  - "D:\Docker\strm-poller\config:/config"
  - "D:\Media\Source:/src:ro"
  - "D:\Media\Target:/dst"
```

5. 启动容器
```powershell
docker-compose up -d
```

#### 方法 2: 使用 PowerShell 命令行

```powershell
docker run -d `
  --name=strm-poller `
  -p 3456:3456 `
  -v "D:\Docker\strm-poller\config:/config" `
  -v "D:\Media\Source:/src:ro" `
  -v "D:\Media\Target:/dst" `
  -e PUID=1000 -e PGID=1000 -e TZ=Asia/Shanghai `
  -e MAX_MEMORY=1024 `
  --memory=1g --memory-swap=1g `
  --restart=unless-stopped `
  ghcr.io/tgszy/strm-poller:latest
```

## 📝 直接运行（开发环境）

### Linux/Mac 环境

1. 克隆项目代码
```bash
git clone https://github.com/tgszy/strm-poller.git
cd strm-poller
```

2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate
```

3. 安装依赖
```bash
# 安装系统依赖
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y gcc python3-dev libffi-dev libssl-dev sqlite3

# CentOS/RHEL
sudo yum install -y gcc python3-devel libffi-devel openssl-devel sqlite-devel

# 安装 Python 依赖
pip install -r requirements.txt
```

4. 创建配置文件
```bash
cp config.example.yaml config.yaml
# 编辑配置文件，设置必要的路径和参数
```

5. 运行应用
```bash
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 3456
```

### Windows 环境

1. 克隆项目代码
```powershell
git clone https://github.com/tgszy/strm-poller.git
cd strm-poller
```

2. 创建虚拟环境
```powershell
python -m venv venv
.\venv\Scripts\activate
```

3. 安装依赖
```powershell
# 安装 Microsoft Build Tools 以编译某些依赖
# 访问 https://visualstudio.microsoft.com/downloads/ 下载 Build Tools

# 安装 Python 依赖
pip install -r requirements.txt
```

4. 创建配置文件
```powershell
Copy-Item config.example.yaml -Destination config.yaml
# 使用文本编辑器编辑配置文件
```

5. 运行应用
```powershell
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 3456
```

## 🔄 路径映射配置详解

### 容器内关键路径

| 容器内路径 | 用途 | 权限要求 |
|------------|------|----------|
| `/config` | 配置文件、数据库、日志 | 读写 |
| `/src` | 源 .strm 文件目录 | 只读 |
| `/dst` | 整理后的媒体文件目录 | 读写 |

### 常见路径映射场景

#### 在 Unraid 或其他 NAS 系统上
```yaml
volumes:
  - /mnt/user/appdata/strm-poller:/config
  - /mnt/user/aliyun:/src:ro
  - /mnt/user/emby:/dst
```

#### 在 Synology DSM 上
```yaml
volumes:
  - /volume1/docker/strm-poller:/config
  - /volume1/video/aliyun:/src:ro
  - /volume1/video/media:/dst
```

#### 在 Windows 上
```yaml
volumes:
  - "D:\Docker\strm-poller\config:/config"
  - "D:\Media\Source:/src:ro"
  - "D:\Media\Target:/dst"
```

## 🔧 环境变量配置

重要的环境变量列表：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `PUID` | 1000 | 用户ID，必须与挂载目录权限匹配 |
| `PGID` | 1000 | 用户组ID，必须与挂载目录权限匹配 |
| `TZ` | Asia/Shanghai | 时区设置 |
| `MAX_MEMORY` | 1024 | 内存限制（MB） |
| `PROXY_ENABLED` | false | 是否启用代理 |
| `LOG_LEVEL` | INFO | 日志级别 |

## 📁 配置文件说明

除了环境变量外，也可以使用 YAML 配置文件进行更详细的配置。配置文件位于 `/config/config.yaml`。

请参考项目根目录的 `config.example.yaml` 文件，复制并根据需要修改。

## ✅ 验证安装

1. 安装完成后，访问 Web UI：`http://<服务器IP>:3456`

2. 检查健康状态：`http://<服务器IP>:3456/api/health`

3. 查看日志确认服务正常启动
```bash
docker logs strm-poller
```

## 🚧 常见问题排查

### 权限问题
- 确保 PUID 和 PGID 与挂载目录的所有者匹配
- 检查主机上目录的读写权限

### 路径映射问题
- 确保主机上的目录已创建
- Windows 上注意使用正确的路径格式
- 检查路径大小写（特别是 Linux 系统）

### 内存限制问题
- 如果出现 OOM 错误，增加 MAX_MEMORY 值和 Docker 容器内存限制

### 网络问题
- 确保端口 3456 未被占用
- 检查防火墙设置是否允许访问该端口