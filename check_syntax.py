#!/usr/bin/env python3
"""
检查所有Python文件中的语法错误
"""
import os
import sys
import compileall

print("=== 开始检查Python文件语法 ===")

# 检查src目录下的所有Python文件
src_dir = os.path.join(os.path.dirname(__file__), 'src')

if not os.path.exists(src_dir):
    print(f"错误: 找不到src目录: {src_dir}")
    sys.exit(1)

# 使用compileall检查所有.py文件
result = compileall.compile_dir(src_dir, force=True, quiet=True)

print(f"语法检查完成: {'成功' if result else '失败'}")

# 单独检查关键文件
key_files = [
    'start_app.py',
]

for file in key_files:
    file_path = os.path.join(os.path.dirname(__file__), file)
    if os.path.exists(file_path):
        try:
            compileall.compile_file(file_path, force=True, quiet=True)
            print(f"✓ {file}: 语法正确")
        except Exception as e:
            print(f"✗ {file}: 语法错误 - {str(e)}")
    else:
        print(f"! {file}: 文件不存在")

print("=== 语法检查完成 ===")