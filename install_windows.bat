@echo off
echo ========================================
echo STRM Poller Windows 一键安装脚本
echo ========================================
echo.

rem 检查Docker是否已安装
echo [1/6] 检查Docker环境...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未检测到Docker，请先安装Docker Desktop
    echo 下载地址: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

echo Docker已安装，版本: 
docker --version

rem 检查Docker服务是否运行
echo [2/6] 检查Docker服务状态...
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: Docker服务未运行，请启动Docker Desktop
    pause
    exit /b 1
)

echo Docker服务运行正常

rem 创建默认目录结构
echo [3/6] 创建默认目录结构...
if not exist "%USERPROFILE%\Documents\strm-poller" mkdir "%USERPROFILE%\Documents\strm-poller"
if not exist "%USERPROFILE%\Documents\strm-poller\config" mkdir "%USERPROFILE%\Documents\strm-poller\config"
if not exist "%USERPROFILE%\Documents\strm-poller\source" mkdir "%USERPROFILE%\Documents\strm-poller\source"
if not exist "%USERPROFILE%\Documents\strm-poller\target" mkdir "%USERPROFILE%\Documents\strm-poller\target"

echo 目录创建完成:
echo   - 配置目录: %USERPROFILE%\Documents\strm-poller\config
echo   - 源文件目录: %USERPROFILE%\Documents\strm-poller\source
echo   - 目标目录: %USERPROFILE%\Documents\strm-poller\target

rem 检查是否已有运行的容器
echo [4/6] 检查现有容器...
docker ps -a --filter "name=strm-poller" | findstr "strm-poller" >nul
if %errorlevel% == 0 (
    echo 发现已存在的strm-poller容器，正在停止并删除...
    docker stop strm-poller >nul 2>&1
    docker rm strm-poller >nul 2>&1
    echo 旧容器已清理
)

rem 拉取最新镜像并运行
echo [5/6] 拉取最新镜像并启动容器...
echo 正在拉取最新镜像...
docker pull ghcr.io/tgszy/strm-poller:latest

echo 启动STRM Poller容器...
docker run -d ^
  --name=strm-poller ^
  -p 35455:35455 ^
  -v "%USERPROFILE%\Documents\strm-poller\config:/config" ^
  -v "%USERPROFILE%\Documents\strm-poller\source:/src:ro" ^
  -v "%USERPROFILE%\Documents\strm-poller\target:/dst" ^
  -e PUID=1000 ^
  -e PGID=1000 ^
  -e TZ=Asia/Shanghai ^
  -e MAX_MEMORY=1024 ^
  --memory=1g ^
  --memory-swap=1g ^
  --restart=unless-stopped ^
  ghcr.io/tgszy/strm-poller:latest

if %errorlevel% neq 0 (
    echo 错误: 容器启动失败
    pause
    exit /b 1
)

echo [6/6] 等待服务启动...
timeout /t 10 /nobreak >nul

rem 检查容器状态
echo 检查容器运行状态...
docker ps --filter "name=strm-poller" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo ========================================
echo 安装完成！
echo ========================================
echo.
echo 访问地址: http://localhost:35455
echo.
echo 重要说明:
echo 1. 首次访问会自动打开设置向导
echo 2. 源文件请放置在: %USERPROFILE%\Documents\strm-poller\source
echo 3. 整理后的文件将输出到: %USERPROFILE%\Documents\strm-poller\target
echo 4. 配置文件和日志在: %USERPROFILE%\Documents\strm-poller\config
echo.
echo 如需停止服务，运行: docker stop strm-poller
echo 如需启动服务，运行: docker start strm-poller
echo.
pause