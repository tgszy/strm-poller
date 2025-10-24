# 测试运行状态指南

本文档提供了详细的测试步骤和命令示例，用于验证使用 `docker run` 和 `docker-compose` 两种方式运行 strm-poller 项目的状态。

## 目录

- [前提条件](#前提条件)
- [Docker Run 方式测试](#docker-run-方式测试)
  - [启动测试](#启动测试)
  - [功能验证](#功能验证)
  - [路径映射测试](#路径映射测试)
  - [清理测试环境](#清理测试环境)
- [Docker Compose 方式测试](#docker-compose-方式测试)
  - [启动测试](#启动测试-1)
  - [功能验证](#功能验证-1)
  - [路径映射测试](#路径映射测试-1)
  - [清理测试环境](#清理测试环境-1)
- [常见问题排查](#常见问题排查)
- [自动化测试脚本](#自动化测试脚本)

## 前提条件

- 已安装 Docker 和 Docker Compose
- 已下载 strm-poller 项目或准备好使用官方镜像
- 已创建测试用的目录结构用于路径映射测试

### 创建测试目录结构

在测试前，建议创建以下测试目录：

```bash
# Linux/macOS
mkdir -p ~/strm-test/config
mkdir -p ~/strm-test/src
mkdir -p ~/strm-test/dst

# Windows PowerShell
mkdir -p $env:USERPROFILE\strm-test\config
mkdir -p $env:USERPROFILE\strm-test\src
mkdir -p $env:USERPROFILE\strm-test\dst
```

## Docker Run 方式测试

### 启动测试

#### Linux/macOS 测试命令

```bash
# 基础启动测试
docker run -d \
  --name strm-poller-test \
  -p 3456:3456 \
  -v ~/strm-test/config:/config \
  -v ~/strm-test/src:/src:ro \
  -v ~/strm-test/dst:/dst \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Shanghai \
  -e LOG_LEVEL=DEBUG \
  ghcr.io/tgszy/strm-poller:latest

# 等待服务启动
sleep 10
```

#### Windows PowerShell 测试命令

```powershell
# 基础启动测试
docker run -d `
  --name strm-poller-test `
  -p 3456:3456 `
  -v "$env:USERPROFILE\strm-test\config:/config" `
  -v "$env:USERPROFILE\strm-test\src:/src:ro" `
  -v "$env:USERPROFILE\strm-test\dst:/dst" `
  -e PUID=1000 `
  -e PGID=1000 `
  -e TZ=Asia/Shanghai `
  -e LOG_LEVEL=DEBUG `
  ghcr.io/tgszy/strm-poller:latest

# 等待服务启动
Start-Sleep -Seconds 10
```

### 功能验证

执行以下命令验证服务是否正常运行：

```bash
# 1. 检查容器状态
docker ps -a --filter "name=strm-poller-test"

# 2. 检查容器日志（确认启动成功）
docker logs strm-poller-test | grep -i "started"

# 3. 验证健康检查端点
docker exec strm-poller-test curl -s http://localhost:3456/api/health

# 4. 验证 API 端点
docker exec strm-poller-test curl -s http://localhost:3456/api/info

# 5. 验证 Web 界面（通过浏览器访问）
echo "请在浏览器中访问: http://localhost:3456"
```

预期结果：
- 容器状态应为 `Up`
- 日志中应包含启动成功的消息
- 健康检查端点应返回 `{"status":"healthy"}`
- API 端点应返回应用信息
- Web 界面应能正常访问

### 路径映射测试

```bash
# 1. 测试配置目录映射
docker exec strm-poller-test ls -la /config

# 2. 测试源目录映射（写入测试文件到源目录）
touch ~/strm-test/src/test_file.strm
docker exec strm-poller-test ls -la /src | grep test_file

# 3. 测试目标目录映射（在容器内写入文件到目标目录）
docker exec strm-poller-test touch /dst/container_written_file.txt
ls -la ~/strm-test/dst | grep container_written_file

# 4. 验证文件权限（确保PUID/PGID设置正确）
docker exec strm-poller-test id
```

### 清理测试环境

```bash
# 停止并删除测试容器
docker stop strm-poller-test
docker rm strm-poller-test

# 可选：清理测试数据
# rm -rf ~/strm-test
```

## Docker Compose 方式测试

### 启动测试

首先，创建一个测试用的 `docker-compose.test.yml` 文件：

```yaml
version: '3.8'

services:
  strm-poller-test:
    image: ghcr.io/tgszy/strm-poller:latest
    container_name: strm-poller-compose-test
    restart: unless-stopped
    ports:
      - "3457:3456"
    volumes:
      # Linux/macOS 路径
      - ~/strm-test/config:/config
      - ~/strm-test/src:/src:ro
      - ~/strm-test/dst:/dst
      # Windows 路径（注释掉上面的Linux路径，取消下面的注释）
      # - ${USERPROFILE}/strm-test/config:/config
      # - ${USERPROFILE}/strm-test/src:/src:ro
      # - ${USERPROFILE}/strm-test/dst:/dst
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Asia/Shanghai
      - LOG_LEVEL=DEBUG
    mem_limit: 1g
    memswap_limit: 1g
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3456/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

启动测试：

```bash
# 启动测试容器
docker-compose -f docker-compose.test.yml up -d

# 等待服务启动
sleep 10
```

### 功能验证

```bash
# 1. 检查服务状态
docker-compose -f docker-compose.test.yml ps

# 2. 检查服务日志
docker-compose -f docker-compose.test.yml logs | grep -i "started"

# 3. 验证健康状态
docker-compose -f docker-compose.test.yml exec strm-poller-test curl -s http://localhost:3456/api/health

# 4. 验证 Web 界面
echo "请在浏览器中访问: http://localhost:3457"
```

### 路径映射测试

```bash
# 1. 测试多路径映射（修改 docker-compose.test.yml 添加额外映射）
# 先停止服务
docker-compose -f docker-compose.test.yml down

# 修改 docker-compose.test.yml 添加额外的映射：
# - ~/strm-test/extra_src:/src_extra:ro
# - ~/strm-test/extra_dst:/dst_extra

# 重新启动服务
docker-compose -f docker-compose.test.yml up -d

# 创建测试文件
mkdir -p ~/strm-test/extra_src
mkdir -p ~/strm-test/extra_dst
touch ~/strm-test/extra_src/extra_test.strm

# 验证额外路径映射
docker-compose -f docker-compose.test.yml exec strm-poller-test ls -la /src_extra | grep extra_test
```

### 清理测试环境

```bash
# 停止并删除测试服务
docker-compose -f docker-compose.test.yml down

# 可选：清理测试数据
# rm -rf ~/strm-test
```

## 常见问题排查

### 容器启动失败

```bash
# 查看详细日志
docker logs strm-poller-test

# 检查端口是否被占用
docker port strm-poller-test
netstat -tuln | grep 3456
```

### 路径映射问题

```bash
# 检查容器内目录权限
docker exec strm-poller-test ls -la /config /src /dst

# 检查挂载卷信息
docker inspect strm-poller-test | grep -A 10 Mounts
```

### Windows 环境特殊排查

```powershell
# 检查 Docker Desktop 共享设置
# 打开 Docker Desktop -> Settings -> Resources -> File Sharing

# 检查 Windows 路径格式是否正确
# 使用正斜杠: C:/Users/username/strm-test/config
# 或使用双反斜杠: C:\\Users\\username\\strm-test\\config
```

## 自动化测试脚本

### Linux/macOS 测试脚本

创建 `test_strm_poller.sh`：

```bash
#!/bin/bash

set -e

echo "==================================="
echo "开始测试 strm-poller 运行状态"
echo "==================================="

# 创建测试目录
TEST_DIR="$HOME/strm-test"
mkdir -p "$TEST_DIR/config"
mkdir -p "$TEST_DIR/src"
mkdir -p "$TEST_DIR/dst"

echo "✓ 测试目录创建完成"

# 清理可能存在的旧容器
docker rm -f strm-poller-test 2>/dev/null || true
echo "✓ 旧容器清理完成"

# 启动测试容器
echo "启动 Docker Run 测试..."
docker run -d \
  --name strm-poller-test \
  -p 3456:3456 \
  -v "$TEST_DIR/config:/config" \
  -v "$TEST_DIR/src:/src:ro" \
  -v "$TEST_DIR/dst:/dst" \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Shanghai \
  -e LOG_LEVEL=DEBUG \
  ghcr.io/tgszy/strm-poller:latest

echo "✓ Docker Run 容器启动"

# 等待服务初始化
echo "等待服务初始化..."
sleep 15

# 验证容器状态
STATUS=$(docker inspect -f '{{.State.Status}}' strm-poller-test)
if [ "$STATUS" != "running" ]; then
  echo "❌ 容器未正常运行，状态: $STATUS"
  docker logs strm-poller-test
  exit 1
fi
echo "✓ 容器状态检查通过"

# 验证健康状态
HEALTH_STATUS=$(docker exec strm-poller-test curl -s http://localhost:3456/api/health 2>/dev/null)
if [[ "$HEALTH_STATUS" != *"healthy"* ]]; then
  echo "❌ 健康检查失败: $HEALTH_STATUS"
  docker logs strm-poller-test
  exit 1
fi
echo "✓ 健康检查通过"

# 验证路径映射
docker exec strm-poller-test touch /dst/test_mount.txt 2>/dev/null
if [ ! -f "$TEST_DIR/dst/test_mount.txt" ]; then
  echo "❌ 路径映射测试失败"
  exit 1
fi
echo "✓ 路径映射测试通过"

echo "==================================="
echo "Docker Run 方式测试成功！"
echo "请在浏览器访问: http://localhost:3456"
echo "==================================="

echo "测试完成。清理测试容器请运行:"
echo "docker stop strm-poller-test && docker rm strm-poller-test"
```

### Windows PowerShell 测试脚本

创建 `test_strm_poller.ps1`：

```powershell
Write-Host "===================================" -ForegroundColor Green
Write-Host "开始测试 strm-poller 运行状态" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Green

# 创建测试目录
$TEST_DIR = Join-Path $env:USERPROFILE "strm-test"
New-Item -ItemType Directory -Force -Path (Join-Path $TEST_DIR "config") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $TEST_DIR "src") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $TEST_DIR "dst") | Out-Null

Write-Host "✓ 测试目录创建完成" -ForegroundColor Green

# 清理可能存在的旧容器
try {
    docker rm -f strm-poller-test 2>$null
} catch {}
Write-Host "✓ 旧容器清理完成" -ForegroundColor Green

# 启动测试容器
Write-Host "启动 Docker Run 测试..." -ForegroundColor Yellow
docker run -d `
  --name strm-poller-test `
  -p 3456:3456 `
  -v "$TEST_DIR\config:/config" `
  -v "$TEST_DIR\src:/src:ro" `
  -v "$TEST_DIR\dst:/dst" `
  -e PUID=1000 `
  -e PGID=1000 `
  -e TZ=Asia/Shanghai `
  -e LOG_LEVEL=DEBUG `
  ghcr.io/tgszy/strm-poller:latest

Write-Host "✓ Docker Run 容器启动" -ForegroundColor Green

# 等待服务初始化
Write-Host "等待服务初始化..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# 验证容器状态
$STATUS = docker inspect -f '{{.State.Status}}' strm-poller-test
if ($STATUS -ne "running") {
    Write-Host "❌ 容器未正常运行，状态: $STATUS" -ForegroundColor Red
    docker logs strm-poller-test
    exit 1
}
Write-Host "✓ 容器状态检查通过" -ForegroundColor Green

# 验证健康状态
try {
    $HEALTH_STATUS = docker exec strm-poller-test curl -s http://localhost:3456/api/health
    if ($HEALTH_STATUS -notmatch "healthy") {
        Write-Host "❌ 健康检查失败: $HEALTH_STATUS" -ForegroundColor Red
        docker logs strm-poller-test
        exit 1
    }
    Write-Host "✓ 健康检查通过" -ForegroundColor Green
} catch {
    Write-Host "❌ 健康检查命令执行失败，请检查容器状态" -ForegroundColor Red
    docker logs strm-poller-test
    exit 1
}

# 验证路径映射
try {
    docker exec strm-poller-test touch /dst/test_mount.txt
    Start-Sleep -Seconds 2
    if (-not (Test-Path "$TEST_DIR\dst\test_mount.txt")) {
        Write-Host "❌ 路径映射测试失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ 路径映射测试通过" -ForegroundColor Green
} catch {
    Write-Host "❌ 路径映射测试命令执行失败" -ForegroundColor Red
    exit 1
}

Write-Host "===================================" -ForegroundColor Green
Write-Host "Docker Run 方式测试成功！" -ForegroundColor Green
Write-Host "请在浏览器访问: http://localhost:3456" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Green

Write-Host "测试完成。清理测试容器请运行:"
Write-Host "docker stop strm-poller-test && docker rm strm-poller-test" -ForegroundColor Yellow
```

### 运行测试脚本

```bash
# Linux/macOS
chmod +x test_strm_poller.sh
./test_strm_poller.sh

# Windows PowerShell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.	est_strm_poller.ps1
```

## 总结

本文档提供了全面的测试方法，帮助您验证 strm-poller 项目在 Docker 环境中的运行状态。通过遵循这些步骤，您可以确保：

1. 项目可以通过 docker run 和 docker-compose 两种方式正常启动
2. 路径映射功能正常工作，包括配置目录、源目录和目标目录
3. Web 界面可以正常访问和使用
4. 容器健康检查和日志记录功能正常

如果在测试过程中遇到任何问题，请参考常见问题排查部分获取解决方案。