@echo off
cd /d %~dp0

rem 激活虚拟环境
echo 激活虚拟环境...
venv\Scripts\activate

rem 升级pip
echo 升级pip...
python -m pip install --upgrade pip

rem 安装依赖，使用--no-cache-dir避免缓存问题
echo 安装项目依赖...
pip install --no-cache-dir -r requirements.txt

echo 依赖安装完成！
pause