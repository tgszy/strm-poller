"""
默认刮削源配置初始化脚本
"""
from .database import SessionLocal, ScraperConfig
from datetime import datetime

def init_default_scrapers():
    """初始化默认刮削源配置"""
    db = SessionLocal()
    
    try:
        # 检查是否已有刮削源配置
        existing_scrapers = db.query(ScraperConfig).all()
        if existing_scrapers:
            print("数据库中已有刮削源配置，跳过初始化")
            return
            
        # 默认刮削源配置
        default_scrapers = [
            {
                'name': 'tmdb',
                'enabled': True,
                'api_key': '',  # 用户需要自行配置
                'cookie': None,
                'api_url': 'https://api.tmdb.org',  # 默认API地址
                'priority': 0,
                'timeout': 30,
                'retry_count': 3
            },
            {
                'name': 'douban',
                'enabled': True,
                'api_key': None,
                'cookie': '',  # 用户需要自行配置
                'api_url': 'https://api.douban.com',  # 默认API地址
                'priority': 1,
                'timeout': 30,
                'retry_count': 3
            },
            {
                'name': 'bangumi',
                'enabled': True,
                'api_key': None,
                'cookie': '',  # 用户需要自行配置
                'api_url': 'https://api.bgm.tv',  # 默认API地址
                'priority': 2,
                'timeout': 30,
                'retry_count': 3
            },
            {
                'name': 'imdb',
                'enabled': True,
                'api_key': None,
                'cookie': '',  # 用户需要自行配置
                'api_url': 'https://imdb-api.com',  # 默认API地址
                'priority': 3,
                'timeout': 30,
                'retry_count': 3
            },
            {
                'name': 'tvdb',
                'enabled': True,
                'api_key': '',  # 用户需要自行配置
                'cookie': None,
                'api_url': 'https://api.thetvdb.com',  # 默认API地址
                'priority': 4,
                'timeout': 30,
                'retry_count': 3
            }
        ]
        
        # 添加默认刮削源配置
        for scraper_data in default_scrapers:
            scraper = ScraperConfig(
                name=scraper_data['name'],
                enabled=scraper_data['enabled'],
                api_key=scraper_data['api_key'],
                cookie=scraper_data['cookie'],
                priority=scraper_data['priority'],
                timeout=scraper_data['timeout'],
                retry_count=scraper_data['retry_count'],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(scraper)
        
        db.commit()
        print("成功初始化默认刮削源配置")
        
    except Exception as e:
        db.rollback()
        print(f"初始化默认刮削源配置失败: {e}")
        
    finally:
        db.close()

if __name__ == "__main__":
    init_default_scrapers()