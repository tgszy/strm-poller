from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import os
import socket
import datetime
from pathlib import Path
import uvicorn

from ..core.config import settings
from ..core.logger import logger
from ..core.database import init_db, get_db, Task, FileRecord, ScraperConfig, SystemConfig
from ..core.task_manager import task_manager
from ..core.watcher import file_processor
from ..core.proxy_memory import ProxyManager, MemoryManager, ResourceMonitor, ProxyConfig
from ..services.monitor import websocket_manager, task_monitor, stats_collector
from ..core.init_default_scrapers import init_default_scrapers

# 初始化数据库
init_db()

# 初始化默认刮削源配置
init_default_scrapers()

# 创建FastAPI应用
app = FastAPI(
    title="STRM Poller",
    description="飞牛NAS STRM文件自动整理和刮削服务",
    version="3.0.0"
)

async def check_scraper_status_on_startup():
    """启动时检测刮削源状态"""
    db = next(get_db())
    try:
        # 获取所有启用的刮削源配置
        configs = db.query(ScraperConfig).filter(ScraperConfig.enabled == True).all()
        
        if not configs:
            logger.info("没有启用的刮削源配置")
            return
            
        logger.info(f"开始检测 {len(configs)} 个刮削源的状态...")
        
        # 统计检测结果
        success_count = 0
        warning_count = 0
        error_count = 0
        
        for config in configs:
            # 记录开始检测
            logger.info(f"检测刮削源: {config.name} (优先级: {config.priority})")
            
            # 检查是否有必要的配置信息
            if config.name == 'tmdb' and not config.api_key:
                logger.warning(f"TMDB刮削源未配置API Key，请检查配置")
                warning_count += 1
                continue
            elif config.name == 'douban' and not config.cookie:
                logger.warning(f"豆瓣刮削源未配置Cookie，请检查配置")
                warning_count += 1
                continue
            elif config.name == 'bangumi' and not config.api_key:
                logger.warning(f"Bangumi刮削源未配置API Key，请检查配置")
                warning_count += 1
                continue
            elif config.name == 'tvdb' and not config.api_key:
                logger.warning(f"TVDB刮削源未配置API Key，请检查配置")
                warning_count += 1
                continue
                
            # 尝试连接刮削源
            try:
                # 构建测试请求
                test_url = config.api_url if config.api_url else f"https://api.{config.name}.org"
                logger.debug(f"刮削源 {config.name} 测试URL: {test_url}")
                
                # 使用代理管理器配置
                proxy_url = None
                if proxy_manager and proxy_manager.config.enabled:
                    proxy_url = proxy_manager.config.get_proxy_url()
                    logger.debug(f"使用代理: {proxy_url}")
                else:
                    logger.debug("未使用代理")
                
                # 创建测试会话
                import aiohttp
                timeout = aiohttp.ClientTimeout(total=10)
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    headers = {}
                    
                    # 添加认证信息
                    if config.api_key:
                        if config.name == 'tmdb':
                            headers['Authorization'] = f'Bearer {config.api_key}'
                            logger.debug("添加TMDB认证头")
                        elif config.name == 'bangumi':
                            headers['Authorization'] = f'Bearer {config.api_key}'
                            logger.debug("添加Bangumi认证头")
                    
                    # 尝试发送测试请求
                    try:
                        test_endpoint = f"{test_url}/configuration" if config.name == 'tmdb' else test_url
                        logger.debug(f"发送测试请求到: {test_endpoint}")
                        
                        async with session.get(test_endpoint, headers=headers, proxy=proxy_url) as response:
                            if response.status in [200, 401, 403]:
                                # 200表示成功，401/403表示认证问题但连接正常
                                logger.info(f"刮削源 {config.name} 连接成功 (状态码: {response.status})")
                                success_count += 1
                                
                                # 记录详细信息
                                if response.status == 200:
                                    logger.info(f"✓ {config.name} - API连接正常")
                                elif response.status == 401:
                                    logger.warning(f"⚠ {config.name} - API认证失败，请检查API Key")
                                elif response.status == 403:
                                    logger.warning(f"⚠ {config.name} - API访问被拒绝，请检查权限")
                            else:
                                logger.warning(f"刮削源 {config.name} 连接异常 (状态码: {response.status})")
                                warning_count += 1
                                
                    except asyncio.TimeoutError:
                        logger.warning(f"刮削源 {config.name} 连接超时")
                        warning_count += 1
                    except Exception as e:
                        logger.warning(f"刮削源 {config.name} 连接失败: {str(e)}")
                        warning_count += 1
                        
            except Exception as e:
                logger.error(f"检测刮削源 {config.name} 状态时出错: {str(e)}")
                error_count += 1
                
    except Exception as e:
        logger.error(f"刮削源状态检测过程中出错: {str(e)}")
        error_count += 1
    finally:
        db.close()
        
    # 输出检测统计结果
    logger.info(f"刮削源状态检测完成: 成功 {success_count} 个, 警告 {warning_count} 个, 错误 {error_count} 个")
    
    # 提供用户友好的提示信息
    if warning_count > 0 or error_count > 0:
        logger.info("部分刮削源存在问题，请检查以下配置:")
        if warning_count > 0:
            logger.info("- 检查API Key、Cookie等认证信息是否正确配置")
            logger.info("- 检查网络连接和代理设置")
        if error_count > 0:
            logger.info("- 检查刮削源服务是否可用")
            logger.info("- 查看详细错误日志以获取更多信息")
    else:
        logger.info("✓ 所有刮削源状态正常")

# 全局管理器
proxy_manager = None
memory_manager = None
resource_monitor = None

# Pydantic模型
class TaskCreate(BaseModel):
    name: str
    source_path: str
    destination_path: str
    organize_strategy: str = "category"  # category, type, none

class TaskResponse(BaseModel):
    id: int
    name: str
    source_path: str
    destination_path: str
    organize_strategy: str
    status: str
    progress: float
    total_files: int
    processed_files: int
    failed_files: int
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]

class ScraperConfigUpdate(BaseModel):
    name: str
    enabled: bool
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    cookie: Optional[str] = None
    priority: int = 0
    timeout: int = 30
    retry_count: int = 3

class SystemConfigUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class ProxyConfigModel(BaseModel):
    enabled: bool = False
    type: str = "http"  # http, https, socks5
    host: str = "localhost"
    port: int = 8080
    username: Optional[str] = None
    password: Optional[str] = None
    test_url: str = "https://httpbin.org/ip"
    timeout: int = 10

class MemoryConfigModel(BaseModel):
    max_memory_mb: int = 1024
    warning_threshold: float = 0.8
    critical_threshold: float = 0.95

# 静态文件服务配置
static_dirs = [
    Path(os.environ.get("STATIC_FILE_PATH", "./src/static")),  # 从环境变量获取
    Path("./src/static"),  # 本地开发环境路径
    Path("/app/src/static"),  # Docker容器内路径
    Path("/static"),  # 可选的挂载路径
    Path(Path(__file__).parent.parent / "static")  # 基于当前文件位置的动态路径
]

# 初始化静态文件目录状态变量
static_dir_found = False
static_dirs_info = []

# 检查每个静态目录是否存在且可读
for static_dir in static_dirs:
    try:
        static_dir_info = {
            "path": str(static_dir),
            "exists": static_dir.exists(),
            "is_dir": static_dir.is_dir() if static_dir.exists() else False,
            "readable": os.access(str(static_dir), os.R_OK) if static_dir.exists() else False,
            "content": []
        }
        
        if static_dir.exists() and static_dir.is_dir():
            try:
                # 获取目录中的主要文件，限制数量以避免日志过大
                static_dir_info["content"] = sorted([
                    f for f in os.listdir(static_dir)
                    if os.path.isfile(os.path.join(static_dir, f))
                ][:10])
                
                # 找到有效的静态目录
                if not static_dir_found:
                    logger.info(f"找到有效的静态文件目录: {static_dir}")
                    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
                    static_dir_found = True
            except Exception as e:
                logger.warning(f"无法访问静态目录 {static_dir}: {str(e)}")
                static_dir_info["error"] = str(e)
        
        static_dirs_info.append(static_dir_info)
    except Exception as e:
        logger.error(f"检查静态目录 {static_dir} 时出错: {str(e)}")

# 如果没有找到有效的静态目录，创建临时目录
if not static_dir_found:
    temp_static_dir = Path("./temp_static")
    try:
        # 创建临时静态目录
        temp_static_dir.mkdir(parents=True, exist_ok=True)
        logger.warning(f"未找到静态文件目录，创建临时目录: {temp_static_dir}")
        
        # 创建基本的HTML文件
        temp_html_path = temp_static_dir / "index.html"
        # 生成静态目录HTML内容的辅助函数
        def get_static_dirs_html(dirs_info):
            items = []
            for d in dirs_info:
                status = '存在' if d['exists'] else '不存在'
                items.append(f"<li>{d['path']} - {status}</li>")
            return '\n            '.join(items)
        
        # 写入HTML内容
        device_ip = get_device_ip_address()
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STRM Poller - 临时页面</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f4f4f4;
        }}
        h1, h2 {{ color: #2c3e50; }}
        .warning {{ color: #e74c3c; }}
        .info {{ color: #3498db; }}
        .debug-info {{ background: #fff; padding: 15px; border-radius: 5px; margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>STRM Poller</h1>
    <h2 class="warning">静态文件未找到 - 临时页面</h2>
    
    <div class="info">
        <p>服务器正在运行，但未找到WebUI静态文件。</p>
        <p>这可能是因为:</p>
        <ul>
            <li>WebUI文件尚未生成或部署</li>
            <li>静态文件路径配置错误</li>
            <li>权限问题</li>
        </ul>
    </div>
    
    <div class="debug-info">
        <h3>调试信息:</h3>
        <p>访问地址: http://{device_ip}:{settings.port}</p>
        <p>环境: {"Docker容器" if os.environ.get('DOCKER_ENV', 'false').lower() == 'true' or os.path.exists('/.dockerenv') else '本地环境'}</p>
        <p>尝试的静态目录:</p>
        <ul>
            {get_static_dirs_html(static_dirs_info)}
        </ul>
    </div>
    
    <p>您仍然可以通过API访问功能。请确保正确部署WebUI文件。</p>
</body>
</html>
"""
        
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # 挂载临时目录
        app.mount("/static", StaticFiles(directory=str(temp_static_dir)), name="static")
        static_dir_found = True
        logger.info(f"已挂载临时静态文件目录: {temp_static_dir}")
    except Exception as e:
        logger.error(f"创建临时静态目录失败: {str(e)}")

def get_device_ip_address():
    """获取设备的主要IP地址"""
    try:
        # 获取主机名
        hostname = socket.gethostname()
        
        # 方法1: 通过socket.gethostbyname_ex获取IP地址
        try:
            host_ex_result = socket.gethostbyname_ex(hostname)
            for ip in host_ex_result[2]:
                # 过滤掉环回地址，优先选择192.168.x.x或10.x.x.x等私有地址
                if not ip.startswith('127.') and (ip.startswith('192.168.') or ip.startswith('10.')):
                    logger.info(f"检测到设备IP地址: {ip}")
                    return ip
        except Exception as e:
            logger.warning(f"hostbyname_ex获取失败: {e}")
        
        # 方法2: 如果没有找到私有地址，尝试获取第一个非环回地址
        try:
            host_ex_result = socket.gethostbyname_ex(hostname)
            for ip in host_ex_result[2]:
                if not ip.startswith('127.'):
                    logger.info(f"检测到设备IP地址: {ip}")
                    return ip
        except Exception as e:
            logger.warning(f"hostbyname_ex获取失败: {e}")
        
        # 方法3: 通过socket.getaddrinfo获取
        try:
            addrinfo_results = socket.getaddrinfo(hostname, None, socket.AF_INET)
            for res in addrinfo_results:
                ip = res[4][0]
                if not ip.startswith('127.'):
                    logger.info(f"检测到设备IP地址: {ip}")
                    return ip
        except Exception as e:
            logger.warning(f"getaddrinfo获取失败: {e}")
        
        # 如果以上方法都失败，返回localhost
        logger.info("未检测到设备IP地址，使用localhost")
        return '127.0.0.1'
        
    except Exception as e:
        logger.error(f"获取设备IP地址失败: {e}")
        # 确保即使失败也返回可用地址
        return '127.0.0.1'

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global proxy_manager, memory_manager, resource_monitor
    
    # 获取设备的主要IP地址
    device_ip = get_device_ip_address()
    
    # 从环境变量读取代理配置
    proxy_http = os.environ.get("PROXY_HTTP")
    proxy_https = os.environ.get("PROXY_HTTPS")
    proxy_type = os.environ.get("PROXY_TYPE", "http")
    
    # 创建默认代理配置
    proxy_config = ProxyConfig()
    
    # 如果配置了代理，则初始化代理配置
    if proxy_http or proxy_https:
        proxy_config.enabled = True
        proxy_config.type = proxy_type
        
        # 尝试解析代理URL格式
        import re
        proxy_url = proxy_http or proxy_https
        pattern = r'(?:https?|socks5)://(?:([^:@]+):([^:@]+)@)?([^:/]+):(\d+)'
        match = re.match(pattern, proxy_url)
        
        if match:
            username, password, host, port = match.groups()
            proxy_config.host = host
            proxy_config.port = int(port)
            proxy_config.username = username
            proxy_config.password = password
            logger.info(f"从环境变量加载代理配置: {proxy_url}, TYPE={proxy_type}")
        else:
            # 如果无法解析URL格式，使用默认配置
            logger.warning(f"环境变量代理配置格式错误: {proxy_url}")
            proxy_config.enabled = False
    else:
        logger.info("未配置代理环境变量")
    
    # 初始化代理管理器
    proxy_manager = ProxyManager(proxy_config)
    
    # 初始化内存管理器和资源监控器
    memory_manager = MemoryManager()
    resource_monitor = ResourceMonitor(memory_manager)
    
    # 启动时检测刮削源状态
    await check_scraper_status_on_startup()
    
    # 优化的静态文件路径列表，按优先级排序
    possible_paths = [
        Path(__file__).parent.parent / "static" / "index.html",  # 开发环境路径(优先级最高)
        Path(os.environ.get("STATIC_FILE_PATH", "") + "/index.html") if os.environ.get("STATIC_FILE_PATH") else None,  # 环境变量指定的路径
        Path("/app/src/static/index.html"),  # Docker容器内标准路径
        Path("/src/static/index.html"),  # 另一个可能的Docker路径
        Path("./src/static/index.html"),  # 相对路径
        Path("/static/index.html"),  # 可选的挂载路径
        Path("/app/static/index.html")  # 备用容器路径
    ]
    
    # 过滤掉None值
    possible_paths = [path for path in possible_paths if path]
    
    # 获取当前工作目录信息，用于调试
    current_dir = os.getcwd()
    logger.info(f"当前工作目录: {current_dir}")
    
    # 记录所有可能的路径存在状态和详细信息
    path_info = []
    for index_path in possible_paths:
        # 跳过空路径
        if not str(index_path).strip():
            continue
            
        exists = False
        is_readable = False
        try:
            exists = index_path.exists()
            is_readable = exists and os.access(index_path, os.R_OK)
        except Exception as e:
            logger.error(f"检查路径时出错 {index_path}: {str(e)}")
            
        file_info = {
            "path": str(index_path),
            "exists": exists,
            "readable": is_readable,
            "error": None
        }
        
        logger.info(f"检查WebUI路径: {index_path} - 存在: {exists}, 可读: {is_readable}")
        path_info.append(file_info)
        
        if exists:
            try:
                # 检查文件权限
                if is_readable:
                    # 验证文件内容
                    with open(index_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 简单验证是否为HTML文件
                        if '<!DOCTYPE html>' in content.lower() or '<html' in content.lower():
                            logger.info(f"成功加载WebUI: {index_path}")
                            # 增强响应，添加访问信息到HTML标题
                            if '<title>' in content:
                                enhanced_title = f'<title>STRM Poller - 访问地址: http://{device_ip}:{settings.port}</title>'
                                content = content.replace('<title>', enhanced_title, 1)
                            return HTMLResponse(content=content)
                        else:
                            logger.warning(f"文件存在但可能不是有效的HTML: {index_path}")
                else:
                    error_msg = f"无权限读取WebUI文件: {index_path}"
                    file_info["error"] = error_msg
                    logger.error(error_msg)
            except UnicodeDecodeError:
                error_msg = f"文件编码错误，无法读取: {index_path}"
                file_info["error"] = error_msg
                logger.error(error_msg)
            except Exception as e:
                error_msg = f"读取WebUI文件失败 {index_path}: {str(e)}"
                file_info["error"] = error_msg
                logger.error(error_msg)
    
    # 如果所有路径都失败，尝试创建和返回一个简单的HTML响应
    try:
        # 获取设备的主要IP地址
        device_ip = get_device_ip_address()
        
        # 直接生成HTML响应，不依赖外部文件
        simple_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>STRM Poller 服务正在运行</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; text-align: center; }}
                h1 {{ color: #333; }}
                .info {{ background: #f0f7ff; padding: 20px; border-radius: 8px; margin-top: 20px; }}
                .warning {{ background: #fff9e6; padding: 20px; border-radius: 8px; margin-top: 10px; }}
                .api-section {{ background: #e6f9e6; padding: 20px; border-radius: 8px; margin-top: 10px; }}
                .debug-info {{ background: #f8f8f8; padding: 20px; border-radius: 8px; margin-top: 10px; text-align: left; }}
                .path-list {{ max-height: 200px; overflow-y: auto; text-align: left; font-size: 12px; }}
                a {{ color: #0066cc; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>STRM Poller 服务正在运行</h1>
            <div class="info">
                <p>服务已成功启动在端口 {settings.port}</p>
                <p>访问地址: <a href="http://{device_ip}:{settings.port}">http://{device_ip}:{settings.port}</a></p>
            </div>
            <div class="api-section">
                <h3>API访问:</h3>
                <p><a href="/api/health">健康检查</a></p>
                <p><a href="/api/tasks">任务列表</a></p>
                <p>更多API端点请参考API文档</p>
            </div>
            <div class="warning">
                <p>⚠️ 完整WebUI未找到，请检查静态文件目录配置</p>
                <p>临时界面提供API访问入口</p>
            </div>
            <div class="debug-info">
                <h3>调试信息:</h3>
                <p><strong>工作目录:</strong> {current_dir}</p>
                <p><strong>监听配置:</strong> {settings.host}:{settings.port}</p>
                <div class="path-list">
                    <p><strong>检查的路径:</strong></p>
                    <ul>
                        {' '.join([f'<li>{info["path"]} - 存在: {info["exists"]}, 可读: {info["readable"]}{" - " + info["error"] if info["error"] else ""}</li>' for info in path_info])}
                    </ul>
                </div>
            </div>
        </body>
        </html>
        '''
        logger.info("返回内联生成的临时WebUI页面")
        return HTMLResponse(content=simple_html)
    except Exception as e:
        logger.error(f"生成内联HTML页面失败: {e}")
        
        # 作为最后的备选，返回JSON响应
        device_ip = get_device_ip_address()
        return JSONResponse(
            status_code=503,
            content={
                "message": "STRM Poller API", 
                "version": "3.0.0", 
                "error": "WebUI not found or inaccessible",
                "current_working_directory": current_dir,
                "device_ip": device_ip,
                "access_url": f"http://{device_ip}:{settings.port}",
                "path_check_results": path_info,
                "server_info": {
                    "host": settings.host,
                    "port": settings.port,
                    "debug": settings.debug,
                    "os": os.name,
                    "python_version": os.sys.version
                }
            }
        )

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """根路由 - 返回WebUI"""
    try:
        # 尝试从静态目录读取index.html（使用绝对路径确保正确性）
        base_dir = Path(__file__).parent.parent
        static_dir = base_dir / "static"
        index_file = static_dir / "index.html"
        
        if index_file.exists() and index_file.is_file():
            with open(index_file, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            # 修复静态文件引用路径
            html_content = html_content.replace('src="static/js/app.js"', 'src="/static/js/app.js"')
            html_content = html_content.replace('src="static/bootstrap-local.js"', 'src="/static/bootstrap-local.js"')
            html_content = html_content.replace('href="static/bootstrap-local.css"', 'href="/static/bootstrap-local.css"')
            
            return HTMLResponse(content=html_content)
        else:
            # 如果找不到index.html，返回简单的HTML页面
            device_ip = get_device_ip_address()
            html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STRM Poller</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        .info {{ background: #f8f9fa; padding: 20px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>STRM Poller</h1>
    <div class="info">
        <p>服务正在运行，但WebUI文件未找到。</p>
        <p>访问地址: http://{device_ip}:{settings.port}</p>
        <p>请确保WebUI文件已正确部署到src/static目录。</p>
    </div>
</body>
</html>"""
            return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"根路由处理失败: {e}")
        return HTMLResponse(content=f"<h1>STRM Poller</h1><p>WebUI加载失败: {str(e)}</p>", status_code=500)

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}

# 任务管理API
@app.post("/api/tasks", response_model=Dict[str, Any])
async def create_task(task: TaskCreate):
    """创建任务"""
    try:
        task_id = await task_manager.create_task(
            name=task.name,
            source_path=task.source_path,
            destination_path=task.destination_path,
            organize_strategy=task.organize_strategy
        )
        return {"success": True, "task_id": task_id}
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/tasks", response_model=List[TaskResponse])
async def get_tasks():
    """获取任务列表"""
    db = next(get_db())
    try:
        tasks = db.query(Task).order_by(Task.created_at.desc()).all()
        return [
            TaskResponse(
                id=task.id,
                name=task.name,
                source_path=task.source_path,
                destination_path=task.destination_path,
                organize_strategy=task.organize_strategy,
                status=task.status,
                progress=task.progress,
                total_files=task.total_files,
                processed_files=task.processed_files,
                failed_files=task.failed_files,
                created_at=task.created_at.isoformat() if task.created_at else None,
                started_at=task.started_at.isoformat() if task.started_at else None,
                completed_at=task.completed_at.isoformat() if task.completed_at else None
            )
            for task in tasks
        ]
    finally:
        db.close()

@app.post("/api/tasks/{task_id}/start")
async def start_task(task_id: int):
    """启动任务"""
    success = await task_manager.start_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="无法启动任务")
    return {"success": True}

@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: int):
    """暂停任务"""
    success = await task_manager.pause_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="无法暂停任务")
    return {"success": True}

@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: int):
    """取消任务"""
    success = await task_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="无法取消任务")
    return {"success": True}

@app.post("/api/tasks/{task_id}/retry")
async def retry_task(task_id: int):
    """重试任务失败的文件"""
    retry_count = await task_manager.retry_failed_files(task_id)
    return {"success": True, "retry_count": retry_count}

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除任务"""
    db = next(get_db())
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 如果任务正在运行，先停止
        if task.status == "running":
            await task_manager.cancel_task(task_id)
        
        # 删除任务记录
        db.delete(task)
        db.commit()
        
        return {"success": True}
    finally:
        db.close()

# 任务文件管理API
@app.get("/api/tasks/{task_id}/files")
async def get_task_files(task_id: int, status: Optional[str] = Query(None, description="文件状态过滤，支持failed,success等")):
    """获取任务文件列表"""
    db = next(get_db())
    try:
        # 检查任务是否存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 查询文件记录
        query = db.query(FileRecord).filter(FileRecord.task_id == task_id)
        
        # 如果指定了状态过滤
        if status:
            query = query.filter(FileRecord.status == status)
        
        files = query.all()
        
        # 转换为响应格式
        return {
            "files": [
                {
                    "id": file.id,
                    "file_name": os.path.basename(file.file_path),
                    "file_path": file.file_path,
                    "status": file.status,
                    "error_message": file.error_message,
                    "created_at": file.created_at.isoformat() if file.created_at else None
                }
                for file in files
            ]
        }
    finally:
        db.close()

# 任务日志API
@app.get("/api/tasks/{task_id}/logs")
async def get_task_logs(task_id: int):
    """获取任务日志"""
    db = next(get_db())
    try:
        # 检查任务是否存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取任务日志记录
        # 这里我们从数据库中获取与任务相关的文件处理日志
        # 实际应用中，可能需要专门的日志表来存储更详细的日志
        
        # 从文件记录中提取日志信息
        file_records = db.query(FileRecord).filter(FileRecord.task_id == task_id).order_by(FileRecord.created_at).all()
        
        logs = []
        
        # 添加任务开始日志
        if task.started_at:
            logs.append(f"[{task.started_at.strftime('%Y-%m-%d %H:%M:%S')}] 任务开始处理: {task.name}")
            logs.append(f"[{task.started_at.strftime('%Y-%m-%d %H:%M:%S')}] 扫描源路径: {task.source_path}")
            logs.append(f"[{task.started_at.strftime('%Y-%m-%d %H:%M:%S')}] 目标路径: {task.destination_path}")
            logs.append(f"[{task.started_at.strftime('%Y-%m-%d %H:%M:%S')}] 组织策略: {task.organize_strategy}")
        
        # 添加文件处理日志
        for file in file_records:
            timestamp = file.created_at.strftime('%Y-%m-%d %H:%M:%S') if file.created_at else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if file.status == "success":
                logs.append(f"[{timestamp}] 成功 - {os.path.basename(file.file_path)}")
            elif file.status == "failed":
                error_msg = file.error_message if file.error_message else "处理失败"
                logs.append(f"[{timestamp}] ERROR - {os.path.basename(file.file_path)} - {error_msg}")
            elif file.status == "skipped":
                logs.append(f"[{timestamp}] 跳过 - {os.path.basename(file.file_path)}")
        
        # 添加任务完成日志
        if task.completed_at:
            logs.append(f"[{task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}] 任务处理完成: {task.name}")
            logs.append(f"[{task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}] 统计: 总数 {task.total_files}, 成功 {task.processed_files}, 失败 {task.failed_files}")
        
        # 如果没有日志，添加默认日志
        if not logs:
            logs.append(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 任务: {task.name} (ID: {task_id})")
            logs.append(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 状态: {task.status}")
        
        return {"logs": logs}
    finally:
        db.close()

# 定义重试单个文件的请求模型
class RetryFileRequest(BaseModel):
    new_filename: str

@app.post("/api/tasks/{task_id}/files/{file_id}/retry")
async def retry_single_file(task_id: int, file_id: int, request: RetryFileRequest):
    """重试单个失败文件"""
    try:
        # 调用task_manager的重试单个文件方法
        result = await task_manager.retry_single_file(task_id, file_id, request.new_filename)
        return result
    except Exception as e:
        logger.error(f"重试单个文件失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# 代理和内存管理API
@app.get("/api/proxy/status")
async def get_proxy_status():
    """获取代理状态"""
    if not proxy_manager:
        return {"error": "代理管理器未初始化"}
    return proxy_manager.get_status()

class ProxyTestRequest(BaseModel):
    proxy_url: Optional[str] = None

@app.post("/api/proxy/test")
async def test_proxy_connection(request: ProxyTestRequest):
    """测试代理连接"""
    if not proxy_manager:
        return {"error": "代理管理器未初始化"}
    
    # 如果提供了代理URL，则测试该URL，否则测试当前配置的代理
    if request.proxy_url:
        return await proxy_manager.test_proxy_url(request.proxy_url)
    else:
        return await proxy_manager.test_proxy()

@app.put("/api/proxy/config")
async def update_proxy_config(config: ProxyConfigModel):
    """更新代理配置"""
    global proxy_manager
    
    # 检查环境变量中的代理配置，优先使用环境变量
    proxy_http = os.environ.get("PROXY_HTTP")
    proxy_https = os.environ.get("PROXY_HTTPS")
    proxy_type = os.environ.get("PROXY_TYPE", "http")
    
    # 如果环境变量中有代理配置，则使用环境变量配置
    if proxy_http or proxy_https:
        # 解析环境变量中的代理配置
        import re
        
        # 尝试从PROXY_HTTP或PROXY_HTTPS中提取主机和端口
        proxy_url = proxy_http or proxy_https
        
        # 匹配代理URL格式：protocol://host:port 或 protocol://user:pass@host:port
        pattern = r'(?:https?|socks5)://(?:([^:@]+):([^:@]+)@)?([^:/]+):(\d+)'
        match = re.match(pattern, proxy_url)
        
        if match:
            username, password, host, port = match.groups()
            proxy_config = ProxyConfig(
                enabled=True,
                type=proxy_type,
                host=host,
                port=int(port),
                username=username,
                password=password,
                test_url=config.test_url,
                timeout=config.timeout
            )
            logger.info(f"从环境变量加载代理配置: {proxy_url}, TYPE={proxy_type}")
        else:
            # 如果无法解析环境变量，则使用API传入的配置
            proxy_config = ProxyConfig(
                enabled=config.enabled,
                type=config.type,
                host=config.host,
                port=config.port,
                username=config.username,
                password=config.password,
                test_url=config.test_url,
                timeout=config.timeout
            )
            logger.info("环境变量代理配置格式错误，使用API配置")
    else:
        # 没有环境变量配置，使用API传入的配置
        proxy_config = ProxyConfig(
            enabled=config.enabled,
            type=config.type,
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            test_url=config.test_url,
            timeout=config.timeout
        )
        logger.info("未配置代理环境变量，使用API配置")
        
        # 检查数据库中是否有代理URL配置
        db = next(get_db())
        try:
            proxy_url_config = db.query(SystemConfig).filter(SystemConfig.key == "proxy_url").first()
            proxy_enabled_config = db.query(SystemConfig).filter(SystemConfig.key == "proxy_enabled").first()
            
            if proxy_url_config and proxy_url_config.value:
                import re
                proxy_url = proxy_url_config.value
                
                # 匹配代理URL格式：protocol://host:port 或 protocol://user:pass@host:port
                pattern = r'(?:https?|socks5)://(?:([^:@]+):([^:@]+)@)?([^:/]+):(\d+)'
                match = re.match(pattern, proxy_url)
                
                if match:
                    username, password, host, port = match.groups()
                    # 从URL中提取协议类型
                    protocol_match = re.match(r'(https?|socks5)', proxy_url)
                    protocol = protocol_match.group(1) if protocol_match else 'http'
                    
                    # 更新代理配置
                    proxy_config.enabled = proxy_enabled_config.value.lower() == "true" if proxy_enabled_config else config.enabled
                    proxy_config.type = protocol
                    proxy_config.host = host
                    proxy_config.port = int(port)
                    proxy_config.username = username
                    proxy_config.password = password
                    logger.info(f"从数据库加载代理配置: {proxy_url}")
        finally:
            db.close()
    
    # 重新初始化代理管理器
    if proxy_manager:
        await proxy_manager.close_session()
    
    proxy_manager = ProxyManager(proxy_config)
    
    return {"success": True, "message": "代理配置已更新"}

@app.get("/api/memory/status")
async def get_memory_status():
    """获取内存状态"""
    if not memory_manager:
        return {"error": "内存管理器未初始化"}
    return memory_manager.get_status()

@app.put("/api/memory/config")
async def update_memory_config(config: MemoryConfigModel):
    """更新内存配置"""
    global memory_manager
    
    # 创建新的内存管理器
    memory_manager = MemoryManager(config.max_memory_mb)
    memory_manager.set_memory_limit()
    
    # 更新资源监控器
    if resource_monitor:
        resource_monitor.memory_manager = memory_manager
    
    return {"success": True, "message": "内存配置已更新"}

@app.get("/api/system/status")
async def get_system_status():
    """获取系统状态"""
    if not resource_monitor:
        return {"error": "资源监控器未初始化"}
    return resource_monitor.get_system_status()

# 刮削源配置API
@app.get("/api/scraper-configs")
async def get_scraper_configs():
    """获取刮削源配置"""
    db = next(get_db())
    try:
        configs = db.query(ScraperConfig).order_by(ScraperConfig.priority.asc()).all()
        
        # 刮削源显示名称映射
        display_name_map = {
            'tmdb': 'TMDB',
            'douban': '豆瓣',
            'bangumi': 'Bangumi',
            'imdb': 'IMDb',
            'tvdb': 'TVDB'
        }
        
        return [
            {
                "id": config.id,
                "name": config.name,
                "display_name": display_name_map.get(config.name, config.name.title()),
                "enabled": config.enabled,
                "api_url": config.api_url,
                "api_key": config.api_key,
                "cookie": config.cookie,
                "priority": config.priority,
                "timeout": config.timeout,
                "retry_count": config.retry_count,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None
            }
            for config in configs
        ]
    finally:
        db.close()

@app.put("/api/scraper-configs/{config_id}")
async def update_scraper_config(config_id: int, config: ScraperConfigUpdate):
    """更新刮削源配置"""
    db = next(get_db())
    try:
        db_config = db.query(ScraperConfig).filter(ScraperConfig.id == config_id).first()
        if not db_config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        db_config.enabled = config.enabled
        db_config.api_url = config.api_url
        db_config.api_key = config.api_key
        db_config.cookie = config.cookie
        db_config.priority = config.priority
        db_config.timeout = config.timeout
        db_config.retry_count = config.retry_count
        db_config.updated_at = datetime.datetime.now()
        
        db.commit()
        return {"success": True}
    finally:
        db.close()

@app.put("/api/scrapers/priority")
async def update_scrapers_priority(updates: dict):
    """批量更新刮削源优先级"""
    db = next(get_db())
    try:
        scraper_updates = updates.get("updates", [])
        
        for update in scraper_updates:
            scraper_id = update.get("id")
            new_priority = update.get("priority")
            
            if scraper_id is not None and new_priority is not None:
                db_config = db.query(ScraperConfig).filter(ScraperConfig.id == scraper_id).first()
                if db_config:
                    db_config.priority = new_priority
                    db_config.updated_at = datetime.datetime.now()
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新优先级失败: {str(e)}")
    finally:
        db.close()

# 系统配置API
@app.get("/api/system-configs")
async def get_system_configs():
    """获取系统配置"""
    db = next(get_db())
    try:
        configs = db.query(SystemConfig).all()
        return [
            {
                "id": config.id,
                "key": config.key,
                "value": config.value,
                "description": config.description,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None
            }
            for config in configs
        ]
    finally:
        db.close()

@app.put("/api/system-configs")
async def update_system_config(config: SystemConfigUpdate):
    """更新系统配置"""
    db = next(get_db())
    try:
        db_config = db.query(SystemConfig).filter(SystemConfig.key == config.key).first()
        if not db_config:
            # 创建新配置
            db_config = SystemConfig(
                key=config.key,
                value=config.value,
                description=config.description
            )
            db.add(db_config)
        else:
            db_config.value = config.value
            db_config.description = config.description
            db_config.updated_at = datetime.datetime.now()
        
        db.commit()
        return {"success": True}
    finally:
        db.close()

# 统计信息API
@app.get("/api/stats/system")
async def get_system_stats():
    """获取系统统计信息"""
    stats = stats_collector.get_system_stats()
    return stats

@app.get("/api/stats/tasks")
async def get_task_stats():
    """获取任务统计信息"""
    stats = stats_collector.get_task_stats()
    return stats

# WebSocket端点
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接端点"""
    message_queue = None
    send_task = None
    receive_task = None
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket连接已接受")
        
        # 创建消息队列
        message_queue = asyncio.Queue()
        await websocket_manager.connect(message_queue)
        logger.debug(f"WebSocket客户端已连接到消息管理器")
        
        # 创建发送和接收任务
        async def send_messages():
            while True:
                try:
                    message = await asyncio.wait_for(message_queue.get(), timeout=1.0)
                    await websocket.send_json(message)
                    message_queue.task_done()
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"WebSocket发送消息失败: {e}")
                    break
        
        async def receive_messages():
            while True:
                try:
                    data = await websocket.receive_json()
                    # 处理客户端消息
                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    logger.debug(f"WebSocket收到客户端消息: {data.get('type')}")
                except Exception as e:
                    logger.error(f"WebSocket接收消息失败: {e}")
                    break
        
        # 并发运行发送和接收任务
        send_task = asyncio.create_task(send_messages())
        receive_task = asyncio.create_task(receive_messages())
        
        await asyncio.gather(send_task, receive_task)
        
    except WebSocketDisconnect:
        logger.info("WebSocket客户端断开连接")
    except Exception as e:
        logger.error(f"WebSocket连接发生异常: {e}")
    finally:
        # 确保资源正确清理
        if send_task:
            send_task.cancel()
        if receive_task:
            receive_task.cancel()
        if message_queue:
            websocket_manager.disconnect(message_queue)
        logger.info("WebSocket资源已清理")

@app.get("/api/network/addresses")
async def get_network_addresses():
    """获取设备的主要网络地址，用于WebUI显示"""
    device_ip = get_device_ip_address()
    port = settings.port
    
    # 获取更多网络信息
    import socket
    hostname = socket.gethostname()
    is_docker = os.environ.get('DOCKER_ENV', 'false').lower() == 'true' or os.path.exists('/.dockerenv')
    bridge_mode = os.environ.get('BRIDGE_MODE', 'false').lower() == 'true'
    
    # 检查网络连接状态
    connection_status = {
        "hostname": hostname,
        "is_docker": is_docker,
        "bridge_mode": bridge_mode,
        "listen_host": settings.host,
        "listen_port": port,
        "is_global_binding": settings.host == '0.0.0.0',
        "device_ip": device_ip,
        "environment_vars": {
            "DOCKER_ENV": os.environ.get('DOCKER_ENV'),
            "BRIDGE_MODE": os.environ.get('BRIDGE_MODE'),
            "CUSTOM_BIND_IP": os.environ.get('CUSTOM_BIND_IP'),
            "HOSTNAME": os.environ.get('HOSTNAME')
        }
    }
    
    # 添加连接诊断信息
    try:
        # 尝试连接本地服务
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        test_socket.connect(('127.0.0.1', port))
        test_socket.close()
        connection_status["local_connection_test"] = "success"
        
        # 测试设备IP连接
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            test_socket.connect((device_ip, port))
            test_socket.close()
            connection_status["device_ip_connection_test"] = "success"
        except Exception as e:
            connection_status["device_ip_connection_test"] = f"failed: {str(e)}"
    except Exception as e:
        connection_status["local_connection_test"] = f"failed: {str(e)}"
    
    return {
        "device_ip": device_ip,
        "port": port,
        "access_url": f"http://{device_ip}:{port}",
        "timestamp": datetime.datetime.now().isoformat(),
        "connection_info": connection_status,
        "tips": [
            f"确保防火墙已开放端口{port}",
            f"Docker环境下使用-p {port}:{port}映射端口",
            f"访问地址格式: http://{device_ip}:{port}",
            "启用桥接模式: 设置环境变量 BRIDGE_MODE=true"
        ]
    }

if __name__ == "__main__":
    # 打印运行配置提示
    logger.info("\n=== 运行配置指南 ===")
    logger.info("推荐使用以下Docker命令启动:")
    logger.info("  # Host模式 (推荐)")
    logger.info("  docker run -d")
    logger.info("    --name strm-poller")
    logger.info("    --network=host")
    logger.info("    -v $(pwd)/config:/config")
    logger.info("    -v $(pwd)/media:/media")
    logger.info("    --restart unless-stopped")
    logger.info("    strm-poller:latest")
    logger.info("")
    logger.info("  # Bridge模式")
    logger.info("  docker run -d")
    logger.info("    --name strm-poller")
    logger.info("    -p 35455:35455")
    logger.info("    -v $(pwd)/config:/config")
    logger.info("    -v $(pwd)/media:/media")
    logger.info("    --restart unless-stopped")
    logger.info("    strm-poller:latest")
    logger.info("")
    logger.info("  # 注意: Bridge模式下端口映射为 35455:35455")
    logger.info("  # Host模式下直接使用端口 35455")
    
    # 防火墙配置提醒
    logger.info("\n=== 防火墙配置 ===")
    logger.info(f"  - 请确保{settings.port}端口已在防火墙中开放")
    logger.info("  - 对于Windows系统: 检查Windows Defender防火墙设置")
    logger.info("  - 对于Linux系统: 使用ufw或iptables开放端口")
    
    # 网络诊断信息
    logger.info("\n=== 网络诊断 ===")
    # 端口测试
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(("127.0.0.1", settings.port))
        port_status = "✅ 端口可用" if result != 0 else "❌ 端口可能被占用"  # connect_ex返回0表示连接成功(端口被占用)
    except:
        port_status = "⚠️  无法检测端口状态"
    logger.info(f"  端口状态: {port_status}")
    
    # 网络连接测试
    try:
        socket.create_connection(("www.google.com", 80), timeout=5)
        net_status = "✅ 网络连接正常"
    except:
        net_status = "⚠️  网络连接可能存在问题"
    logger.info(f"  网络状态: {net_status}")
    
    # 启动uvicorn服务器
    logger.info("\n=== 启动服务器 ===")
    logger.info(f"  启动STRM Poller 服务...")
    
    # 启动uvicorn服务器
    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        log_level="info" if not settings.debug else "debug",
        workers=1,
        timeout_keep_alive=60,
        timeout_graceful_shutdown=5
    )