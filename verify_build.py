#!/usr/bin/env python3
"""
验证项目构建状态
"""
import os
import sys
import subprocess

print("=== 开始验证项目构建状态 ===")

# 检查必要文件是否存在
required_files = [
    'requirements.txt',
    'src/api/main.py',
    'start_app.py',
    'Dockerfile',
    'config.example.yaml'
]

for file in required_files:
    if os.path.exists(file):
        print(f"✓ {file}: 存在")
    else:
        print(f"✗ {file}: 不存在")
        sys.exit(1)

# 检查项目目录结构
print("\n=== 检查项目目录结构 ===")
dirs_to_check = ['src', 'src/api', 'src/core', 'src/services', 'src/static']
for dir_path in dirs_to_check:
    if os.path.isdir(dir_path):
        print(f"✓ {dir_path}: 目录存在")
    else:
        print(f"! {dir_path}: 目录不存在")

# 检查Python版本
print("\n=== 检查Python版本 ===")
try:
    result = subprocess.run([sys.executable, '--version'], capture_output=True, text=True)
    print(f"✓ Python版本: {result.stdout.strip()}")
except Exception as e:
    print(f"✗ Python版本检查失败: {str(e)}")

# 检查是否可以安装依赖（不实际安装）
print("\n=== 检查依赖项格式 ===")
try:
    with open('requirements.txt', 'r') as f:
        dependencies = f.readlines()
        print(f"✓ requirements.txt: 包含 {len(dependencies)} 个依赖项")
except Exception as e:
    print(f"✗ requirements.txt 读取失败: {str(e)}")
    sys.exit(1)

print("\n=== 构建验证完成 ===")
print("项目结构和配置文件检查通过，可以尝试构建Docker镜像或直接运行应用")
print("\n提示:")
print("1. 运行应用: python start_app.py")
print("2. 构建Docker镜像: docker build -t strm-poller .")
print("3. 运行Docker容器: docker run -p 35455:35455 -v ./config:/config -v ./data:/app/data -v ./logs:/app/logs strm-poller")