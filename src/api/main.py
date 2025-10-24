from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import os
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

# 静态文件服务
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global proxy_manager, memory_manager, resource_monitor
    
    logger.info("STRM Poller 服务启动")
    
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
    """根路径，返回WebUI"""
    # 尝试多个可能的静态文件路径，适应不同环境
    possible_paths = [
        Path(__file__).parent.parent / "static" / "index.html",  # 开发环境路径
        Path("/src/static/index.html"),  # Docker容器内路径
    ]
    
    # 检查所有可能的路径
    for index_path in possible_paths:
        if index_path.exists():
            try:
                content = index_path.read_text(encoding="utf-8")
                logger.info(f"成功加载WebUI: {index_path}")
                return HTMLResponse(content=content)
            except Exception as e:
                logger.error(f"读取WebUI文件失败 {index_path}: {e}")
    
    # 所有路径都失败，返回详细错误信息
    logger.error("WebUI文件未找到")
    return JSONResponse(
        status_code=503,
        content={
            "message": "STRM Poller API", 
            "version": "3.0.0", 
            "error": "WebUI not found",
            "searched_paths": [str(p) for p in possible_paths]
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
        db_config.updated_at = datetime.now()
        
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
            db_config.updated_at = datetime.now()
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)