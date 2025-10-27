import asyncio
import aiohttp
import json
import re
import time
from typing import Dict, Optional, List, Any
from urllib.parse import urljoin, quote
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BaseScraper:
    """基础刮削器类"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.priority = config.get('priority', 0)
        self.timeout = config.get('timeout', 30)
        self.retry_count = config.get('retry_count', 3)
        self.proxy = config.get('proxy')
        self.session = None
        
    async def __aenter__(self):
        await self.init_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()
        
    async def init_session(self):
        """初始化HTTP会话"""
        connector = None
        if self.proxy:
            if self.proxy.startswith('socks5://'):
                # 需要安装aiohttp-socks
                try:
                    from aiohttp_socks import ProxyConnector
                    connector = ProxyConnector.from_url(self.proxy)
                except ImportError:
                    logger.warning(f"{self.name}: SOCKS5代理需要安装aiohttp-socks包")
            else:
                # HTTP/HTTPS代理
                connector = aiohttp.TCPConnector(ssl=False)
                
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'STRM-Poller/3.0'}
        )
        
    async def close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            
    async def scrape(self, media_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """刮削媒体信息"""
        if not self.enabled:
            return None
            
        for attempt in range(self.retry_count + 1):
            try:
                result = await self._scrape_impl(media_info)
                if result:
                    logger.info(f"{self.name}: 成功刮削 {media_info.get('title', 'Unknown')}")
                    return result
            except Exception as e:
                logger.warning(f"{self.name}: 刮削失败 (尝试 {attempt + 1}/{self.retry_count + 1}): {e}")
                if attempt < self.retry_count:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    
        logger.error(f"{self.name}: 刮削失败 {media_info.get('title', 'Unknown')}")
        return None
        
    async def _scrape_impl(self, media_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """具体刮削实现，子类必须重写"""
        raise NotImplementedError
        
    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            await self.init_session()
            result = await self._test_connection_impl()
            return result
        except Exception as e:
            logger.error(f"{self.name}: 连接测试失败: {e}")
            return False
        finally:
            await self.close_session()
            
    async def _test_connection_impl(self) -> bool:
        """连接测试实现，子类必须重写"""
        raise NotImplementedError

class TMDBScraper(BaseScraper):
    """TMDB刮削器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__('tmdb', config)
        self.api_key = config.get('api_key')
        self.base_url = 'https://api.themoviedb.org/3'
        self.image_base_url = 'https://image.tmdb.org/t/p/w500'
        self.language = config.get('language', 'zh-CN')
        
    async def _scrape_impl(self, media_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("TMDB: API密钥未配置")
            return None
            
        title = media_info.get('title')
        year = media_info.get('year')
        media_type = media_info.get('type', 'movie')  # movie or tv
        
        # 搜索媒体
        search_url = f"{self.base_url}/search/{media_type}"
        params = {
            'api_key': self.api_key,
            'query': title,
            'language': self.language,
            'year': year if year else None
        }
        
        async with self.session.get(search_url, params=params) as response:
            if response.status != 200:
                logger.error(f"TMDB搜索失败: HTTP {response.status}")
                return None
                
            data = await response.json()
            if not data.get('results'):
                logger.warning(f"TMDB: 未找到匹配结果: {title}")
                return None
                
            # 获取第一个结果
            result = data['results'][0]
            tmdb_id = result['id']
            
            # 获取详细信息
            detail_url = f"{self.base_url}/{media_type}/{tmdb_id}"
            detail_params = {
                'api_key': self.api_key,
                'language': self.language,
                'append_to_response': 'credits,keywords,external_ids'
            }
            
            async with self.session.get(detail_url, params=detail_params) as detail_response:
                if detail_response.status != 200:
                    logger.error(f"TMDB获取详情失败: HTTP {detail_response.status}")
                    return None
                    
                detail_data = await detail_response.json()
                
                # 构建返回数据
                scraped_data = {
                    'title': detail_data.get('title') or detail_data.get('name', title),
                    'original_title': detail_data.get('original_title') or detail_data.get('original_name'),
                    'year': year or self._extract_year(detail_data.get('release_date') or detail_data.get('first_air_date')),
                    'overview': detail_data.get('overview', ''),
                    'poster_path': self._get_image_url(detail_data.get('poster_path')),
                    'backdrop_path': self._get_image_url(detail_data.get('backdrop_path')),
                    'genres': [genre['name'] for genre in detail_data.get('genres', [])],
                    'rating': detail_data.get('vote_average', 0),
                    'runtime': detail_data.get('runtime') or detail_data.get('episode_run_time', [0])[0],
                    'cast': [cast['name'] for cast in detail_data.get('credits', {}).get('cast', [])[:5]],
                    'director': [crew['name'] for crew in detail_data.get('credits', {}).get('crew', []) 
                                if crew['job'] == 'Director'][:3],
                    'tmdb_id': tmdb_id,
                    'imdb_id': detail_data.get('external_ids', {}).get('imdb_id'),
                    'source': 'tmdb'
                }
                
                return scraped_data
                
    def _extract_year(self, date_str: str) -> Optional[int]:
        """从日期字符串提取年份"""
        if not date_str:
            return None
        try:
            return int(date_str.split('-')[0])
        except (ValueError, IndexError):
            return None
            
    def _get_image_url(self, path: str) -> Optional[str]:
        """获取图片完整URL"""
        if not path:
            return None
        return f"{self.image_base_url}{path}"
        
    async def _test_connection_impl(self) -> bool:
        """测试TMDB连接"""
        if not self.api_key:
            return False
            
        test_url = f"{self.base_url}/configuration"
        params = {'api_key': self.api_key}
        
        async with self.session.get(test_url, params=params) as response:
            return response.status == 200

class DoubanScraper(BaseScraper):
    """豆瓣刮削器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__('douban', config)
        self.cookie = config.get('cookie', '')
        self.base_url = 'https://api.douban.com/v2'
        self.search_url = 'https://www.douban.com/search'
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
    async def _scrape_impl(self, media_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        title = media_info.get('title')
        year = media_info.get('year')
        
        # 搜索媒体
        search_params = {
            'q': title,
            'cat': '1002'  # 电影
        }
        
        headers = {
            'User-Agent': self.user_agent,
            'Cookie': self.cookie,
            'Referer': 'https://www.douban.com/'
        }
        
        async with self.session.get(self.search_url, params=search_params, headers=headers) as response:
            if response.status != 200:
                logger.error(f"豆瓣搜索失败: HTTP {response.status}")
                return None
                
            html = await response.text()
            
            # 解析搜索结果
            movie_links = re.findall(r'<a[^>]*href="https://movie\.douban\.com/subject/(\d+)/"[^>]*>([^<]+)</a>', html)
            
            if not movie_links:
                logger.warning(f"豆瓣: 未找到匹配结果: {title}")
                return None
                
            # 获取第一个结果的详细信息
            douban_id = movie_links[0][0]
            detail_url = f"https://movie.douban.com/subject/{douban_id}/"
            
            async with self.session.get(detail_url, headers=headers) as detail_response:
                if detail_response.status != 200:
                    logger.error(f"豆瓣获取详情失败: HTTP {detail_response.status}")
                    return None
                    
                detail_html = await detail_response.text()
                
                # 解析电影信息
                scraped_data = self._parse_douban_detail(detail_html, douban_id)
                if scraped_data:
                    scraped_data['title'] = title  # 使用原始标题
                    scraped_data['year'] = year or scraped_data.get('year')
                    scraped_data['source'] = 'douban'
                    
                return scraped_data
                
    def _parse_douban_detail(self, html: str, douban_id: str) -> Optional[Dict[str, Any]]:
        """解析豆瓣详情页"""
        try:
            # 提取基本信息
            title_match = re.search(r'<h1[^>]*>\s*<span[^>]*property="v:itemreviewed"[^>]*>([^<]+)</span>', html)
            title = title_match.group(1) if title_match else ''
            
            year_match = re.search(r'<span[^>]*class="year"[^>]*>\((\d{4})\)</span>', html)
            year = int(year_match.group(1)) if year_match else None
            
            rating_match = re.search(r'<strong[^>]*class="ll rating_num "[^>]*>([^<]+)</strong>', html)
            rating = float(rating_match.group(1)) if rating_match and rating_match.group(1).strip() else 0
            
            # 提取简介
            summary_match = re.search(r'<span[^>]*property="v:summary"[^>]*>([^<]+)</span>', html)
            overview = summary_match.group(1).strip() if summary_match else ''
            
            # 提取海报
            poster_match = re.search(r'<img[^>]*src="([^"]*)"[^>]*alt="[^"]*海报"', html)
            poster_path = poster_match.group(1) if poster_match else ''
            
            # 提取类型
            genres = re.findall(r'<span[^>]*property="v:genre"[^>]*>([^<]+)</span>', html)
            
            # 提取导演和演员
            director_match = re.search(r'<a[^>]*href="/celebrity/[^"]*"[^>]*rel="v:directedBy"[^>]*>([^<]+)</a>', html)
            director = [director_match.group(1)] if director_match else []
            
            cast = re.findall(r'<a[^>]*href="/celebrity/[^"]*"[^>]*rel="v:starring"[^>]*>([^<]+)</a>', html)
            
            return {
                'title': title,
                'year': year,
                'overview': overview,
                'poster_path': poster_path,
                'backdrop_path': None,
                'genres': genres,
                'rating': rating,
                'cast': cast[:5],
                'director': director[:3],
                'douban_id': douban_id,
                'source': 'douban'
            }
            
        except Exception as e:
            logger.error(f"解析豆瓣详情失败: {e}")
            return None
            
    async def _test_connection_impl(self) -> bool:
        """测试豆瓣连接"""
        headers = {
            'User-Agent': self.user_agent,
            'Cookie': self.cookie,
            'Referer': 'https://www.douban.com/'
        }
        
        async with self.session.get('https://www.douban.com/', headers=headers) as response:
            return response.status == 200

class BangumiScraper(BaseScraper):
    """Bangumi刮削器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__('bangumi', config)
        self.api_key = config.get('api_key')
        self.base_url = 'https://api.bgm.tv'
        
    async def _scrape_impl(self, media_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("Bangumi: API密钥未配置")
            return None
            
        title = media_info.get('title')
        
        # 搜索动画
        search_url = f"{self.base_url}/search/subject/{quote(title)}"
        params = {
            'type': 2,  # 动画
            'responseGroup': 'large'
        }
        
        headers = {'User-Agent': 'STRM-Poller/3.0'}
        
        async with self.session.get(search_url, params=params, headers=headers) as response:
            if response.status != 200:
                logger.error(f"Bangumi搜索失败: HTTP {response.status}")
                return None
                
            data = await response.json()
            if not data.get('list'):
                logger.warning(f"Bangumi: 未找到匹配结果: {title}")
                return None
                
            # 获取第一个结果
            result = data['list'][0]
            subject_id = result['id']
            
            # 获取详细信息
            detail_url = f"{self.base_url}/subject/{subject_id}"
            detail_params = {'responseGroup': 'large'}
            
            async with self.session.get(detail_url, params=detail_params, headers=headers) as detail_response:
                if detail_response.status != 200:
                    logger.error(f"Bangumi获取详情失败: HTTP {detail_response.status}")
                    return None
                    
                detail_data = await detail_response.json()
                
                # 构建返回数据
                scraped_data = {
                    'title': detail_data.get('name_cn') or detail_data.get('name', title),
                    'original_title': detail_data.get('name'),
                    'year': self._extract_year(detail_data.get('air_date')),
                    'overview': detail_data.get('summary', ''),
                    'poster_path': detail_data.get('images', {}).get('large'),
                    'backdrop_path': None,
                    'genres': [tag['name'] for tag in detail_data.get('tags', [])[:3]],
                    'rating': detail_data.get('rating', {}).get('score', 0),
                    'cast': [],  # Bangumi API不直接提供演员信息
                    'director': [],
                    'bangumi_id': subject_id,
                    'source': 'bangumi'
                }
                
                return scraped_data
                
    async def _test_connection_impl(self) -> bool:
        """测试Bangumi连接"""
        headers = {'User-Agent': 'STRM-Poller/3.0'}
        
        async with self.session.get(f"{self.base_url}/calendar", headers=headers) as response:
            return response.status == 200

class IMDbScraper(BaseScraper):
    """IMDb刮削器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__('imdb', config)
        self.cookie = config.get('cookie', '')
        self.base_url = 'https://www.imdb.com'
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
    async def _scrape_impl(self, media_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        title = media_info.get('title')
        year = media_info.get('year')
        
        # 搜索媒体
        search_url = f"{self.base_url}/find"
        search_params = {
            'q': title,
            'ref_': 'nv_sr_sm'
        }
        
        headers = {
            'User-Agent': self.user_agent,
            'Cookie': self.cookie,
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        
        async with self.session.get(search_url, params=search_params, headers=headers) as response:
            if response.status != 200:
                logger.error(f"IMDb搜索失败: HTTP {response.status}")
                return None
                
            html = await response.text()
            
            # 提取搜索结果
            imdb_id_match = re.search(r'<a[^>]*href="/title/(tt\d+)/"[^>]*>([^<]+)</a>', html)
            if not imdb_id_match:
                logger.warning(f"IMDb: 未找到匹配结果: {title}")
                return None
                
            imdb_id = imdb_id_match.group(1)
            
            # 获取详细信息
            detail_url = f"{self.base_url}/title/{imdb_id}/"
            
            async with self.session.get(detail_url, headers=headers) as detail_response:
                if detail_response.status != 200:
                    logger.error(f"IMDb获取详情失败: HTTP {detail_response.status}")
                    return None
                    
                detail_html = await detail_response.text()
                
                # 解析IMDb详情页
                scraped_data = self._parse_imdb_detail(detail_html, imdb_id)
                if scraped_data:
                    scraped_data['title'] = title  # 使用原始标题
                    scraped_data['year'] = year or scraped_data.get('year')
                    scraped_data['source'] = 'imdb'
                    
                return scraped_data
                
    def _parse_imdb_detail(self, html: str, imdb_id: str) -> Optional[Dict[str, Any]]:
        """解析IMDb详情页"""
        try:
            # 提取标题
            title_match = re.search(r'<h1[^>]*data-testid="hero-title-block__title"[^>]*>([^<]+)</h1>', html)
            title = title_match.group(1) if title_match else ''
            
            # 提取年份
            year_match = re.search(r'<a[^>]*href="/year/\d{4}/"[^>]*>(\d{4})</a>', html)
            year = int(year_match.group(1)) if year_match else None
            
            # 提取评分
            rating_match = re.search(r'<span[^>]*itemprop="ratingValue"[^>]*>([^<]+)</span>', html)
            rating = float(rating_match.group(1)) if rating_match else 0
            
            # 提取简介
            summary_match = re.search(r'<span[^>]*data-testid="plot-l"[^>]*>([^<]+)</span>', html)
            overview = summary_match.group(1).strip() if summary_match else ''
            
            # 提取海报
            poster_match = re.search(r'<img[^>]*src="([^"]*)"[^>]*alt="[^"]*poster"', html)
            poster_path = poster_match.group(1) if poster_match else ''
            
            # 提取类型
            genres = re.findall(r'<a[^>]*href="/genre/[^"]*"[^>]*>([^<]+)</a>', html)
            
            # 提取导演和演员
            director_match = re.search(r'<a[^>]*href="/name/nm\d+/"[^>]*>([^<]+)</a>', html)
            director = [director_match.group(1)] if director_match else []
            
            cast = re.findall(r'<a[^>]*href="/name/nm\d+/"[^>]*>([^<]+)</a>', html)
            
            return {
                'title': title,
                'year': year,
                'overview': overview,
                'poster_path': poster_path,
                'backdrop_path': None,
                'genres': genres,
                'rating': rating,
                'cast': cast[:5],
                'director': director[:3],
                'imdb_id': imdb_id,
                'source': 'imdb'
            }
            
        except Exception as e:
            logger.error(f"解析IMDb详情失败: {e}")
            return None
            
    async def _test_connection_impl(self) -> bool:
        """测试IMDb连接"""
        headers = {
            'User-Agent': self.user_agent,
            'Cookie': self.cookie
        }
        
        async with self.session.get(self.base_url, headers=headers) as response:
            return response.status == 200

class FMartScraper(BaseScraper):
    """FMart刮削器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__('fmart', config)
        self.api_key = config.get('api_key')
        self.cookie = config.get('cookie', '')
        self.base_url = 'https://www.fmart.net'
        self.search_url = 'https://www.fmart.net/search'
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
    async def _scrape_impl(self, media_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        title = media_info.get('title')
        year = media_info.get('year')
        
        # 搜索媒体
        search_params = {
            'word': title,
            'category': 'all'
        }
        
        headers = {
            'User-Agent': self.user_agent,
            'Cookie': self.cookie,
            'Referer': self.base_url
        }
        
        async with self.session.get(self.search_url, params=search_params, headers=headers) as response:
            if response.status != 200:
                logger.error(f"FMart搜索失败: HTTP {response.status}")
                return None
                
            html = await response.text()
            
            # 解析搜索结果
            item_links = re.findall(r'<a[^>]*href="https://www.fmart.net/thread-(\d+)-\d+-\d+\.html"[^>]*title="[^>]*>([^<]+)</a>', html)
            
            if not item_links:
                logger.warning(f"FMart: 未找到匹配结果: {title}")
                return None
                
            # 获取第一个结果的详细信息
            fmart_id = item_links[0][0]
            detail_url = f"https://www.fmart.net/thread-{fmart_id}-1-1.html"
            
            async with self.session.get(detail_url, headers=headers) as detail_response:
                if detail_response.status != 200:
                    logger.error(f"FMart获取详情失败: HTTP {detail_response.status}")
                    return None
                    
                detail_html = await detail_response.text()
                
                # 解析FMart详情页
                scraped_data = self._parse_fmart_detail(detail_html, fmart_id)
                if scraped_data:
                    scraped_data['title'] = title  # 使用原始标题
                    scraped_data['year'] = year or scraped_data.get('year')
                    scraped_data['source'] = 'fmart'
                    
                return scraped_data
                
    def _parse_fmart_detail(self, html: str, fmart_id: str) -> Optional[Dict[str, Any]]:
        """解析FMart详情页"""
        try:
            # 提取标题
            title_match = re.search(r'<h1[^>]*class="ts"[^>]*>([^<]+)</h1>', html)
            title = title_match.group(1) if title_match else ''
            
            # 尝试从标题中提取年份
            year_match = re.search(r'(\d{4})', title)
            year = int(year_match.group(1)) if year_match else None
            
            # 提取评分（如果有）
            rating_match = re.search(r'<span[^>]*class="ratings"[^>]*>([^<]+)</span>', html)
            rating = float(rating_match.group(1)) if rating_match else 0
            
            # 提取简介
            summary_match = re.search(r'<div[^>]*class="t_f"[^>]*>(.*?)</div>', html, re.DOTALL)
            if summary_match:
                # 清理HTML标签
                overview = re.sub(r'<[^>]+>', '', summary_match.group(1)).strip()
            else:
                overview = ''
            
            # 提取海报
            poster_match = re.search(r'<img[^>]*src="([^"\s]*\.(jpg|png|gif))"[^>]*alt="[^>]*"', html)
            poster_path = poster_match.group(1) if poster_match else ''
            
            # 提取类型（根据关键词）
            genres = []
            if re.search(r'电影|movie', html, re.IGNORECASE):
                genres.append('电影')
            if re.search(r'剧集|series|tv', html, re.IGNORECASE):
                genres.append('剧集')
            if re.search(r'动画|anime', html, re.IGNORECASE):
                genres.append('动画')
            
            # 提取导演和演员（如果有）
            director_match = re.search(r'导演[^>]*:([^<]*)', html, re.IGNORECASE)
            director = [director_match.group(1).strip()] if director_match else []
            
            cast_match = re.search(r'演员[^>]*:([^<]*)', html, re.IGNORECASE)
            cast = []
            if cast_match:
                # 分割演员列表
                cast = [c.strip() for c in re.split(r'[，,]+', cast_match.group(1).strip())]
            
            return {
                'title': title,
                'year': year,
                'overview': overview,
                'poster_path': poster_path,
                'backdrop_path': None,
                'genres': genres,
                'rating': rating,
                'cast': cast[:5],
                'director': director[:3],
                'fmart_id': fmart_id,
                'source': 'fmart'
            }
            
        except Exception as e:
            logger.error(f"解析FMart详情失败: {e}")
            return None
            
    async def _test_connection_impl(self) -> bool:
        """测试FMart连接"""
        headers = {
            'User-Agent': self.user_agent,
            'Cookie': self.cookie
        }
        
        async with self.session.get(self.base_url, headers=headers) as response:
            return response.status == 200

class TVDBScraper(BaseScraper):
    """TVDB刮削器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__('tvdb', config)
        self.api_key = config.get('api_key')
        self.base_url = 'https://api.thetvdb.com'
        self.token = None
        
    async def _authenticate(self):
        """TVDB认证"""
        if not self.api_key:
            return False
            
        auth_url = f"{self.base_url}/login"
        auth_data = {'apikey': self.api_key}
        
        async with self.session.post(auth_url, json=auth_data) as response:
            if response.status == 200:
                data = await response.json()
                self.token = data.get('token')
                return True
            return False
            
    async def _scrape_impl(self, media_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("TVDB: API密钥未配置")
            return None
            
        # 先认证
        if not await self._authenticate():
            logger.error("TVDB认证失败")
            return None
            
        title = media_info.get('title')
        
        # 搜索剧集
        search_url = f"{self.base_url}/search/series"
        params = {'name': title}
        headers = {'Authorization': f'Bearer {self.token}'}
        
        async with self.session.get(search_url, params=params, headers=headers) as response:
            if response.status != 200:
                logger.error(f"TVDB搜索失败: HTTP {response.status}")
                return None
                
            data = await response.json()
            if not data.get('data'):
                logger.warning(f"TVDB: 未找到匹配结果: {title}")
                return None
                
            # 获取第一个结果
            result = data['data'][0]
            series_id = result['id']
            
            # 获取详细信息
            detail_url = f"{self.base_url}/series/{series_id}"
            
            async with self.session.get(detail_url, headers=headers) as detail_response:
                if detail_response.status != 200:
                    logger.error(f"TVDB获取详情失败: HTTP {detail_response.status}")
                    return None
                    
                detail_data = await detail_response.json()
                series_info = detail_data.get('data', {})
                
                # 构建返回数据
                scraped_data = {
                    'title': series_info.get('seriesName', title),
                    'original_title': series_info.get('seriesName'),
                    'year': self._extract_year(series_info.get('firstAired')),
                    'overview': series_info.get('overview', ''),
                    'poster_path': self._get_image_url(series_info.get('poster')),
                    'backdrop_path': self._get_image_url(series_info.get('fanart')),
                    'genres': [series_info.get('genre', '')] if series_info.get('genre') else [],
                    'rating': float(series_info.get('siteRating', {}).get('rating', 0)),
                    'cast': [],
                    'director': [],
                    'tvdb_id': series_id,
                    'source': 'tvdb'
                }
                
                return scraped_data
                
    def _extract_year(self, date_str: str) -> Optional[int]:
        """从日期字符串提取年份"""
        if not date_str:
            return None
        try:
            return int(date_str.split('-')[0])
        except (ValueError, IndexError):
            return None
            
    def _get_image_url(self, path: str) -> Optional[str]:
        """获取图片完整URL"""
        if not path:
            return None
        return f"https://thetvdb.com/banners/{path}"
        
    async def _test_connection_impl(self) -> bool:
        """测试TVDB连接"""
        if not self.api_key:
            return False
            
        auth_url = f"{self.base_url}/login"
        auth_data = {'apikey': self.api_key}
        
        async with self.session.post(auth_url, json=auth_data) as response:
            return response.status == 200

class ScraperManager:
    """刮削器管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.scrapers: List[BaseScraper] = []
        self._init_scrapers()
        
    def _init_scrapers(self):
        """初始化所有刮削器"""
        scraper_configs = self.config.get('scrapers', {})
        
        # 创建刮削器实例
        scraper_classes = {
            'tmdb': TMDBScraper,
            'douban': DoubanScraper,
            'bangumi': BangumiScraper,
            'imdb': IMDbScraper,
            'tvdb': TVDBScraper,
            'fmart': FMartScraper
        }
        
        for name, scraper_class in scraper_classes.items():
            config = scraper_configs.get(name, {})
            if config.get('enabled', True):
                try:
                    scraper = scraper_class(config)
                    self.scrapers.append(scraper)
                    logger.info(f"初始化刮削器: {name}")
                except Exception as e:
                    logger.error(f"初始化刮削器失败 {name}: {e}")
                    
        # 按优先级排序
        self.scrapers.sort(key=lambda x: x.priority)
        
    async def scrape_media(self, media_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """使用多个刮削器刮削媒体信息"""
        for scraper in self.scrapers:
            try:
                async with scraper:
                    result = await scraper.scrape(media_info)
                    if result:
                        logger.info(f"使用 {scraper.name} 成功刮削: {media_info.get('title', 'Unknown')}")
                        return result
            except Exception as e:
                logger.error(f"刮削器 {scraper.name} 失败: {e}")
                continue
                
        logger.error(f"所有刮削器都失败了: {media_info.get('title', 'Unknown')}")
        return None
        
    async def test_all_scrapers(self) -> Dict[str, bool]:
        """测试所有刮削器连接"""
        results = {}
        
        for scraper in self.scrapers:
            try:
                success = await scraper.test_connection()
                results[scraper.name] = success
                logger.info(f"刮削器 {scraper.name} 连接测试: {'成功' if success else '失败'}")
            except Exception as e:
                results[scraper.name] = False
                logger.error(f"刮削器 {scraper.name} 连接测试异常: {e}")
                
        return results
        
    def get_scraper_status(self) -> List[Dict[str, Any]]:
        """获取刮削器状态"""
        return [{
            'name': scraper.name,
            'enabled': scraper.enabled,
            'priority': scraper.priority,
            'timeout': scraper.timeout,
            'retry_count': scraper.retry_count
        } for scraper in self.scrapers]