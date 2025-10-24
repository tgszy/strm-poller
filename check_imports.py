# 检查导入是否正常工作
print("开始检查导入...")

try:
    # 尝试导入所有相关模块
    from typing import Dict, Optional, Any, List
    print("✓ 成功导入typing模块")
except ImportError as e:
    print(f"✗ 导入typing模块失败: {e}")

try:
    # 检查notification模块
    from src.core.notification import notification_manager, NotificationEvents
    print("✓ 成功导入notification模块")
except Exception as e:
    print(f"✗ 导入notification模块失败: {e}")

try:
    # 检查proxy_memory模块
    from src.core.proxy_memory import ProxyManager, MemoryManager, ResourceMonitor, ProxyConfig
    print("✓ 成功导入proxy_memory模块")
except Exception as e:
    print(f"✗ 导入proxy_memory模块失败: {e}")

try:
    # 检查task_manager模块
    from src.core.task_manager import task_manager
    print("✓ 成功导入task_manager模块")
except Exception as e:
    print(f"✗ 导入task_manager模块失败: {e}")

print("导入检查完成。")