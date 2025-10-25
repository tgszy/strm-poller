from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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

# 初始化数据库
init_db()

# 创建FastAPI应用
app = FastAPI(
    title="STRM Poller",
    description="飞牛NAS STRM文件自动整理和刮削服务",
    version="3.0.0"
)

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
    Path("./src/static"),
    Path("/app/src/static"),
    Path("/static")
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
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
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
        <p>服务地址: http://{settings.host}:{settings.port}</p>
        <p>环境: {{"Docker容器" if os.environ.get('DOCKER_ENV', 'false').lower() == 'true' or os.path.exists('/.dockerenv') else '本地环境'}}</p>
        <p>尝试的静态目录:</p>
        <ul>
            {"\n            ".join(["<li>{path} - {status}</li>".format(path=d['path'], status='存在' if d['exists'] else '不存在') for d in static_dirs_info])}
        </ul>
    </div>
    
    <p>您仍然可以通过API访问功能。请确保正确部署WebUI文件。</p>
</body>
</html>
""")
        
        # 挂载临时目录
        app.mount("/static", StaticFiles(directory=str(temp_static_dir)), name="static")
        static_dir_found = True
        logger.info(f"已挂载临时静态文件目录: {temp_static_dir}")
    except Exception as e:
        logger.error(f"创建临时静态目录失败: {str(e)}")

def get_all_network_addresses():
    """获取所有网络接口的IP地址"""
    addresses = []
    try:
        # 获取主机名
        hostname = socket.gethostname()
        logger.debug(f"当前主机名: {hostname}")
        
        # 方法1: 通过socket.gethostbyname_ex获取IP地址
        try:
            host_ex_result = socket.gethostbyname_ex(hostname)
            for ip in host_ex_result[2]:
                # 过滤掉环回地址
                if not ip.startswith('127.'):
                    addresses.append(ip)
                    logger.debug(f"添加有效IP地址: {ip}")
        except Exception as e:
            logger.warning(f"hostbyname_ex获取失败: {e}")
        
        # 方法2: 如果没有找到有效地址，尝试通过socket.getaddrinfo
        if not addresses or all(ip.startswith('127.') for ip in addresses):
            try:
                addrinfo_results = socket.getaddrinfo(hostname, None, socket.AF_INET)
                for res in addrinfo_results:
                    ip = res[4][0]
                    if not ip.startswith('127.'):
                        addresses.append(ip)
                        logger.debug(f"通过getaddrinfo添加IP地址: {ip}")
            except Exception as e:
                logger.warning(f"getaddrinfo获取失败: {e}")
        
        # 方法3: 尝试使用netifaces库获取网络接口信息
        try:
            import netifaces
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        if ip and not ip.startswith('127.'):
                            addresses.append(ip)
                            logger.debug(f"通过netifaces添加接口 {interface} 的IP地址: {ip}")
        except (ImportError, Exception) as e:
            logger.debug(f"netifaces获取失败: {e}")
        
        # 添加自定义绑定IP（如果设置）
        custom_ip = os.environ.get('CUSTOM_BIND_IP')
        if custom_ip:
            logger.info(f"检测到自定义绑定IP: {custom_ip}")
            addresses.append(custom_ip)
        
        # 从Docker网络配置获取网关IP
        try:
            docker_gateway_ip = socket.gethostbyname('host.docker.internal')
            if docker_gateway_ip and docker_gateway_ip not in addresses:
                addresses.append(docker_gateway_ip)
                logger.info(f"检测到Docker网关地址: {docker_gateway_ip}")
        except:
            logger.debug(f"未检测到Docker网关地址")
        
        # 添加常见的Docker网络地址
        common_docker_ips = [
            '172.17.0.1',  # 默认Docker桥接网络
            '172.18.0.1',  # 自定义网络(如果使用)
        ]
        for docker_ip in common_docker_ips:
            if docker_ip not in addresses:
                addresses.append(docker_ip)
                logger.debug(f"添加常见Docker网络地址: {docker_ip}")
        
        # 去重并排序
        addresses = sorted(list(set(addresses)))
        
        # 添加localhost作为备用
        if '127.0.0.1' not in addresses:
            addresses.insert(0, '127.0.0.1')
        
        # 网络诊断信息
        logger.info("\n=== 网络诊断 ===")
        logger.info(f"检测到的IP地址: {', '.join(addresses)}")
        
    except Exception as e:
        logger.error(f"获取网络地址失败: {e}")
        import traceback
        logger.debug(f"详细错误信息: {traceback.format_exc()}")
        # 确保即使失败也返回可用地址
        addresses = ['127.0.0.1']
    
    return addresses

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global proxy_manager, memory_manager, resource_monitor
    
    # 获取所有可用的网络地址
    network_addresses = get_all_network_addresses()
    
    # 添加详细的网络绑定信息日志
    logger.info(f"STRM Poller 服务启动 - 监听地址: {settings.host}:{settings.port}")
    logger.info(f"允许访问来源: {settings.host == '0.0.0.0' and '所有网络接口' or '仅本地'}")
    logger.info(f"网络模式: {settings.host == '0.0.0.0' and '全局绑定' or '本地绑定'}")
    
    # 记录环境信息
    is_docker = os.environ.get('DOCKER_ENV', 'false').lower() == 'true' or os.path.exists('/.dockerenv')
    logger.info(f"运行环境: {'Docker容器' if is_docker else '本地环境'}")
    
    # 容器环境特殊提醒
    if is_docker:
        logger.info(f"容器环境注意事项:")
        logger.info(f"  1. 确保端口映射正确: -p {settings.port}:{settings.port}")
        logger.info(f"  2. 推荐使用host网络模式: --network=host")
    
    # 防火墙提醒
    logger.info(f"防火墙设置提醒:")
    logger.info(f"  - 请确保{settings.port}端口已在防火墙中开放")
    
    logger.info(f"\n可通过以下所有IP地址访问WebUI:")
    for ip in network_addresses:
        logger.info(f"  - http://{ip}:{settings.port}")
    
    # 网络状态检查
    import socket
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        bind_result = test_socket.bind((settings.host, settings.port))
        test_socket.close()
        logger.info(f"端口绑定测试成功: {settings.host}:{settings.port}")
    except Exception as e:
        logger.error(f"端口绑定测试失败: {e}")
        logger.error(f"请检查端口 {settings.port} 是否已被占用或权限不足")
    
    # 初始化内存管理器
    memory_manager = MemoryManager(settings.max_memory_mb)
    memory_manager.set_memory_limit()
    
    # 初始化代理管理器
    proxy_config = ProxyConfig(
        enabled=settings.proxy_enabled,
        type=settings.proxy_type,
        host=settings.proxy_host,
        port=settings.proxy_port,
        username=settings.proxy_username,
        password=settings.proxy_password
    )
    proxy_manager = ProxyManager(proxy_config)
    
    # 初始化资源监控器
    resource_monitor = ResourceMonitor(memory_manager, proxy_manager)
    await resource_monitor.start_monitoring()
    
    # 添加告警回调
    async def alert_callback(alert_info):
        await websocket_manager.broadcast({
            "type": "alert",
            "data": alert_info
        })
    resource_monitor.add_alert_callback(alert_callback)
    
    # 初始化任务管理器的刮削器管理器
    task_manager.init_scraper_manager(proxy_manager)
    
    # 启动文件监控
    watch_paths = [settings.src_path]
    if os.path.exists(settings.src_path):
        await file_processor.start_watching(watch_paths)
    
    # 启动任务监控
    asyncio.create_task(task_monitor.start_monitoring())
    
    # 启动队列处理器
    asyncio.create_task(file_processor.process_queue())

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    global proxy_manager, memory_manager, resource_monitor
    
    logger.info("STRM Poller 服务关闭")
    
    # 停止资源监控
    if resource_monitor:
        await resource_monitor.stop_monitoring()
    
    # 关闭代理管理器
    if proxy_manager:
        await proxy_manager.close_session()
    
    # 停止文件监控
    await file_processor.stop_watching()
    file_processor.stop_processing()
    
    # 停止任务监控
    task_monitor.stop()
    
    # 停止WebSocket管理器
    websocket_manager.stop()

# API路由
@app.get("/")
async def root():
    """根路径，返回WebUI - 增强的桥接模式支持"""
    # 尝试多个可能的静态文件路径，适应不同环境和桥接模式
    possible_paths = [
        Path(__file__).parent.parent / "static" / "index.html",  # 开发环境路径
        Path("/src/static/index.html"),  # Docker容器内路径
        Path("/app/src/static/index.html"),  # 另一个可能的Docker容器路径
        Path("/app/static/index.html"),  # 另一个可能的容器路径
        Path("/static/index.html"),  # 直接从挂载点访问
        Path("/config/static/index.html"),  # 临时WebUI路径
        Path(__file__).parent / "static" / "index.html",  # 另一个可能的相对路径
        # 额外添加的路径用于桥接模式支持
        Path("../static/index.html"),  # 相对路径支持
        Path("./static/index.html"),  # 当前目录下的静态文件夹
        Path(os.environ.get("STATIC_FILE_PATH", "") + "/index.html")  # 环境变量指定的路径
    ]
    
    # 获取当前工作目录信息，用于调试
    current_dir = os.getcwd()
    logger.info(f"当前工作目录: {current_dir}")
    
    # 获取所有可用网络地址
    network_addresses = get_all_network_addresses()
    
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
                                enhanced_title = f'<title>STRM Poller - 可访问地址: {" | ".join(network_addresses)}</title>'
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
        # 直接生成HTML响应，不依赖外部文件
        simple_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>STRM Poller - 管理界面</title>
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
                <p>可访问地址:</p>
                <ul style="list-style-type: none; padding: 0;">
                    {' '.join([f'<li><a href="http://{ip}:{settings.port}">http://{ip}:{settings.port}</a></li>' for ip in network_addresses])}
                </ul>
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
        return JSONResponse(
            status_code=503,
            content={
                "message": "STRM Poller API", 
                "version": "3.0.0", 
                "error": "WebUI not found or inaccessible",
                "current_working_directory": current_dir,
                "network_addresses": network_addresses,
                "access_urls": [f"http://{ip}:{settings.port}" for ip in network_addresses],
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

# 代理和内存管理API
@app.get("/api/proxy/status")
async def get_proxy_status():
    """获取代理状态"""
    if not proxy_manager:
        return {"error": "代理管理器未初始化"}
    return proxy_manager.get_status()

@app.post("/api/proxy/test")
async def test_proxy_connection():
    """测试代理连接"""
    if not proxy_manager:
        return {"error": "代理管理器未初始化"}
    return await proxy_manager.test_proxy()

@app.put("/api/proxy/config")
async def update_proxy_config(config: ProxyConfigModel):
    """更新代理配置"""
    global proxy_manager
    
    # 创建新的代理配置
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
        return [
            {
                "id": config.id,
                "name": config.name,
                "enabled": config.enabled,
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
    """获取所有可用的网络地址，用于WebUI显示，增强对桥接模式和本地网络的支持"""
    addresses = get_all_network_addresses()
    port = settings.port
    
    # 获取更多网络信息
    import socket
    hostname = socket.gethostname()
    is_docker = os.environ.get('DOCKER_ENV', 'false').lower() == 'true' or os.path.exists('/.dockerenv')
    bridge_mode = os.environ.get('BRIDGE_MODE', 'false').lower() == 'true'
    
    # 分离本地网络IP和其他IP
    local_network_ips = [ip for ip in addresses if ip.startswith('192.168.') and ip != '127.0.0.1']
    other_ips = [ip for ip in addresses if not ip.startswith('192.168.') or ip == '127.0.0.1']
    
    # 检查网络连接状态
    connection_status = {
        "hostname": hostname,
        "is_docker": is_docker,
        "bridge_mode": bridge_mode,
        "listen_host": settings.host,
        "listen_port": port,
        "is_global_binding": settings.host == '0.0.0.0',
        "local_network_ips": local_network_ips,
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
        
        # 测试本地网络连接（如果有本地网络IP）
        connection_status["local_network_tests"] = {}
        for ip in local_network_ips:
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(1)
                test_socket.connect((ip, port))
                test_socket.close()
                connection_status["local_network_tests"][ip] = "success"
            except Exception as e:
                connection_status["local_network_tests"][ip] = f"failed: {str(e)}"
    except Exception as e:
        connection_status["local_connection_test"] = f"failed: {str(e)}"
    
    # 生成访问URLs，优先显示本地网络地址
    access_urls = []
    for ip in local_network_ips:
        access_urls.append(f"http://{ip}:{port}")
    for ip in other_ips:
        access_urls.append(f"http://{ip}:{port}")
    
    # 生成桥接模式特定提示
    bridge_tips = []
    if bridge_mode:
        bridge_tips = [
            "桥接模式已启用，支持通过主机IP直接访问",
            "请确保防火墙已开放端口访问",
            "Docker桥接网络需要正确配置端口映射"
        ]
    
    return {
        "addresses": addresses,
        "local_network_addresses": local_network_ips,
        "port": port,
        "access_urls": access_urls,
        "preferred_access_urls": [f"http://{ip}:{port}" for ip in local_network_ips] if local_network_ips else access_urls[:1],
        "timestamp": datetime.datetime.now().isoformat(),
        "connection_info": connection_status,
        "tips": [
            f"确保防火墙已开放端口{port}",
            f"Docker环境下使用-p {port}:{port}映射端口",
            "或使用--network=host直接使用主机网络",
            f"访问地址格式: http://[设备IP]:{port}",
            "本地网络访问: 使用192.168.x.x格式的IP地址",
            "启用桥接模式: 设置环境变量 BRIDGE_MODE=true"
        ] + bridge_tips
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
            port_status = "✅ 端口可用" if result != 0 else "❌ 端口可能被占用"
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