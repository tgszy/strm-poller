import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.database import SessionLocal, ScraperConfig, init_db

def add_fmart_scraper():
    # 初始化数据库表
    init_db()
    
    # 创建数据库会话
    db = SessionLocal()
    
    try:
        # 检查fmart是否已存在
        existing = db.query(ScraperConfig).filter(ScraperConfig.name == 'fmart').first()
        
        if existing:
            print("FMart刮削源已存在于数据库中")
        else:
            # 创建新的FMart刮削源配置
            fmart_scraper = ScraperConfig(
                name='fmart',
                enabled=True,
                api_key=None,
                cookie='',  # 用户需要自行配置
                api_url='https://www.fmart.net',
                priority=5,
                timeout=30,
                retry_count=3
            )
            
            # 添加到数据库
            db.add(fmart_scraper)
            db.commit()
            print("FMart刮削源已成功添加到数据库")
            
    except Exception as e:
        print(f"添加FMart刮削源时出错: {e}")
        db.rollback()
    finally:
        # 关闭数据库会话
        db.close()

if __name__ == "__main__":
    add_fmart_scraper()
    print("请重新启动应用以应用更改")