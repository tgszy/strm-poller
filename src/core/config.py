from pydantic import BaseSettings
from typing import Optional, List, Dict
import os

class Settings(BaseSettings):
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 3456
    debug: bool = False
    
    # 路径配置 - 支持从环境变量读取，增加灵活性
    config_path: str = os.environ.get("CONFIG_PATH", "/config")
    src_path: str = os.environ.get("SRC_PATH", "/src")
    dst_path: str = os.environ.get("DST_PATH", "/dst")
    
    # 代理配置
    proxy_enabled: bool = False
    proxy_type: str = "http"  # http, https, socks5
    proxy_host: str = "localhost"
    proxy_port: int = 8080
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    proxy_url: Optional[str] = None  # http://user:pass@host:port 或 socks5://host:port
    proxy_test_url: str = "https://api.themoviedb.org/3/configuration"
    
    # 刮削源配置
    scraper_order: List[str] = ["tmdb", "douban", "bangumi", "imdb", "tvdb"]
    
    # TMDB配置
    tmdb_api_key: Optional[str] = None
    tmdb_language: str = "zh-CN"
    
    # 豆瓣配置
    douban_cookie: Optional[str] = None
    
    # Bangumi配置
    bangumi_api_key: Optional[str] = None
    
    # IMDb配置
    imdb_cookie: Optional[str] = None
    
    # TVDB配置
    tvdb_api_key: Optional[str] = None
    
    # 系统配置
    max_memory_mb: int = int(os.environ.get("MAX_MEMORY", "1024"))  # 内存限制，单位MB
    max_workers: int = 4  # 最大工作线程数
    task_timeout: int = 3600  # 任务超时时间，单位秒
    retry_count: int = 3  # 重试次数
    retry_delay: int = 3600  # 重试延迟，单位秒
    
    # 文件监控配置
    watch_debounce_seconds: float = float(os.environ.get("WATCH_DEBOUNCE_SECONDS", "1.0"))  # 文件事件防抖时间
    watch_recursive: bool = True  # 是否递归监控
    
    # 整理策略
    organize_strategy: str = "category"  # category, type, none
    rename_template: str = "{title} ({year}){extension}"
    # 二级分类配置
    enable_subcategory: bool = True
    subcategory_map: Dict[str, Dict[str, str]] = {
        "movie": {
            "Action": "动作",
            "Comedy": "喜剧",
            "Drama": "剧情",
            "Horror": "恐怖",
            "Sci-Fi": "科幻",
            "Fantasy": "奇幻",
            "Romance": "爱情"
        },
        "tv": {
            "Series": "剧集",
            "Anime": "动画",
            "Documentary": "纪录片",
            "Reality": "真人秀"
        }
    }
    
    # 通知配置
    # 微信企业机器人配置
    notify_wechat_enabled: bool = False
    notify_wechat_webhook_url: Optional[str] = None
    notify_wechat_events: List[str] = []
    
    # Telegram配置
    notify_telegram_enabled: bool = False
    notify_telegram_bot_token: Optional[str] = None
    notify_telegram_chat_id: Optional[str] = None
    notify_telegram_events: List[str] = []
    
    # 数据库配置
    # SQLite配置 - 默认值，将在__init__中根据config_path更新
    sqlite_path: str = "/config/strm-poller.db"
    
    # PostgreSQL配置
    postgres_enabled: bool = False
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "strm-poller"
    postgres_password: str = "password"
    postgres_dbname: str = "strm-poller"
    
    @property
    def database_url(self) -> str:
        """获取数据库URL"""
        if self.postgres_enabled:
            return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_dbname}"
        else:
            return f"sqlite:///{self.sqlite_path}"
    
    # 日志配置
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    log_file: str = "/config/logs/strm-poller.log"  # 默认值，将在__init__中更新
    log_max_size: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5
    
    # 用户配置
    puid: int = int(os.environ.get("PUID", "1000"))
    pgid: int = int(os.environ.get("PGID", "1000"))
    timezone: str = os.environ.get("TZ", "Asia/Shanghai")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保路径使用正确的分隔符，支持Windows和Linux环境下的路径处理
        self.config_path = os.path.normpath(self.config_path)
        self.src_path = os.path.normpath(self.src_path)
        self.dst_path = os.path.normpath(self.dst_path)
        
        # 更新依赖于config_path的路径，确保路径正确拼接
        self.sqlite_path = os.path.join(self.config_path, "strm-poller.db")
        
        # 确保日志目录存在，自动创建必要的目录结构
        log_dir = os.path.join(self.config_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "strm-poller.log")

# 全局设置实例
settings = Settings()