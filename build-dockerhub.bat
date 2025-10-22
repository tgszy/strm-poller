@echo off
REM Windows Docker Hub 构建脚本

echo 🚀 开始构建 Docker Hub 镜像...
echo.

REM 检查Docker是否安装
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Docker 未安装或未添加到PATH
    echo 📥 请先安装 Docker Desktop:
    echo    https://www.docker.com/products/docker-desktop/
    echo.
    echo 🔄 安装完成后，请重新运行此脚本
    pause
    exit /b 1
)

REM 检查Docker是否运行
docker version >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Docker 未运行
    echo 🔄 请启动 Docker Desktop 后重新运行此脚本
    pause
    exit /b 1
)

REM 检查Docker Hub登录状态
echo 🔐 检查Docker Hub登录状态...
docker info | findstr /C:"Username:" >nul
if %errorlevel% neq 0 (
    echo 📥 请先登录Docker Hub:
    docker login
    if %errorlevel% neq 0 (
        echo ❌ Docker Hub登录失败
        pause
        exit /b 1
    )
)

REM 设置镜像名称
set DOCKERHUB_IMAGE=tgszy/strm-poller
if "%1"=="" (
    set VERSION=latest
) else (
    set VERSION=%1
)

echo 🔨 开始构建镜像...
docker build -t %DOCKERHUB_IMAGE%:%VERSION% -t %DOCKERHUB_IMAGE%:latest .

if %errorlevel% neq 0 (
    echo ❌ 镜像构建失败
    pause
    exit /b 1
)

echo 📤 推送到Docker Hub...
docker push %DOCKERHUB_IMAGE%:%VERSION%
docker push %DOCKERHUB_IMAGE%:latest

if %errorlevel% neq 0 (
    echo ❌ 推送失败
    pause
    exit /b 1
)

echo ✅ 构建和推送完成！
echo 🔗 Docker Hub链接: https://hub.docker.com/r/%DOCKERHUB_IMAGE%
echo.
echo 🎉 镜像已成功推送到Docker Hub！
pause