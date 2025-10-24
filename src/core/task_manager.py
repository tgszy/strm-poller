import asyncio
import os
import shutil
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from .database import get_db, Task, FileRecord
from .logger import logger
from .config import settings
from .scrapers import ScraperManager
from .notification import notification_manager, NotificationEvents
import json

class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.running_tasks = {}
        self.task_workers = {}
        self.scraper_manager = None
        
    def init_scraper_manager(self, proxy_manager=None):
        """初始化刮削器管理器"""
        # 构建刮削器配置
        scraper_configs = {
            'tmdb': {
                'enabled': bool(settings.tmdb_api_key),
                'api_key': settings.tmdb_api_key,
                'language': settings.tmdb_language,
                'priority': 1,
                'timeout': 30,
                'retry_count': 3,
                'proxy': proxy_manager.config.get_proxy_url() if proxy_manager and proxy_manager.config.enabled else None
            },
            'douban': {
                'enabled': True,
                'cookie': settings.douban_cookie,
                'priority': 2,
                'timeout': 30,
                'retry_count': 3,
                'proxy': proxy_manager.config.get_proxy_url() if proxy_manager and proxy_manager.config.enabled else None
            },
            'bangumi': {
                'enabled': bool(settings.bangumi_api_key),
                'api_key': settings.bangumi_api_key,
                'priority': 3,
                'timeout': 30,
                'retry_count': 3,
                'proxy': proxy_manager.config.get_proxy_url() if proxy_manager and proxy_manager.config.enabled else None
            },
            'imdb': {
                'enabled': bool(settings.imdb_cookie),
                'cookie': settings.imdb_cookie,
                'priority': 4,
                'timeout': 30,
                'retry_count': 3,
                'proxy': proxy_manager.config.get_proxy_url() if proxy_manager and proxy_manager.config.enabled else None
            },
            'tvdb': {
                'enabled': bool(settings.tvdb_api_key),
                'api_key': settings.tvdb_api_key,
                'priority': 5,
                'timeout': 30,
                'retry_count': 3,
                'proxy': proxy_manager.config.get_proxy_url() if proxy_manager and proxy_manager.config.enabled else None
            }
        }
        
        self.scraper_manager = ScraperManager({'scrapers': scraper_configs})
        
    async def create_task(self, name: str, source_path: str, destination_path: str, 
                         organize_strategy: str = "category") -> int:
        """创建新任务"""
        db = next(get_db())
        try:
            # 检查路径是否存在
            if not os.path.exists(source_path):
                raise ValueError(f"源路径不存在: {source_path}")
            
            # 创建目标目录
            os.makedirs(destination_path, exist_ok=True)
            
            # 创建任务记录
            task = Task(
                name=name,
                source_path=source_path,
                destination_path=destination_path,
                organize_strategy=organize_strategy,
                status="pending"
            )
            
            db.add(task)
            db.commit()
            db.refresh(task)
            
            logger.info(f"创建任务成功: {name} (ID: {task.id})")
            return task.id
            
        except Exception as e:
            db.rollback()
            logger.error(f"创建任务失败: {e}")
            raise
        finally:
            db.close()
    
    async def start_task(self, task_id: int) -> bool:
        """启动任务"""
        db = next(get_db())
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            if task.status in ["running", "completed"]:
                logger.warning(f"任务状态不允许启动: {task.status}")
                return False
            
            # 更新任务状态
            task.status = "running"
            task.started_at = datetime.now()
            db.commit()
            
            # 启动任务工作器
            task_worker = TaskWorker(task, self)
            self.task_workers[task_id] = task_worker
            
            # 异步执行任务
            asyncio.create_task(task_worker.execute())
            
            logger.info(f"启动任务成功: {task.name} (ID: {task_id})")
            
            # 发送任务开始通知
            await notification_manager.notify(
                title=f"任务开始: {task.name}",
                message=f"任务ID: {task_id}\n源路径: {task.source_path}\n目标路径: {task.destination_path}\n整理策略: {task.organize_strategy}",
                event_type=NotificationEvents.TASK_STARTED
            )
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"启动任务失败: {e}")
            return False
        finally:
            db.close()
    
    async def pause_task(self, task_id: int) -> bool:
        """暂停任务"""
        db = next(get_db())
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            if task.status != "running":
                logger.warning(f"任务状态不允许暂停: {task.status}")
                return False
            
            # 更新任务状态
            task.status = "paused"
            db.commit()
            
            # 停止任务工作器
            if task_id in self.task_workers:
                self.task_workers[task_id].stop()
                del self.task_workers[task_id]
            
            logger.info(f"暂停任务成功: {task.name} (ID: {task_id})")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"暂停任务失败: {e}")
            return False
        finally:
            db.close()
    
    async def cancel_task(self, task_id: int) -> bool:
        """取消任务"""
        db = next(get_db())
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            # 更新任务状态
            task.status = "cancelled"
            db.commit()
            
            # 停止任务工作器
            if task_id in self.task_workers:
                self.task_workers[task_id].stop()
                del self.task_workers[task_id]
            
            logger.info(f"取消任务成功: {task.name} (ID: {task_id})")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"取消任务失败: {e}")
            return False
        finally:
            db.close()
    
    async def retry_failed_files(self, task_id: int) -> int:
        """重试失败的文件"""
        db = next(get_db())
        try:
            # 查找失败的文件记录
            failed_files = db.query(FileRecord).filter(
                FileRecord.task_id == task_id,
                FileRecord.status == "failed",
                FileRecord.retry_count < settings.retry_count
            ).all()
            
            retry_count = 0
            for file_record in failed_files:
                # 重置状态
                file_record.status = "pending"
                file_record.retry_count += 1
                file_record.error_message = None
                retry_count += 1
            
            db.commit()
            
            if retry_count > 0:
                # 重新启动任务来处理重试的文件
                await self.start_task(task_id)
            
            logger.info(f"重试失败的文件: {retry_count}个 (任务ID: {task_id})")
            return retry_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"重试失败文件失败: {e}")
            return 0
        finally:
            db.close()

class TaskWorker:
    """任务工作器"""
    
    def __init__(self, task, task_manager):
        self.task = task
        self.task_manager = task_manager
        self.running = False
        self.processed_count = 0
        self.failed_count = 0
        
    def stop(self):
        """停止工作"""
        self.running = False
    
    async def execute(self):
        """执行任务"""
        self.running = True
        db = next(get_db())
        
        try:
            logger.info(f"开始执行任务: {self.task.name}")
            
            # 扫描源目录
            strm_files = self._scan_strm_files(self.task.source_path)
            total_files = len(strm_files)
            
            # 更新任务统计
            self.task.total_files = total_files
            db.commit()
            
            logger.info(f"发现STRM文件: {total_files}个")
            
            # 处理每个文件
            for i, strm_file in enumerate(strm_files):
                if not self.running:
                    logger.info(f"任务被停止: {self.task.name}")
                    break
                
                try:
                    await self._process_strm_file(strm_file, db)
                    self.processed_count += 1
                    
                    # 更新进度
                    progress = (i + 1) / total_files * 100
                    self.task.progress = progress
                    self.task.processed_files = self.processed_count
                    self.task.failed_files = self.failed_count
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"处理文件失败 {strm_file}: {e}")
                    self.failed_count += 1
                    
                    # 创建失败的文件记录
                    file_record = FileRecord(
                        task_id=self.task.id,
                        source_path=strm_file,
                        file_name=os.path.basename(strm_file),
                        status="failed",
                        error_message=str(e)
                    )
                    db.add(file_record)
                    db.commit()
                    
                    # 发送文件处理失败通知
                    await notification_manager.notify(
                        title=f"文件处理失败: {os.path.basename(strm_file)}",
                        message=f"文件路径: {strm_file}\n错误信息: {str(e)}\n任务ID: {self.task.id}",
                        event_type=NotificationEvents.FILE_FAILED
                    )
            
            # 更新任务状态
            if self.running:
                self.task.status = "completed"
                self.task.completed_at = datetime.now()
                self.task.progress = 100.0
                
                # 发送任务完成通知
                await notification_manager.notify(
                    title=f"任务完成: {self.task.name}",
                    message=f"任务ID: {self.task.id}\n处理文件数: {self.processed_count}\n失败文件数: {self.failed_count}\n耗时: {datetime.now() - self.task.started_at}",
                    event_type=NotificationEvents.TASK_COMPLETED
                )
            else:
                self.task.status = "paused"
            
            db.commit()
            
            logger.info(f"任务执行完成: {self.task.name}")
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            self.task.status = "failed"
            self.task.error_message = str(e)
            db.commit()
            
            # 发送任务失败通知
            await notification_manager.notify(
                title=f"任务失败: {self.task.name}",
                message=f"任务ID: {self.task.id}\n错误信息: {str(e)}\n已处理文件数: {self.processed_count}",
                event_type=NotificationEvents.TASK_FAILED
            )
            
        finally:
            db.close()
            self.running = False
    
    def _scan_strm_files(self, source_path: str) -> list:
        """扫描STRM文件"""
        strm_files = []
        
        for root, dirs, files in os.walk(source_path):
            for file in files:
                if file.lower().endswith('.strm'):
                    strm_files.append(os.path.join(root, file))
        
        return strm_files
    
    async def _process_strm_file(self, strm_file: str, db):
        """处理单个STRM文件"""
        logger.info(f"处理STRM文件: {strm_file}")
        
        # 读取STRM文件内容
        with open(strm_file, 'r', encoding='utf-8') as f:
            media_url = f.read().strip()
        
        if not media_url:
            raise ValueError("STRM文件为空")
        
        # 从文件名提取媒体信息
        file_name = os.path.basename(strm_file)
        media_info = self._extract_media_info(file_name)
        
        # 刮削元数据
        if not self.task_manager.scraper_manager:
            raise ValueError("刮削器管理器未初始化")
            
        scraped_data = await self.task_manager.scraper_manager.scrape_media(
            media_info['title'],
            media_info.get('year'),
            media_info.get('type', 'movie')
        )
        
        if not scraped_data:
            raise ValueError("无法刮削媒体信息")
        
        # 组织文件
        destination_path = self._organize_file(strm_file, scraped_data)
        
        # 创建文件记录
        file_record = FileRecord(
            task_id=self.task.id,
            source_path=strm_file,
            destination_path=destination_path,
            file_name=file_name,
            status="completed",
            scraped_data=json.dumps(scraped_data, ensure_ascii=False)
        )
        db.add(file_record)
        
        logger.info(f"STRM文件处理完成: {strm_file} -> {destination_path}")
        
        # 发送文件处理成功通知
        await notification_manager.notify(
            title=f"文件处理成功: {os.path.basename(strm_file)}",
            message=f"原路径: {strm_file}\n目标路径: {destination_path}\n媒体标题: {scraped_data.get('title')}\n年份: {scraped_data.get('year')}",
            event_type=NotificationEvents.FILE_PROCESSED
        )
    
    def _extract_media_info(self, file_name: str) -> dict:
        """从文件名提取媒体信息"""
        # 移除扩展名
        name_without_ext = os.path.splitext(file_name)[0]
        
        # 简单的正则表达式匹配
        patterns = [
            r'^(?P<title>.+?)\s*\((?P<year>\d{4})\)',  # 标题 (年份)
            r'^(?P<title>.+?)\s*(?P<year>\d{4})',      # 标题 年份
            r'^(?P<title>.+?)$',                        # 只有标题
        ]
        
        for pattern in patterns:
            match = re.match(pattern, name_without_ext, re.IGNORECASE)
            if match:
                info = match.groupdict()
                info['type'] = 'movie'  # 默认为电影
                return info
        
        # 默认返回
        return {
            'title': name_without_ext,
            'type': 'movie'
        }
    
    def _organize_file(self, source_file: str, scraped_data: dict) -> str:
        """组织文件"""
        if self.task.organize_strategy == "none":
            # 不整理，直接复制
            dest_file = os.path.join(
                self.task.destination_path,
                os.path.basename(source_file)
            )
        else:
            # 根据刮削数据创建目录结构
            title = scraped_data.get('title', 'Unknown')
            year = scraped_data.get('year', '')
            media_type = scraped_data.get('type', 'movie')
            
            # 构建基本目录路径
            if self.task.organize_strategy == "category":
                # 分类别整理
                category = self._get_category(media_type)
                base_dir = os.path.join(self.task.destination_path, category)
            else:
                # 分类型整理
                base_dir = os.path.join(self.task.destination_path, media_type)
            
            # 添加二级分类（如果启用）
            dest_dir = base_dir
            if settings.enable_subcategory:
                subcategory = self._get_subcategory(scraped_data, media_type)
                if subcategory:
                    dest_dir = os.path.join(base_dir, subcategory)
            
            # 添加标题和年份目录
            dest_dir = os.path.join(dest_dir, f"{title} ({year})")
            
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = os.path.join(dest_dir, os.path.basename(source_file))
        
        # 复制文件
        shutil.copy2(source_file, dest_file)
        
        return dest_file
    
    def _get_subcategory(self, scraped_data: dict, media_type: str) -> str:
        """获取二级分类"""
        # 从刮削数据中获取 genres 或 categories
        genres = scraped_data.get('genres', [])
        
        # 检查是否在配置的二级分类映射中
        if media_type in settings.subcategory_map:
            subcategory_map = settings.subcategory_map[media_type]
            # 尝试匹配第一个有效的分类
            for genre in genres:
                for key, value in subcategory_map.items():
                    if genre.lower() == key.lower() or genre.lower() == value.lower():
                        return value
        
        # 默认返回通用二级分类
        default_subcategories = {
            'movie': '其他',
            'tv': '其他'
        }
        return default_subcategories.get(media_type, '其他')
    
    def _get_category(self, media_type: str) -> str:
        """获取分类"""
        categories = {
            'movie': 'Movies',
            'tv': 'TV Shows',
            'anime': 'Anime'
        }
        return categories.get(media_type, 'Others')

# 全局任务管理器实例
task_manager = TaskManager()