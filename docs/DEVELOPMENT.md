# STRM Poller 开发指南

## 开发环境搭建

### 系统要求

- Python 3.8+
- Node.js 16+ (用于前端开发)
- Docker (可选，用于容器化部署)
- Git

### 环境配置

1. **克隆项目**
```bash
# 克隆仓库
git clone https://github.com/tgszy/strm-poller.git
cd strm-poller
```

2. **创建虚拟环境**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **安装开发依赖**
```bash
pip install -r requirements-dev.txt
```

5. **创建配置文件**
```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml 文件
```

### 项目结构

```
strm-poller/
├── src/
│   ├── api/                    # FastAPI 接口层
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI 应用入口
│   │   ├── routes/            # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── tasks.py       # 任务管理接口
│   │   │   ├── proxy.py       # 代理配置接口
│   │   │   ├── scrapers.py    # 刮削源接口
│   │   │   └── system.py      # 系统状态接口
│   │   └── websocket.py       # WebSocket 处理
│   ├── core/                  # 核心业务逻辑
│   │   ├── __init__.py
│   │   ├── config.py          # 配置管理
│   │   ├── task_manager.py    # 任务管理器
│   │   ├── scrapers.py        # 刮削器管理
│   │   ├── proxy_memory.py    # 代理管理器
│   │   └── models.py          # 数据模型
│   ├── services/              # 后台服务
│   │   ├── __init__.py
│   │   ├── monitor.py         # 系统监控服务
│   │   └── watcher.py         # 文件监控服务
│   ├── static/                # WebUI 静态文件
│   │   ├── index.html
│   │   ├── css/
│   │   ├── js/
│   │   └── assets/
│   └── utils/                 # 工具函数
│       ├── __init__.py
│       ├── logger.py          # 日志工具
│       └── helpers.py         # 辅助函数
├── tests/                     # 测试文件
├── docs/                      # 文档
├── requirements.txt           # Python 依赖
├── requirements-dev.txt       # 开发依赖
├── Dockerfile                # Docker 构建文件
├── docker-compose.yml        # Docker Compose 配置
└── README.md                 # 项目说明
```

## 开发模式运行

### 后端开发模式
```bash
# 启动后端服务
python -m src.main --dev

# 或使用 uvicorn 直接启动
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 3456
```

### 前端开发模式
```bash
# 进入静态文件目录
cd src/static

# 安装前端依赖
npm install

# 启动前端开发服务器
npm run dev
```

## 代码规范

### Python 代码规范

1. **遵循 PEP 8**
   - 使用 4 个空格缩进
   - 行长度不超过 88 个字符（Black 默认）
   - 使用有意义的变量名

2. **类型注解**
```python
from typing import Optional, List, Dict, Any

def process_file(
    file_path: str,
    task_id: str,
    options: Optional[Dict[str, Any]] = None
) -> bool:
    """处理单个文件"""
    pass
```

3. **文档字符串**
```python
def create_task(name: str, source_path: str) -> str:
    """
    创建新的整理任务
    
    Args:
        name: 任务名称
        source_path: 源文件路径
        
    Returns:
        任务ID
        
    Raises:
        ValueError: 参数无效时抛出
    """
    pass
```

4. **错误处理**
```python
try:
    result = scraper.scrape_media(file_path)
except ScraperError as e:
    logger.error(f"刮削失败: {e}")
    raise TaskError(f"文件处理失败: {file_path}") from e
except Exception as e:
    logger.exception(f"未知错误: {e}")
    raise
```

### 代码格式化

```bash
# 格式化代码
black src/ tests/

# 检查代码风格
flake8 src/ tests/

# 类型检查
mypy src/

# 自动修复导入排序
isort src/ tests/
```

## 测试

### 运行测试
```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_task_manager.py

# 运行特定测试函数
pytest tests/test_task_manager.py::test_create_task

# 生成测试覆盖率报告
pytest --cov=src --cov-report=html
```

### 测试结构
```python
# tests/test_task_manager.py
import pytest
from src.core.task_manager import TaskManager
from src.core.config import Settings

class TestTaskManager:
    @pytest.fixture
    def task_manager(self):
        settings = Settings()
        return TaskManager(settings)
    
    def test_create_task_success(self, task_manager):
        """测试成功创建任务"""
        task_id = task_manager.create_task(
            name="测试任务",
            source_path="/test/src",
            target_path="/test/dst"
        )
        assert task_id is not None
        assert len(task_id) > 0
    
    def test_create_task_invalid_path(self, task_manager):
        """测试无效路径"""
        with pytest.raises(ValueError):
            task_manager.create_task(
                name="测试任务",
                source_path="",
                target_path="/test/dst"
            )
```

## 数据库设计

### SQLite 数据库结构

```sql
-- 任务表
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    target_path TEXT NOT NULL,
    organization_strategy TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL DEFAULT 0.0,
    files_processed INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文件记录表
CREATE TABLE task_files (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_path TEXT NOT NULL,
    target_path TEXT,
    status TEXT NOT NULL,
    media_info TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 系统日志表
CREATE TABLE system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    module TEXT,
    task_id TEXT,
    extra_data TEXT
);

-- 代理状态表
CREATE TABLE proxy_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    response_time_ms INTEGER,
    error_message TEXT
);
```

## 核心模块开发

### 任务管理器 (TaskManager)

```python
# src/core/task_manager.py
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from .models import Task, TaskStatus
from .scrapers import ScraperManager
from .config import Settings

logger = logging.getLogger(__name__)

class TaskManager:
    """任务管理器"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tasks: Dict[str, Task] = {}
        self.scraper_manager: Optional[ScraperManager] = None
        self._running = False
    
    async def init_scraper_manager(self, proxy_manager):
        """初始化刮削器管理器"""
        # 实现代码...
        pass
    
    def create_task(
        self,
        name: str,
        source_path: str,
        target_path: str,
        organization_strategy: str = "by_category",
        auto_start: bool = False
    ) -> str:
        """创建新任务"""
        # 实现代码...
        pass
    
    async def start_task(self, task_id: str) -> bool:
        """启动任务"""
        # 实现代码...
        pass
    
    async def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        # 实现代码...
        pass
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        # 实现代码...
        pass
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        # 实现代码...
        pass
```

### 刮削器管理器 (ScraperManager)

```python
# src/core/scrapers.py
import asyncio
import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from .models import MediaInfo

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """基础刮削器类"""
    
    def __init__(self, config: Dict[str, Any], proxy_url: Optional[str] = None):
        self.config = config
        self.proxy_url = proxy_url
        self.enabled = config.get('enabled', True)
        self.priority = config.get('priority', 1)
        self.timeout = config.get('timeout', 30)
        self.retries = config.get('retries', 3)
    
    @abstractmethod
    async def scrape_media(self, file_path: str) -> Optional[MediaInfo]:
        """刮削媒体信息"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """测试连接"""
        pass

class TMDBScraper(BaseScraper):
    """TMDB 刮削器"""
    
    async def scrape_media(self, file_path: str) -> Optional[MediaInfo]:
        # 实现 TMDB 刮削逻辑
        pass
    
    async def test_connection(self) -> bool:
        # 测试 TMDB API 连接
        pass

class ScraperManager:
    """刮削器管理器"""
    
    def __init__(self, scraper_configs: Dict[str, Any], proxy_manager=None):
        self.scrapers: List[BaseScraper] = []
        self.proxy_manager = proxy_manager
        self._init_scrapers(scraper_configs)
    
    def _init_scrapers(self, configs: Dict[str, Any]):
        """初始化刮削器"""
        # 实现代码...
        pass
    
    async def scrape_media(self, file_path: str) -> Optional[MediaInfo]:
        """按优先级刮削媒体信息"""
        # 实现代码...
        pass
    
    async def test_all_scrapers(self) -> Dict[str, bool]:
        """测试所有刮削器"""
        # 实现代码...
        pass
```

### 代理管理器 (ProxyManager)

```python
# src/core/proxy_memory.py
import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ProxyConfig:
    """代理配置"""
    enabled: bool = False
    type: str = "http"  # http, https, socks5
    host: str = "localhost"
    port: int = 8080
    username: Optional[str] = None
    password: Optional[str] = None
    
    @property
    def url(self) -> str:
        """生成代理 URL"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.type}://{auth}{self.host}:{self.port}"

class ProxyManager:
    """代理管理器"""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.status = "unknown"
        self.last_check = None
        self.response_time = None
    
    async def test_connection(self) -> bool:
        """测试代理连接"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            async with aiohttp.ClientSession() as session:
                proxy = self.config.url if self.config.enabled else None
                
                async with session.get(
                    "https://httpbin.org/ip",
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        self.status = "connected"
                        self.response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                        self.last_check = datetime.now()
                        return True
                    else:
                        self.status = "failed"
                        return False
                        
        except Exception as e:
            logger.error(f"代理测试失败: {e}")
            self.status = "failed"
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取代理状态"""
        return {
            "enabled": self.config.enabled,
            "type": self.config.type,
            "host": self.config.host,
            "port": self.config.port,
            "status": self.status,
            "response_time_ms": self.response_time,
            "last_check": self.last_check.isoformat() if self.last_check else None
        }
```

## API 开发

### FastAPI 路由示例

```python
# src/api/routes/tasks.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from ...core.task_manager import TaskManager

router = APIRouter(prefix="/tasks", tags=["任务管理"])

task_manager: TaskManager = None  # 将在应用启动时注入

class CreateTaskRequest(BaseModel):
    name: str
    source_path: str
    target_path: str
    organization_strategy: str = "by_category"
    auto_start: bool = False

class TaskResponse(BaseModel):
    id: str
    name: str
    status: str
    progress: float
    files_processed: int
    total_files: int
    created_at: str

@router.post("/", response_model=Dict[str, str])
async def create_task(request: CreateTaskRequest):
    """创建新任务"""
    try:
        task_id = task_manager.create_task(
            name=request.name,
            source_path=request.source_path,
            target_path=request.target_path,
            organization_strategy=request.organization_strategy,
            auto_start=request.auto_start
        )
        return {"success": True, "task_id": task_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    status: Optional[str] = Query(None, description="任务状态过滤"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """获取任务列表"""
    tasks = task_manager.get_tasks(status=status, limit=limit, offset=offset)
    return tasks

@router.post("/{task_id}/start")
async def start_task(task_id: str):
    """启动任务"""
    success = await task_manager.start_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或无法启动")
    return {"success": True, "message": "任务已启动"}
```

### WebSocket 处理

```python
# src/api/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket 连接已建立: {websocket.client}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket 连接已断开: {websocket.client}")
    
    async def send_message(self, message: Dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict):
        """广播消息给所有连接"""
        disconnected = set()
        
        for websocket in self.active_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                disconnected.add(websocket)
        
        # 清理断开的连接
        for websocket in disconnected:
            self.disconnect(websocket)

manager = ConnectionManager()

async def log_handler(message: Dict):
    """日志消息处理器"""
    await manager.broadcast({
        "type": "log",
        "data": message
    })

async def task_update_handler(task_data: Dict):
    """任务更新消息处理器"""
    await manager.broadcast({
        "type": "task_update",
        "data": task_data
    })
```

## 前端开发

### 技术栈
- HTML5 + CSS3 + JavaScript (ES6+)
- Bootstrap 5 (UI 框架)
- WebSocket API (实时通信)
- Fetch API (HTTP 请求)

### 项目结构
```
src/static/
├── index.html          # 主页面
├── css/
│   ├── main.css       # 主样式
│   └── components/    # 组件样式
├── js/
│   ├── app.js         # 主应用
│   ├── api.js         # API 封装
│   ├── websocket.js   # WebSocket 处理
│   └── components/    # 组件
└── assets/            # 静态资源
```

### 前端代码示例

```javascript
// src/static/js/api.js
class API {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }
        
        const response = await fetch(url, config);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    }
    
    // 任务管理
    async getTasks(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/tasks?${query}`);
    }
    
    async createTask(taskData) {
        return this.request('/tasks', {
            method: 'POST',
            body: taskData
        });
    }
    
    async startTask(taskId) {
        return this.request(`/tasks/${taskId}/start`, {
            method: 'POST'
        });
    }
    
    // 代理管理
    async getProxyConfig() {
        return this.request('/proxy/config');
    }
    
    async updateProxyConfig(config) {
        return this.request('/proxy/config', {
            method: 'PUT',
            body: config
        });
    }
    
    // 系统状态
    async getSystemStatus() {
        return this.request('/status');
    }
}

// src/static/js/websocket.js
class WebSocketManager {
    constructor(url = 'ws://localhost:3456/api/ws') {
        this.url = url;
        this.ws = null;
        this.reconnectInterval = 5000;
        this.shouldReconnect = true;
        this.listeners = new Map();
    }
    
    connect() {
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.onopen = () => {
                console.log('WebSocket 连接成功');
                this.onConnect();
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleMessage(message);
                } catch (error) {
                    console.error('解析消息失败:', error);
                }
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket 连接关闭');
                if (this.shouldReconnect) {
                    setTimeout(() => this.connect(), this.reconnectInterval);
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket 错误:', error);
            };
        } catch (error) {
            console.error('连接 WebSocket 失败:', error);
        }
    }
    
    handleMessage(message) {
        const listeners = this.listeners.get(message.type) || [];
        listeners.forEach(callback => {
            try {
                callback(message.data);
            } catch (error) {
                console.error('处理消息回调失败:', error);
            }
        });
    }
    
    on(messageType, callback) {
        if (!this.listeners.has(messageType)) {
            this.listeners.set(messageType, []);
        }
        this.listeners.get(messageType).push(callback);
    }
    
    off(messageType, callback) {
        const listeners = this.listeners.get(messageType) || [];
        const index = listeners.indexOf(callback);
        if (index > -1) {
            listeners.splice(index, 1);
        }
    }
    
    disconnect() {
        this.shouldReconnect = false;
        if (this.ws) {
            this.ws.close();
        }
    }
}

// src/static/js/app.js
class App {
    constructor() {
        this.api = new API();
        this.ws = new WebSocketManager();
        this.currentTask = null;
        this.init();
    }
    
    async init() {
        // 初始化 WebSocket 监听
        this.ws.on('log', (data) => {
            this.appendLog(data);
        });
        
        this.ws.on('task_update', (data) => {
            this.updateTaskProgress(data);
        });
        
        this.ws.on('system_status', (data) => {
            this.updateSystemStatus(data);
        });
        
        // 连接 WebSocket
        this.ws.connect();
        
        // 加载初始数据
        await this.loadTasks();
        await this.loadSystemStatus();
        
        // 绑定事件
        this.bindEvents();
    }
    
    async loadTasks() {
        try {
            const response = await this.api.getTasks();
            this.renderTasks(response.tasks);
        } catch (error) {
            console.error('加载任务失败:', error);
        }
    }
    
    async createTask(taskData) {
        try {
            const response = await this.api.createTask(taskData);
            console.log('任务创建成功:', response);
            await this.loadTasks(); // 刷新任务列表
        } catch (error) {
            console.error('创建任务失败:', error);
            alert('创建任务失败: ' + error.message);
        }
    }
    
    renderTasks(tasks) {
        const container = document.getElementById('task-list');
        container.innerHTML = tasks.map(task => `
            <div class="task-item" data-task-id="${task.id}">
                <div class="task-info">
                    <h5>${task.name}</h5>
                    <p>进度: ${task.progress.toFixed(1)}%</p>
                </div>
                <div class="task-actions">
                    <button class="btn btn-sm btn-primary" onclick="app.startTask('${task.id}')">
                        启动
                    </button>
                    <button class="btn btn-sm btn-warning" onclick="app.pauseTask('${task.id}')">
                        暂停
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    updateTaskProgress(data) {
        const taskElement = document.querySelector(`[data-task-id="${data.task_id}"]`);
        if (taskElement) {
            const progressBar = taskElement.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = `${data.progress}%`;
                progressBar.textContent = `${data.progress.toFixed(1)}%`;
            }
        }
    }
    
    bindEvents() {
        // 绑定创建任务表单
        const createForm = document.getElementById('create-task-form');
        if (createForm) {
            createForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(createForm);
                const taskData = {
                    name: formData.get('task-name'),
                    source_path: formData.get('source-path'),
                    target_path: formData.get('target-path'),
                    organization_strategy: formData.get('organization-strategy'),
                    auto_start: formData.get('auto-start') === 'on'
                };
                await this.createTask(taskData);
            });
        }
    }
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
```

## Docker 开发

### 本地 Docker 构建
```bash
# 构建镜像
docker build -t strm-poller:dev .

# 运行容器
docker run -d \
  --name=strm-poller-dev \
  -p 3456:3456 \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -e PYTHONPATH=/app \
  strm-poller:dev
```

### Docker Compose 开发环境
```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  strm-poller:
    build: .
    ports:
      - "3456:3456"
    volumes:
      - ./src:/app/src
      - ./config.yaml:/app/config.yaml
      - ./logs:/app/logs
    environment:
      - PYTHONPATH=/app
      - LOG_LEVEL=DEBUG
      - ENV=development
    command: python -m src.main --dev
    
  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 30 --cleanup strm-poller
```

## 调试技巧

### 日志调试
```python
import logging

# 设置日志级别
logging.basicConfig(level=logging.DEBUG)

# 在代码中添加调试日志
logger.debug(f"变量值: {variable}")
logger.info("任务开始处理")
logger.warning("代理连接超时")
logger.error("刮削失败", exc_info=True)
```

### 断点调试
```python
# 使用 pdb 调试
import pdb; pdb.set_trace()

# 使用 VS Code 调试配置
# .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: 当前文件",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal"
        },
        {
            "name": "Python: FastAPI",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "src.api.main:app",
                "--reload",
                "--host", "0.0.0.0",
                "--port", "3456"
            ]
        }
    ]
}
```

### 性能分析
```python
import cProfile
import pstats

# 性能分析
cProfile.run('main_function()', 'profile_stats')

# 查看分析结果
stats = pstats.Stats('profile_stats')
stats.sort_stats('cumulative')
stats.print_stats(20)  # 显示前20个耗时函数
```

## 部署

### 生产环境部署
```bash
# 1. 构建生产镜像
docker build -t strm-poller:latest .

# 2. 推送到镜像仓库
docker tag strm-poller:latest ghcr.io/tgszy/strm-poller:latest
docker push ghcr.io/tgszy/strm-poller:latest

# 或者直接构建多架构镜像
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/tgszy/strm-poller:latest \
  --push .

# 3. 在生产环境部署
docker run -d \
  --name=strm-poller-prod \
  -p 3456:3456 \
  -v /opt/strm-poller/config:/app/config \
  -v /opt/strm-poller/logs:/app/logs \
  -e ENV=production \
  --restart=unless-stopped \
  ghcr.io/tgszy/strm-poller:latest
```

### 监控和日志
```bash
# 查看容器日志
docker logs -f strm-poller-prod

# 监控资源使用
docker stats strm-poller-prod

# 使用 systemd 管理 (可选)
sudo systemctl enable docker-container@strm-poller-prod
sudo systemctl start docker-container@strm-poller-prod
```

## 贡献指南

1. **Fork 项目**
2. **创建功能分支**: `git checkout -b feature/amazing-feature`
3. **提交更改**: `git commit -m 'Add some amazing feature'`
4. **推送到分支**: `git push origin feature/amazing-feature`
5. **创建 Pull Request**

### 提交规范
```
类型(范围): 简短描述

详细描述...

Fixes #123
```

**类型说明**:
- `feat`: 新功能
- `fix`: 修复
- `docs`: 文档
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

## 许可证

MIT License - 详见项目根目录的 LICENSE 文件