import asyncio
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileMovedEvent
from typing import Set, Callable, Optional
import time
from .logger import logger
from .config import settings

class STRMFileHandler(FileSystemEventHandler):
    """STRM文件事件处理器"""
    
    def __init__(self, callback: Callable[[str], None]):
        self.callback = callback
        self.debounce_tasks = {}
        self.supported_extensions = {'.strm'}
        
    def _is_strm_file(self, file_path: str) -> bool:
        """检查是否为STRM文件"""
        return Path(file_path).suffix.lower() in self.supported_extensions
    
    def _debounce_callback(self, file_path: str):
        """防抖回调"""
        async def debounced_task():
            await asyncio.sleep(settings.watch_debounce_seconds)
            if file_path in self.debounce_tasks:
                del self.debounce_tasks[file_path]
                if os.path.exists(file_path) and self._is_strm_file(file_path):
                    logger.info(f"处理STRM文件: {file_path}")
                    await self.callback(file_path)
        
        # 取消之前的任务
        if file_path in self.debounce_tasks:
            self.debounce_tasks[file_path].cancel()
        
        # 创建新任务
        task = asyncio.create_task(debounced_task())
        self.debounce_tasks[file_path] = task
    
    def on_created(self, event):
        """文件创建事件"""
        if not event.is_directory and self._is_strm_file(event.src_path):
            logger.debug(f"检测到STRM文件创建: {event.src_path}")
            asyncio.create_task(self._debounce_callback(event.src_path))
    
    def on_modified(self, event):
        """文件修改事件"""
        if not event.is_directory and self._is_strm_file(event.src_path):
            logger.debug(f"检测到STRM文件修改: {event.src_path}")
            asyncio.create_task(self._debounce_callback(event.src_path))
    
    def on_moved(self, event):
        """文件移动事件"""
        if not event.is_directory:
            # 检查源文件是否为STRM
            if self._is_strm_file(event.src_path):
                logger.debug(f"检测到STRM文件移动: {event.src_path} -> {event.dest_path}")
                if self._is_strm_file(event.dest_path):
                    asyncio.create_task(self._debounce_callback(event.dest_path))

class FileWatcher:
    """文件监控器"""
    
    def __init__(self):
        self.observer = None
        self.watch_handlers = {}
        self.running = False
        
    def add_watch_path(self, path: str, callback: Callable[[str], None]) -> bool:
        """添加监控路径"""
        try:
            if not os.path.exists(path):
                logger.error(f"监控路径不存在: {path}")
                return False
                
            if not os.path.isdir(path):
                logger.error(f"监控路径不是目录: {path}")
                return False
            
            # 创建事件处理器
            event_handler = STRMFileHandler(callback)
            
            # 开始监控
            self.observer.schedule(
                event_handler, 
                path, 
                recursive=settings.watch_recursive
            )
            
            self.watch_handlers[path] = event_handler
            logger.info(f"添加监控路径: {path}")
            return True
            
        except Exception as e:
            logger.error(f"添加监控路径失败 {path}: {e}")
            return False
    
    def remove_watch_path(self, path: str) -> bool:
        """移除监控路径"""
        try:
            if path in self.watch_handlers:
                # 取消所有防抖任务
                handler = self.watch_handlers[path]
                for task in handler.debounce_tasks.values():
                    task.cancel()
                
                del self.watch_handlers[path]
                logger.info(f"移除监控路径: {path}")
                return True
            return False
        except Exception as e:
            logger.error(f"移除监控路径失败 {path}: {e}")
            return False
    
    async def start(self):
        """开始监控"""
        if self.running:
            return
            
        try:
            self.observer = Observer()
            self.observer.start()
            self.running = True
            logger.info("文件监控器已启动")
            
            # 保持运行
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"文件监控器启动失败: {e}")
            self.running = False
            raise
    
    async def stop(self):
        """停止监控"""
        if not self.running:
            return
            
        self.running = False
        
        try:
            # 取消所有防抖任务
            for handler in self.watch_handlers.values():
                for task in handler.debounce_tasks.values():
                    task.cancel()
            
            # 停止观察者
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
            
            logger.info("文件监控器已停止")
            
        except Exception as e:
            logger.error(f"文件监控器停止失败: {e}")

class STRMFileProcessor:
    """STRM文件处理器"""
    
    def __init__(self):
        self.watcher = FileWatcher()
        self.processing_queue = asyncio.Queue()
        self.processing = False
        
    async def process_strm_file(self, file_path: str):
        """处理STRM文件"""
        try:
            logger.info(f"开始处理STRM文件: {file_path}")
            
            # 读取STRM文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                media_url = f.read().strip()
            
            if not media_url:
                logger.warning(f"STRM文件为空: {file_path}")
                return
            
            logger.info(f"STRM文件内容: {media_url}")
            
            # 这里可以添加更多的处理逻辑
            # 例如：验证URL、触发刮削任务等
            
            # 将任务添加到处理队列
            await self.processing_queue.put({
                'type': 'strm_file',
                'file_path': file_path,
                'media_url': media_url,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"处理STRM文件失败 {file_path}: {e}")
    
    async def start_watching(self, watch_paths: list):
        """开始监控指定路径"""
        # 添加监控路径
        for path in watch_paths:
            self.watcher.add_watch_path(path, self.process_strm_file)
        
        # 启动监控器
        await self.watcher.start()
    
    async def stop_watching(self):
        """停止监控"""
        await self.watcher.stop()
    
    async def process_queue(self):
        """处理队列中的任务"""
        self.processing = True
        
        while self.processing:
            try:
                # 获取队列中的任务
                task = await asyncio.wait_for(self.processing_queue.get(), timeout=1.0)
                
                # 处理任务
                if task['type'] == 'strm_file':
                    # 这里可以触发实际的刮削和整理任务
                    logger.info(f"处理队列任务: {task['file_path']}")
                
                self.processing_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"处理队列任务失败: {e}")
                self.processing_queue.task_done()
    
    def stop_processing(self):
        """停止处理队列"""
        self.processing = False

# 全局文件处理器实例
file_processor = STRMFileProcessor()