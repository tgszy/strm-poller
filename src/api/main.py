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

# 静态文件服务 - 自动查找多个可能的静态文件目录
static_dirs = [
    Path(__file__).parent / "static",
    Path(__file__).parent.parent / "static",
    Path("/src/static"),
    Path("/app/src/static"),
    Path("/app/static")
]

# 尝试挂载存在的静态文件目录
static_dir_found = False
for static_dir in static_dirs:
    if static_dir.exists() and os.access(static_dir, os.R_OK):
        logger.info(f"挂载静态文件目录: {static_dir}")
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        static_dir_found = True
        break

if not static_dir_found:
    logger.warning("未找到有效的静态文件目录，WebUI可能无法正常工作")

def get_all_network_addresses():
    """获取所有网络接口的IP地址，支持识别本地IP和桥接模式"""
    addresses = []
    try:
        # 获取主机名
        hostname = socket.gethostname()
        logger.debug(f"当前主机名: {hostname}")
        
        # 获取所有网络接口的IP地址
        logger.debug(f"尝试方法1: 通过socket.gethostbyname_ex获取IP地址")
        host_ex_result = socket.gethostbyname_ex(hostname)
        logger.debug(f"hostbyname_ex结果: {host_ex_result}")
        
        for ip in host_ex_result[2]:
            # 过滤掉IPv6链路本地地址和环回地址
            if not ip.startswith('127.') and not ip.startswith('fe80::'):
                addresses.append(ip)
                logger.debug(f"添加有效IP地址: {ip}")
                # 特别标记本地网络地址(192.168.x.x)
                if ip.startswith('192.168.'):
                    logger.info(f"检测到本地网络IP地址: {ip}")
        
        # 如果没有找到除了环回以外的地址，尝试另一种方法
        if not addresses:
            logger.debug(f"方法1未找到有效地址，尝试方法2: 通过socket.getaddrinfo获取IP地址")
            addrinfo_results = socket.getaddrinfo(hostname, None, socket.AF_INET)
            logger.debug(f"getaddrinfo结果数量: {len(addrinfo_results)}")
            
            for res in addrinfo_results:
                ip = res[4][0]
                if not ip.startswith('127.'):
                    addresses.append(ip)
                    logger.debug(f"通过getaddrinfo添加IP地址: {ip}")
                    if ip.startswith('192.168.'):
                        logger.info(f"通过getaddrinfo检测到本地网络IP地址: {ip}")
        
        # 尝试获取所有网络接口信息
        try:
            import netifaces
            logger.debug(f"尝试使用netifaces库获取网络接口信息")
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                # 检查IPv4地址
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        if ip and not ip.startswith('127.'):
                            addresses.append(ip)
                            logger.debug(f"通过netifaces添加接口 {interface} 的IP地址: {ip}")
                            if ip.startswith('192.168.'):
                                logger.info(f"通过netifaces检测到本地网络IP地址: {ip} (接口: {interface})")
        except ImportError:
            logger.debug(f"netifaces库未安装，跳过详细网络接口扫描")
        except Exception as e:
            logger.debug(f"使用netifaces获取网络接口信息失败: {e}")
        
        # 手动添加用户指定的IP地址（如果环境变量设置了）
        custom_ip = os.environ.get('CUSTOM_BIND_IP')
        if custom_ip:
            logger.info(f"检测到自定义绑定IP: {custom_ip} (通过环境变量设置)")
            addresses.append(custom_ip)
        
        # 检查Docker桥接网络地址
        try:
            # 尝试获取Docker默认桥接网络地址
            docker_bridge_ip = socket.gethostbyname('docker.for.win.localhost')
            if docker_bridge_ip and docker_bridge_ip not in addresses:
                addresses.append(docker_bridge_ip)
                logger.info(f"检测到Docker桥接网络地址: {docker_bridge_ip}")
        except:
            logger.debug(f"未检测到Docker桥接网络地址")
        
        # 去重并排序
        addresses = sorted(list(set(addresses)))
        logger.debug(f"去重排序后的地址列表: {addresses}")
        
        # 添加localhost作为备用
        addresses.insert(0, '127.0.0.1')
        logger.debug(f"最终地址列表 (包含localhost): {addresses}")
        
    except Exception as e:
        logger.error(f"获取网络地址失败: {e}")
        import traceback
        logger.debug(f"详细错误信息: {traceback.format_exc()}")
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
    
    # 检测桥接模式设置
    bridge_mode = os.environ.get('BRIDGE_MODE', 'false').lower() == 'true'
    logger.info(f"桥接模式: {'已启用' if bridge_mode else '未启用'}")
    
    # 容器环境特殊提醒
    if is_docker:
        logger.info(f"容器环境注意事项:")
        logger.info(f"  1. 确保端口映射正确: -p {settings.port}:{settings.port}")
        logger.info(f"  2. 推荐使用host网络模式: --network=host")
        logger.info(f"  3. 或使用extra_hosts确保主机访问: --add-host=host.docker.internal:host-gateway")
        logger.info(f"  4. 桥接模式: 通过设置 BRIDGE_MODE=true 启用完整的桥接支持")
    
    # 防火墙提醒
    logger.info(f"防火墙设置提醒:")
    logger.info(f"  - Windows: 请确保{settings.port}端口已在防火墙中开放")
    logger.info(f"  - Linux: 请检查iptables规则确保端口可访问")
    
    # 特别提示本地网络访问
    local_network_ips = [ip for ip in network_addresses if ip.startswith('192.168.') and ip != '127.0.0.1']
    if local_network_ips:
        logger.info(f"\n本地网络访问信息 (重要):")
        logger.info(f"===================================")
        for ip in local_network_ips:
            logger.info(f"  本地网络访问地址: http://{ip}:{settings.port}")
        logger.info(f"  桥接模式访问格式: http://[主机IP]:{settings.port}")
        logger.info(f"===================================")
    
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
            
        exists = index_path.exists()
        is_readable = exists and os.access(index_path, os.R_OK)
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
    
    # 所有路径都失败，返回详细错误信息，包含更多调试数据
    logger.error("WebUI文件未找到或无法访问")
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
            },
            "available_networks": {
                "addresses": network_addresses,
                "connection_hints": [
                    "确保防火墙未阻止端口访问",
                    "在桥接模式下检查网络配置",
                    "尝试使用上面列出的IP地址访问",
                    "检查Docker网络设置是否正确"
                ]
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
    await websocket.accept()
    
    # 创建消息队列
    message_queue = asyncio.Queue()
    await websocket_manager.connect(message_queue)
    
    try:
        # 创建发送和接收任务
        async def send_messages():
            while True:
                try:
                    message = await asyncio.wait_for(message_queue.get(), timeout=1.0)
                    await websocket.send_json(message)
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
                except Exception as e:
                    logger.error(f"WebSocket接收消息失败: {e}")
                    break
        
        # 并发运行发送和接收任务
        await asyncio.gather(send_messages(), receive_messages())
        
    except WebSocketDisconnect:
        logger.info("WebSocket客户端断开连接")
    finally:
        websocket_manager.disconnect(message_queue)

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
    import uvicorn
    import socket
    
    # 获取所有可用的网络地址并记录
    network_addresses = get_all_network_addresses()
    # 强制使用'0.0.0.0'以确保在容器环境中绑定到所有网络接口
    host = '0.0.0.0'
    
    # 检测环境设置
    is_docker = os.environ.get('DOCKER_ENV', 'false').lower() == 'true' or os.path.exists('/.dockerenv')
    bridge_mode = os.environ.get('BRIDGE_MODE', 'false').lower() == 'true'
    custom_ip = os.environ.get('CUSTOM_BIND_IP')
    
    # 添加详细的启动日志
    logger.info("=== STRM Poller 服务启动配置 ===")
    logger.info(f"使用uvicorn启动应用: host={host}, port={settings.port}")
    logger.info(f"WebUI配置为监听所有网络接口 (0.0.0.0)")
    logger.info(f"运行环境检测: {'Docker容器' if is_docker else '本地环境'}")
    logger.info(f"桥接模式: {'已启用' if bridge_mode else '未启用'}")
    
    # 特别标记本地网络地址
    local_network_ips = [ip for ip in network_addresses if ip.startswith('192.168.') and ip != '127.0.0.1']
    if local_network_ips:
        logger.info(f"\n🔍 检测到本地网络IP地址 (192.168.x.x):")
        for ip in local_network_ips:
            logger.info(f"   http://{ip}:{settings.port}")
        logger.info(f"   请使用以上地址从本地网络访问WebUI")
    else:
        logger.info(f"\n⚠️  未检测到本地网络IP地址 (192.168.x.x)")
        logger.info(f"   请检查网络连接或使用以下地址:")
        
    # 显示所有可能的访问地址
    logger.info(f"\n📡 所有可用的访问地址:")
    for ip in network_addresses:
        logger.info(f"   - http://{ip}:{settings.port}")
    
    # 容器环境特殊说明
    if is_docker:
        logger.info("\n=== Docker环境配置说明 ===")
        logger.info(f"容器内部访问地址: http://127.0.0.1:{settings.port}")
        logger.info(f"主机映射访问格式: -p {settings.port}:{settings.port}")
        logger.info(f"推荐使用host网络模式: --network=host")
        logger.info(f"或添加主机访问: --add-host=host.docker.internal:host-gateway")
        
        # 桥接模式特殊说明
        if bridge_mode:
            logger.info("\n=== 桥接模式配置 ===")
            logger.info("桥接模式已启用，配置参数:")
            logger.info(f"  - 外部访问格式: http://[主机IP]:{settings.port}")
            logger.info(f"  - 例如: http://192.168.0.111:{settings.port}")
            logger.info(f"  - 确保端口映射正确: -p {settings.port}:{settings.port}")
            logger.info("  - 桥接模式允许从同一网络的其他设备访问")
    
    # 防火墙配置提醒
    logger.info("\n=== 防火墙配置提醒 ===")
    logger.info(f"请确保端口 {settings.port} 已在防火墙中开放")
    if os.name == 'nt':  # Windows系统
        logger.info(f"Windows防火墙命令: netsh advfirewall firewall add rule name=\"STRM Poller\" dir=in action=allow protocol=TCP localport={settings.port} remoteip=any profile=any")
    else:  # Linux系统
        logger.info(f"Linux防火墙命令: sudo ufw allow {settings.port}/tcp")
    
    # 网络诊断信息
    logger.info("\n=== 网络诊断信息 ===")
    try:
        # 测试端口是否可用
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(2)
        test_socket.bind((host, settings.port))
        test_socket.close()
        logger.info(f"✅ 端口 {settings.port} 可用，绑定测试成功")
    except Exception as e:
        logger.error(f"❌ 端口 {settings.port} 绑定测试失败: {e}")
        logger.error(f"  请检查端口是否已被占用或权限不足")
    
    # 获取网络接口信息
    try:
        logger.info(f"\n📊 网络连接测试:")
        for ip in network_addresses:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((ip, settings.port))
                status = "✅ 可连接" if result == 0 else "❌ 服务未启动"
                logger.info(f"   - IP: {ip}, 端口: {settings.port}, 状态: {status}")
                sock.close()
            except Exception as e:
                logger.info(f"   - IP: {ip}, 状态检查失败: {e}")
    except Exception as e:
        logger.debug(f"获取网络接口状态失败: {e}")
    
    # 显示用户指南
    logger.info("\n=== 用户访问指南 ===")
    logger.info(f"1. 如果您的设备IP是 192.168.0.111，请使用以下地址访问:")
    logger.info(f"   http://192.168.0.111:{settings.port}")
    logger.info(f"2. 确保防火墙已开放{settings.port}端口")
    logger.info(f"3. Docker运行时请使用: docker run -p {settings.port}:{settings.port} strm-poller")
    logger.info(f"4. 启用桥接模式: docker run -p {settings.port}:{settings.port} -e BRIDGE_MODE=true strm-poller")
    
    logger.info("\n=== 启动服务 ===")
    
    # 显式配置uvicorn参数以确保正确绑定所有网络接口和桥接模式支持
    uvicorn.run(
        app,
        host=host,  # 直接使用'0.0.0.0'而不是settings.host
        port=settings.port,
        log_level="debug",  # 提高日志级别以帮助调试
        access_log=True,  # 启用访问日志以帮助调试连接问题
        reload=False,      # 生产环境禁用自动重载
        forwarded_allow_ips="*",  # 允许所有IP通过代理访问，确保容器环境正常工作
        interface="",  # 让uvicorn自动处理接口绑定
        backlog=2048,  # 增加连接队列大小
        workers=1,  # 单工作进程，避免多进程绑定问题
        # 桥接模式特定配置
        limit_concurrency=1000 if bridge_mode else None,  # 桥接模式下增加并发限制
        timeout_keep_alive=30 if bridge_mode else None  # 桥接模式下优化keep-alive时间
    )