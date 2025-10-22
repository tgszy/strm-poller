from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from .config import settings

Base = declarative_base()

class Task(Base):
    """任务表"""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    source_path = Column(String(500), nullable=False)
    destination_path = Column(String(500), nullable=False)
    organize_strategy = Column(String(50), default="category")  # category, type, none
    status = Column(String(50), default="pending")  # pending, running, paused, completed, failed
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress = Column(Float, default=0.0)
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

class FileRecord(Base):
    """文件处理记录表"""
    __tablename__ = "file_records"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, index=True)
    source_path = Column(String(500), nullable=False)
    destination_path = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, default=0)
    file_hash = Column(String(64), nullable=True)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    scraped_data = Column(Text, nullable=True)  # JSON格式的刮削数据
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    processed_at = Column(DateTime, nullable=True)

class ScraperConfig(Base):
    """刮削源配置表"""
    __tablename__ = "scraper_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)  # tmdb, douban, bangumi, imdb, tvdb
    enabled = Column(Boolean, default=True)
    api_key = Column(String(255), nullable=True)
    cookie = Column(Text, nullable=True)
    priority = Column(Integer, default=0)
    timeout = Column(Integer, default=30)
    retry_count = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

# 创建数据库引擎
engine = create_engine(settings.database_url, echo=False)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()