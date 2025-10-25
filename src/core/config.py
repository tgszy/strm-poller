from pydantic_settings import BaseSettings
from typing import Optional, List, Dict
import os
import json
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 35455  # 默认端口35455，与配置文件和Docker保持一致
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

    def load_config_from_file(self):
        """加载配置文件，支持YAML格式"""
        # 尝试多种配置文件格式
        config_files = [
            os.path.join(self.config_path, "config.yaml"),
            os.path.join(self.config_path, "config.yml"),
            os.path.join(self.config_path, "config.json")  # 处理错误提示中的JSON文件
        ]
        
        for config_file in config_files:
            logger.info(f"尝试加载配置文件: {config_file}")
            if os.path.exists(config_file):
                try:
                    if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                        # 尝试导入PyYAML
                        try:
                            import yaml
                            with open(config_file, 'r', encoding='utf-8') as f:
                                config_data = yaml.safe_load(f)
                            logger.info(f"成功加载YAML配置文件: {config_file}")
                            return config_data
                        except ImportError:
                            logger.warning("PyYAML未安装，无法加载YAML配置")
                    elif config_file.endswith('.json'):
                        # 即使使用JSON文件，也尝试优雅处理
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                        logger.info(f"成功加载JSON配置文件: {config_file}")
                        return config_data
                except Exception as e:
                    logger.error(f"加载配置文件 {config_file} 失败: {str(e)}")
            else:
                logger.info(f"配置文件不存在: {config_file}")
        
        # 如果没有找到配置文件，创建默认配置文件
        self._create_default_config()
        return None
    
    def _create_default_config(self):
        """创建默认配置文件"""
        default_config_path = os.path.join(self.config_path, "config.yaml")
        try:
            # 确保配置目录存在
            os.makedirs(self.config_path, exist_ok=True)
            
            # 生成默认配置内容
            default_config = """
# STRM Poller 默认配置文件
server:
  host: "0.0.0.0"
  port: 35455
  debug: false

paths:
  config_path: "%(config_path)s"
  src_path: "%(src_path)s"
  dst_path: "%(dst_path)s"

# 数据库配置
database:
  sqlite_path: "%(sqlite_path)s"

# 日志配置
logging:
  level: "INFO"
  file: "%(log_file)s"
            """
            
            # 填充路径变量
            default_config = default_config % {
                'config_path': self.config_path,
                'src_path': self.src_path,
                'dst_path': self.dst_path,
                'sqlite_path': self.sqlite_path,
                'log_file': self.log_file
            }
            
            # 写入默认配置文件
            with open(default_config_path, 'w', encoding='utf-8') as f:
                f.write(default_config.strip())
            
            logger.info(f"已创建默认配置文件: {default_config_path}")
            
            # 同时创建一个空的config.json文件以避免错误
            empty_json_path = os.path.join(self.config_path, "config.json")
            with open(empty_json_path, 'w', encoding='utf-8') as f:
                f.write("{}\n")
            logger.info(f"已创建空的config.json文件: {empty_json_path}")
            
        except Exception as e:
            logger.error(f"创建默认配置文件失败: {str(e)}")
    
    def __init__(self, **kwargs):
        try:
            super().__init__(**kwargs)
            # 确保路径使用正确的分隔符，支持Windows和Linux环境下的路径处理
            self.config_path = os.path.normpath(self.config_path)
            self.src_path = os.path.normpath(self.src_path)
            self.dst_path = os.path.normpath(self.dst_path)
            
            logger.info(f"配置路径设置: config_path={self.config_path}, src_path={self.src_path}, dst_path={self.dst_path}")
            
            # 更新依赖于config_path的路径，确保路径正确拼接
            self.sqlite_path = os.path.join(self.config_path, "strm-poller.db")
            logger.info(f"SQLite数据库路径: {self.sqlite_path}")
            
            # 确保日志目录存在，自动创建必要的目录结构
            try:
                log_dir = os.path.join(self.config_path, "logs")
                os.makedirs(log_dir, exist_ok=True)
                self.log_file = os.path.join(log_dir, "strm-poller.log")
                logger.info(f"日志文件路径: {self.log_file}")
            except Exception as e:
                logger.error(f"创建日志目录失败: {str(e)}")
                # 回退到临时目录
                self.log_file = "/tmp/strm-poller.log"
                logger.warning(f"回退到临时日志文件: {self.log_file}")
            
            # 检查配置目录权限
            if not os.access(self.config_path, os.W_OK):
                logger.warning(f"配置目录 {self.config_path} 无写权限")
            
            # 加载配置文件（如果存在）
            config_data = self.load_config_from_file()
            if config_data:
                # 可以在这里处理加载的配置数据
                logger.info("配置文件已加载")
                
        except Exception as e:
            logger.error(f"初始化配置时出错: {str(e)}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            # 使用默认值继续运行
            self.host = "0.0.0.0"
            self.port = 35455
            self.config_path = os.environ.get("CONFIG_PATH", "/config")
            self.src_path = os.environ.get("SRC_PATH", "/src")
            self.dst_path = os.environ.get("DST_PATH", "/dst")
            self.sqlite_path = os.path.join(self.config_path, "strm-poller.db")
            self.log_file = os.path.join(self.config_path, "strm-poller.log")

# 全局设置实例
settings = Settings()