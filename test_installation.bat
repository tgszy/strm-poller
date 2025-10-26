@echo off
echo ========================================
echo STRM Poller 安装测试脚本
echo ========================================
echo.

rem 检查Docker环境
echo [1/4] 检查Docker环境...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker未安装
    echo 请先安装Docker Desktop: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo ✅ Docker已安装: 
docker --version

rem 检查Docker服务
echo [2/4] 检查Docker服务状态...
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker服务未运行
    echo 请启动Docker Desktop
    pause
    exit /b 1
)
echo ✅ Docker服务运行正常

rem 检查一键安装脚本
echo [3/4] 检查一键安装脚本...
if exist "install_windows.bat" (
    echo ✅ install_windows.bat 存在
    echo   文件大小: %~z0 bytes
) else (
    echo ❌ install_windows.bat 不存在
)

if exist "install_linux.sh" (
    echo ✅ install_linux.sh 存在
) else (
    echo ❌ install_linux.sh 不存在
)

rem 检查Docker Compose文件
echo [4/4] 检查Docker配置文件...
if exist "docker-compose.yml" (
    echo ✅ docker-compose.yml 存在
) else (
    echo ❌ docker-compose.yml 不存在
)

if exist "Dockerfile" (
    echo ✅ Dockerfile 存在
) else (
    echo ❌ Dockerfile 不存在
)

echo.
echo ========================================
echo 测试完成！
echo ========================================
echo.
echo 下一步操作建议:
echo 1. Windows用户: 双击运行 install_windows.bat
echo 2. Linux/macOS用户: 运行 chmod +x install_linux.sh && ./install_linux.sh
echo 3. 访问 http://localhost:35455 开始使用
echo.
pause