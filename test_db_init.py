#!/usr/bin/env python3
"""测试数据库初始化脚本"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.database import init_db, engine
from src.core.config import settings

print("=== 测试数据库初始化 ===")
print(f"数据库URL: {settings.database_url}")
print(f"数据库文件路径: {settings.sqlite_path}")

# 检查数据库文件是否存在
if os.path.exists(settings.sqlite_path):
    print(f"数据库文件已存在: {settings.sqlite_path}")
    # 删除现有数据库文件
    os.remove(settings.sqlite_path)
    print("已删除现有数据库文件")
else:
    print("数据库文件不存在，将创建新文件")

# 初始化数据库
print("正在初始化数据库...")
init_db()
print("数据库初始化完成")

# 检查表结构
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"数据库中的表: {tables}")

if 'scraper_configs' in tables:
    columns = [col['name'] for col in inspector.get_columns('scraper_configs')]
    print(f"scraper_configs表的列: {columns}")
    if 'api_url' in columns:
        print("✅ api_url字段已成功添加到数据库表")
    else:
        print("❌ api_url字段未添加到数据库表")
else:
    print("❌ scraper_configs表不存在")