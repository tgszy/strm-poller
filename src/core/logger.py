import logging
import logging.handlers
import os
import sys
from pathlib import Path
from .config import settings

def setup_logging():
    """设置日志系统"""
    # 创建日志目录
    log_dir = Path(settings.log_file).parent
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"创建日志目录失败: {e}")
        # 回退到临时目录
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "strm-poller"
        temp_dir.mkdir(parents=True, exist_ok=True)
        settings.log_file = str(temp_dir / "strm-poller.log")
    
    # 创建logger
    logger = logging.getLogger("strm-poller")
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # 清除现有的handler
    logger.handlers.clear()
    
    # 创建formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 文件handler（轮转日志）
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_file,
            maxBytes=settings.log_max_size,
            backupCount=settings.log_backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"创建文件日志处理器失败: {e}")
        # 回退到基础文件处理器
        try:
            file_handler = logging.FileHandler(settings.log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e2:
            print(f"创建基础文件日志处理器也失败: {e2}")
    
    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# 全局logger实例
logger = setup_logging()