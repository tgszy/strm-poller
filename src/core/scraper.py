from typing import Optional, Dict, Any, List
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import json
import re
from .logger import logger
from .config import settings

class BaseScraper:
    """基础刮削器"""
    
    def __init__(self, name: str, api_key: Optional[str] = None, cookie: Optional[str] = None):
        self.name = name
        self.api_key = api_key
        self.cookie = cookie
        self.session = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=30)
        
        # 配置代理
        if settings.proxy_enabled and settings.proxy_url:
            if settings.proxy_url.startswith('socks5'):
                # 需要安装aiohttp-socks
                try:
                    from aiohttp_socks import ProxyConnector
                    connector = ProxyConnector.from_url(settings.proxy_url)
                except ImportError:
                    logger.warning("SOCKS5 proxy requires aiohttp-socks package")
            else:
                # HTTP/HTTPS代理
                proxy_auth = None
                proxy = settings.proxy_url
                
                # 提取认证信息
                if '@' in proxy and proxy.startswith(('http://', 'https://')):
                    proxy_parts = proxy.replace('http://', '').replace('https://', '').split('@')
                    if len(proxy_parts) == 2:
                        auth_part, host_part = proxy_parts
                        if ':' in auth_part:
                            username, password = auth_part.split(':', 1)
                            proxy_auth = aiohttp.BasicAuth(username, password)
                            proxy = f"http://{host_part}"
                
                # 创建会话时直接传入代理配置
                self.session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    trust_env=True,
                    connector_owner=False  # 让session负责关闭connector
                )
                # 标准方式设置代理
                self.session._default_proxy = proxy
                if proxy_auth:
                    self.session._proxy_auth = proxy_auth
        else:
            self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def search(self, title: str, year: Optional[int] = None, media_type: str = "movie") -> Optional[Dict[str, Any]]:
        """搜索媒体信息"""
        raise NotImplementedError
    
    async def get_details(self, media_id: str) -> Optional[Dict[str, Any]]:
        """获取详细信息"""
        raise NotImplementedError
    
    async def get_poster(self, media_id: str) -> Optional[bytes]:
        """获取海报图片"""
        raise NotImplementedError
    
    async def get_fanart(self, media_id: str) -> Optional[bytes]:
        """获取同人画"""
        raise NotImplementedError

class TMDBScraper(BaseScraper):
    """TMDB刮削器"""
    
    def __init__(self, api_key: str):
        super().__init__("tmdb", api_key)
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p"
    
    async def search(self, title: str, year: Optional[int] = None, media_type: str = "movie") -> Optional[Dict[str, Any]]:
        """搜索TMDB"""
        if not self.api_key:
            return None
            
        search_type = "movie" if media_type == "movie" else "tv"
        url = f"{self.base_url}/search/{search_type}"
        params = {
            "api_key": self.api_key,
            "query": title,
            "language": settings.tmdb_language,
            "page": 1
        }
        
        if year:
            if search_type == "movie":
                params["year"] = year
            else:
                params["first_air_date_year"] = year
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("results"):
                        return {
                            "id": data["results"][0]["id"],
                            "title": data["results"][0].get("title") or data["results"][0].get("name"),
                            "year": year,
                            "type": search_type,
                            "poster_path": data["results"][0].get("poster_path"),
                            "overview": data["results"][0].get("overview")
                        }
        except Exception as e:
            logger.error(f"TMDB搜索失败: {e}")
        
        return None
    
    async def get_details(self, media_id: str) -> Optional[Dict[str, Any]]:
        """获取TMDB详细信息"""
        if not self.api_key:
            return None
            
        url = f"{self.base_url}/movie/{media_id}"
        params = {
            "api_key": self.api_key,
            "language": settings.tmdb_language,
            "append_to_response": "credits,keywords,images"
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.error(f"TMDB获取详情失败: {e}")
        
        return None
    
    async def get_poster(self, media_id: str) -> Optional[bytes]:
        """获取海报"""
        details = await self.get_details(media_id)
        if details and details.get("poster_path"):
            poster_url = f"{self.image_base_url}/w500{details['poster_path']}"
            try:
                async with self.session.get(poster_url) as response:
                    if response.status == 200:
                        return await response.read()
            except Exception as e:
                logger.error(f"TMDB获取海报失败: {e}")
        
        return None

class DoubanScraper(BaseScraper):
    """豆瓣刮削器"""
    
    def __init__(self, cookie: Optional[str] = None):
        super().__init__("douban", cookie=cookie)
        self.base_url = "https://movie.douban.com"
        self.search_url = "https://www.douban.com/search"
    
    async def search(self, title: str, year: Optional[int] = None, media_type: str = "movie") -> Optional[Dict[str, Any]]:
        """搜索豆瓣"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        if self.cookie:
            headers["Cookie"] = self.cookie
        
        params = {
            "q": title,
            "cat": "1002"  # 电影
        }
        
        try:
            async with self.session.get(self.search_url, params=params, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    # 这里需要实现豆瓣HTML解析逻辑
                    # 简化版实现
                    return self._parse_douban_search(html, title, year)
        except Exception as e:
            logger.error(f"豆瓣搜索失败: {e}")
        
        return None
    
    def _parse_douban_search(self, html: str, title: str, year: Optional[int]) -> Optional[Dict[str, Any]]:
        """解析豆瓣搜索结果"""
        soup = BeautifulSoup(html, 'html.parser')
        # 这里需要实现具体的HTML解析逻辑
        # 简化版返回
        return None

class ScraperManager:
    """刮削器管理器"""
    
    def __init__(self):
        self.scrapers = {}
        self._init_scrapers()
    
    def _init_scrapers(self):
        """初始化刮削器"""
        # TMDB
        if settings.tmdb_api_key:
            self.scrapers["tmdb"] = TMDBScraper(settings.tmdb_api_key)
        
        # 豆瓣
        self.scrapers["douban"] = DoubanScraper(settings.douban_cookie)
        
        # 其他刮削器...
    
    async def scrape_media(self, title: str, year: Optional[int] = None, media_type: str = "movie") -> Optional[Dict[str, Any]]:
        """刮削媒体信息"""
        for scraper_name in settings.scraper_order:
            if scraper_name not in self.scrapers:
                continue
                
            scraper = self.scrapers[scraper_name]
            try:
                async with scraper:
                    result = await scraper.search(title, year, media_type)
                    if result:
                        logger.info(f"使用{scraper_name}成功刮削: {title}")
                        return result
            except Exception as e:
                logger.error(f"{scraper_name}刮削失败: {e}")
                continue
        
        logger.warning(f"所有刮削源都失败: {title}")
        return None

# 全局刮削器管理器实例
scraper_manager = ScraperManager()