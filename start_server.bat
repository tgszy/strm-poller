@echo off
cd /d %~dp0

rem 激活虚拟环境
echo 激活虚拟环境...
venv\Scripts\activate

rem 启动服务 - 使用配置文件中的45678端口（桥接模式）
echo 启动STRM Poller服务...
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 35455 --reload