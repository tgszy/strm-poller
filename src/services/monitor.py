import asyncio
import json
from typing import Dict, Any, Set, List
from datetime import datetime
from ..core.logger import logger
from ..core.database import get_db, Task, FileRecord

class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Set[asyncio.Queue] = set()
        self.log_queue = asyncio.Queue()
        self.running = False
        
    async def connect(self, websocket_queue: asyncio.Queue):
        """添加WebSocket连接"""
        self.active_connections.add(websocket_queue)
        logger.info(f"WebSocket连接已添加，当前连接数: {len(self.active_connections)}")
        
    def disconnect(self, websocket_queue: asyncio.Queue):
        """移除WebSocket连接"""
        self.active_connections.discard(websocket_queue)
        logger.info(f"WebSocket连接已移除，当前连接数: {len(self.active_connections)}")
        
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息到所有连接"""
        if not self.active_connections:
            return
            
        # 移除已关闭的连接
        closed_connections = []
        
        for queue in self.active_connections:
            try:
                await queue.put(message)
            except Exception as e:
                logger.error(f"WebSocket消息发送失败: {e}")
                closed_connections.append(queue)
        
        # 清理已关闭的连接
        for queue in closed_connections:
            self.active_connections.discard(queue)
    
    async def log_processor(self):
        """日志处理器"""
        self.running = True
        
        while self.running:
            try:
                # 从日志队列获取消息
                log_data = await asyncio.wait_for(self.log_queue.get(), timeout=1.0)
                
                # 广播日志消息
                await self.broadcast({
                    "type": "log",
                    "data": log_data
                })
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"日志处理器错误: {e}")
    
    def stop(self):
        """停止日志处理器"""
        self.running = False

class TaskMonitor:
    """任务监控器"""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.running = False
        
    async def start_monitoring(self):
        """开始监控任务状态"""
        self.running = True
        
        while self.running:
            try:
                # 获取所有运行中的任务
                db = next(get_db())
                running_tasks = db.query(Task).filter(
                    Task.status.in_(["running", "pending"])
                ).all()
                
                # 广播任务状态
                task_data = []
                for task in running_tasks:
                    task_data.append({
                        "id": task.id,
                        "name": task.name,
                        "status": task.status,
                        "progress": task.progress,
                        "total_files": task.total_files,
                        "processed_files": task.processed_files,
                        "failed_files": task.failed_files,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "started_at": task.started_at.isoformat() if task.started_at else None
                    })
                
                await self.websocket_manager.broadcast({
                    "type": "task_update",
                    "data": task_data
                })
                
                db.close()
                
                # 每5秒更新一次
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"任务监控错误: {e}")
                await asyncio.sleep(5)
    
    def stop(self):
        """停止监控"""
        self.running = False

class StatisticsCollector:
    """统计收集器"""
    
    def __init__(self):
        self.stats_cache = {}
        self.cache_timeout = 60  # 缓存超时时间（秒）
        
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        import psutil
        import time
        
        current_time = time.time()
        cache_key = "system_stats"
        
        # 检查缓存
        if cache_key in self.stats_cache:
            cached_data, timestamp = self.stats_cache[cache_key]
            if current_time - timestamp < self.cache_timeout:
                return cached_data
        
        # 获取系统信息
        stats = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": {},
            "network_io": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # 磁盘使用情况
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                stats["disk_usage"][partition.mountpoint] = {
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent
                }
            except PermissionError:
                continue
        
        # 网络IO
        net_io = psutil.net_io_counters()
        stats["network_io"] = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv
        }
        
        # 缓存结果
        self.stats_cache[cache_key] = (stats, current_time)
        
        return stats
    
    def get_task_stats(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        db = next(get_db())
        
        try:
            # 任务状态统计
            task_stats = {}
            for status in ["pending", "running", "completed", "failed", "paused", "cancelled"]:
                count = db.query(Task).filter(Task.status == status).count()
                task_stats[status] = count
            
            # 文件处理统计
            file_stats = {}
            for status in ["pending", "processing", "completed", "failed"]:
                count = db.query(FileRecord).filter(FileRecord.status == status).count()
                file_stats[status] = count
            
            # 今日统计
            from datetime import date
            today = date.today()
            
            today_tasks = db.query(Task).filter(
                Task.created_at >= today
            ).count()
            
            today_files = db.query(FileRecord).filter(
                FileRecord.created_at >= today
            ).count()
            
            stats = {
                "tasks": task_stats,
                "files": file_stats,
                "today": {
                    "tasks": today_tasks,
                    "files": today_files
                },
                "timestamp": datetime.now().isoformat()
            }
            
            return stats
            
        finally:
            db.close()
    
    def clear_cache(self):
        """清除缓存"""
        self.stats_cache.clear()

# 全局实例
websocket_manager = WebSocketManager()
task_monitor = TaskMonitor(websocket_manager)
stats_collector = StatisticsCollector()