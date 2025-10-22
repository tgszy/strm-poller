# STRM Poller API 文档

## 概述

STRM Poller 提供 RESTful API 接口，用于管理任务、配置系统参数、监控状态等。

## 基础信息

- **Base URL**: `http://localhost:3456/api`
- **认证**: 当前版本无需认证
- **Content-Type**: `application/json`
- **响应格式**: JSON

## 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## API 端点

### 系统状态

#### 健康检查
```http
GET /api/health
```

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "3.0.0"
}
```

#### 系统状态
```http
GET /api/status
```

**响应示例**:
```json
{
  "cpu_usage": 15.2,
  "memory_usage": {
    "used_mb": 512,
    "total_mb": 1024,
    "percentage": 50.0
  },
  "disk_usage": {
    "used_gb": 10.5,
    "total_gb": 100.0,
    "percentage": 10.5
  },
  "uptime": "2h30m"
}
```

### 代理管理

#### 获取代理配置
```http
GET /api/proxy/config
```

**响应示例**:
```json
{
  "enabled": true,
  "type": "http",
  "host": "192.168.1.100",
  "port": 7890,
  "username": null,
  "password": null,
  "status": "connected",
  "last_check": "2024-01-01T11:55:00Z"
}
```

#### 更新代理配置
```http
PUT /api/proxy/config
```

**请求体**:
```json
{
  "enabled": true,
  "type": "http",
  "host": "192.168.1.100",
  "port": 7890,
  "username": "optional",
  "password": "optional"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "Proxy configuration updated"
}
```

#### 测试代理连接
```http
POST /api/proxy/test
```

**响应示例**:
```json
{
  "success": true,
  "response_time_ms": 150,
  "status": "connected"
}
```

### 刮削源管理

#### 获取刮削源配置
```http
GET /api/scrapers/config
```

**响应示例**:
```json
{
  "scrapers": [
    {
      "name": "tmdb",
      "enabled": true,
      "priority": 1,
      "config": {
        "api_key": "your_tmdb_api_key",
        "timeout": 30,
        "retries": 3
      },
      "status": "active"
    },
    {
      "name": "douban",
      "enabled": true,
      "priority": 2,
      "config": {
        "cookie": "your_douban_cookie",
        "timeout": 30,
        "retries": 3
      },
      "status": "active"
    }
  ],
  "scraper_order": ["tmdb", "douban", "bangumi", "imdb", "tvdb"]
}
```

#### 更新刮削源配置
```http
PUT /api/scrapers/config
```

**请求体**:
```json
{
  "scrapers": [
    {
      "name": "tmdb",
      "enabled": true,
      "priority": 1,
      "config": {
        "api_key": "your_tmdb_api_key",
        "timeout": 30,
        "retries": 3
      }
    }
  ],
  "scraper_order": ["tmdb", "douban", "bangumi", "imdb", "tvdb"]
}
```

#### 测试刮削源
```http
POST /api/scrapers/{scraper_name}/test
```

**响应示例**:
```json
{
  "success": true,
  "scraper_name": "tmdb",
  "response_time_ms": 200,
  "status": "active"
}
```

### 任务管理

#### 获取任务列表
```http
GET /api/tasks
```

**查询参数**:
- `status`: 可选，过滤任务状态 (pending, running, completed, failed, paused)
- `limit`: 可选，限制返回数量，默认 50
- `offset`: 可选，偏移量，默认 0

**响应示例**:
```json
{
  "tasks": [
    {
      "id": "task_123",
      "name": "整理电影",
      "source_path": "/src/movies",
      "target_path": "/dst/movies",
      "organization_strategy": "by_category",
      "status": "running",
      "progress": 75.5,
      "files_processed": 150,
      "total_files": 200,
      "created_at": "2024-01-01T10:00:00Z",
      "started_at": "2024-01-01T10:05:00Z",
      "estimated_completion": "2024-01-01T12:30:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### 获取任务详情
```http
GET /api/tasks/{task_id}
```

**响应示例**:
```json
{
  "id": "task_123",
  "name": "整理电影",
  "source_path": "/src/movies",
  "target_path": "/dst/movies",
  "organization_strategy": "by_category",
  "status": "running",
  "progress": 75.5,
  "files_processed": 150,
  "total_files": 200,
  "failed_files": 5,
  "retry_count": 2,
  "created_at": "2024-01-01T10:00:00Z",
  "started_at": "2024-01-01T10:05:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "estimated_completion": "2024-01-01T12:30:00Z",
  "statistics": {
    "movies": 100,
    "tv_shows": 50,
    "others": 50
  }
}
```

#### 创建任务
```http
POST /api/tasks
```

**请求体**:
```json
{
  "name": "整理电影",
  "source_path": "/src/movies",
  "target_path": "/dst/movies",
  "organization_strategy": "by_category",
  "auto_start": true
}
```

**响应示例**:
```json
{
  "success": true,
  "task_id": "task_123",
  "message": "Task created successfully"
}
```

#### 启动任务
```http
POST /api/tasks/{task_id}/start
```

**响应示例**:
```json
{
  "success": true,
  "message": "Task started"
}
```

#### 暂停任务
```http
POST /api/tasks/{task_id}/pause
```

**响应示例**:
```json
{
  "success": true,
  "message": "Task paused"
}
```

#### 取消任务
```http
POST /api/tasks/{task_id}/cancel
```

**响应示例**:
```json
{
  "success": true,
  "message": "Task cancelled"
}
```

#### 删除任务
```http
DELETE /api/tasks/{task_id}
```

**响应示例**:
```json
{
  "success": true,
  "message": "Task deleted"
}
```

#### 重试失败文件
```http
POST /api/tasks/{task_id}/retry-failed
```

**响应示例**:
```json
{
  "success": true,
  "message": "Retrying 5 failed files"
}
```

### 文件处理

#### 获取任务文件列表
```http
GET /api/tasks/{task_id}/files
```

**查询参数**:
- `status`: 可选，过滤文件状态 (pending, processing, completed, failed)
- `limit`: 可选，限制返回数量，默认 100
- `offset`: 可选，偏移量，默认 0

**响应示例**:
```json
{
  "files": [
    {
      "id": "file_123",
      "filename": "movie.strm",
      "path": "/src/movies/movie.strm",
      "status": "completed",
      "media_info": {
        "title": "Movie Title",
        "year": 2024,
        "type": "movie",
        "tmdb_id": 12345,
        "poster_url": "https://image.tmdb.org/..."
      },
      "target_path": "/dst/movies/Movie Title (2024)/movie.strm",
      "error_message": null,
      "retry_count": 0,
      "created_at": "2024-01-01T10:00:00Z",
      "updated_at": "2024-01-01T10:05:00Z"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### 系统设置

#### 获取系统设置
```http
GET /api/settings
```

**响应示例**:
```json
{
  "max_memory_mb": 1024,
  "warning_threshold": 0.8,
  "critical_threshold": 0.95,
  "log_level": "INFO",
  "max_concurrent_tasks": 3,
  "retry_limit": 3,
  "retry_interval_hours": 24
}
```

#### 更新系统设置
```http
PUT /api/settings
```

**请求体**:
```json
{
  "max_memory_mb": 2048,
  "warning_threshold": 0.8,
  "critical_threshold": 0.95,
  "log_level": "DEBUG",
  "max_concurrent_tasks": 5,
  "retry_limit": 3,
  "retry_interval_hours": 24
}
```

### 日志管理

#### 获取系统日志
```http
GET /api/logs
```

**查询参数**:
- `level`: 可选，日志级别 (DEBUG, INFO, WARNING, ERROR)
- `limit`: 可选，限制返回数量，默认 100
- `offset`: 可选，偏移量，默认 0

**响应示例**:
```json
{
  "logs": [
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "level": "INFO",
      "message": "Task task_123 started",
      "module": "task_manager",
      "task_id": "task_123"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

#### 获取任务日志
```http
GET /api/tasks/{task_id}/logs
```

**查询参数**:
- `level`: 可选，日志级别
- `limit`: 可选，限制返回数量
- `offset`: 可选，偏移量

#### 清空日志
```http
DELETE /api/logs
```

**响应示例**:
```json
{
  "success": true,
  "message": "Logs cleared"
}
```

### WebSocket 接口

#### 实时日志推送
```
ws://localhost:3456/api/ws/logs
```

**消息格式**:
```json
{
  "type": "log",
  "data": {
    "timestamp": "2024-01-01T12:00:00Z",
    "level": "INFO",
    "message": "Task progress: 75%",
    "task_id": "task_123"
  }
}
```

#### 任务状态推送
```
ws://localhost:3456/api/ws/tasks
```

**消息格式**:
```json
{
  "type": "task_update",
  "data": {
    "task_id": "task_123",
    "status": "running",
    "progress": 75.5,
    "files_processed": 150,
    "total_files": 200
  }
}
```

#### 系统状态推送
```
ws://localhost:3456/api/ws/system
```

**消息格式**:
```json
{
  "type": "system_status",
  "data": {
    "cpu_usage": 15.2,
    "memory_usage": 50.0,
    "disk_usage": 10.5,
    "active_tasks": 2
  }
}
```

## 错误处理

### 错误响应格式
```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task not found",
    "details": "Task with ID task_999 does not exist"
  }
}
```

### 常见错误码

| 错误码 | 说明 |
|--------|------|
| `INVALID_REQUEST` | 请求参数无效 |
| `TASK_NOT_FOUND` | 任务不存在 |
| `TASK_ALREADY_RUNNING` | 任务已在运行中 |
| `PROXY_CONNECTION_FAILED` | 代理连接失败 |
| `SCRAPER_CONFIG_INVALID` | 刮削源配置无效 |
| `MEMORY_LIMIT_EXCEEDED` | 内存限制超出 |
| `INTERNAL_ERROR` | 服务器内部错误 |

## 使用示例

### Python 示例
```python
import requests
import json

# 基础配置
base_url = "http://localhost:3456/api"
headers = {"Content-Type": "application/json"}

# 创建任务
task_data = {
    "name": "整理电影",
    "source_path": "/src/movies",
    "target_path": "/dst/movies",
    "organization_strategy": "by_category",
    "auto_start": True
}

response = requests.post(
    f"{base_url}/tasks",
    headers=headers,
    data=json.dumps(task_data)
)

if response.status_code == 200:
    result = response.json()
    task_id = result["task_id"]
    print(f"任务创建成功: {task_id}")
else:
    print(f"错误: {response.status_code} - {response.text}")

# 获取任务状态
response = requests.get(f"{base_url}/tasks/{task_id}")
if response.status_code == 200:
    task_info = response.json()
    print(f"任务进度: {task_info['progress']}%")
```

### JavaScript 示例
```javascript
// WebSocket 连接示例
const ws = new WebSocket('ws://localhost:3456/api/ws/logs');

ws.onopen = function() {
    console.log('WebSocket 连接成功');
};

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    console.log('收到消息:', message);
    
    if (message.type === 'task_update') {
        const taskData = message.data;
        console.log(`任务 ${taskData.task_id} 进度: ${taskData.progress}%`);
    }
};

ws.onerror = function(error) {
    console.error('WebSocket 错误:', error);
};

// API 调用示例
async function createTask() {
    const taskData = {
        name: "整理电影",
        source_path: "/src/movies",
        target_path: "/dst/movies",
        organization_strategy: "by_category",
        auto_start: true
    };

    try {
        const response = await fetch('http://localhost:3456/api/tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(taskData)
        });

        const result = await response.json();
        console.log('任务创建成功:', result);
        return result.task_id;
    } catch (error) {
        console.error('创建任务失败:', error);
    }
}
```

### cURL 示例
```bash
# 获取系统状态
curl -X GET http://localhost:3456/api/status

# 创建任务
curl -X POST http://localhost:3456/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "整理电影",
    "source_path": "/src/movies",
    "target_path": "/dst/movies",
    "organization_strategy": "by_category",
    "auto_start": true
  }'

# 启动任务
curl -X POST http://localhost:3456/api/tasks/task_123/start

# 获取任务状态
curl -X GET http://localhost:3456/api/tasks/task_123
```

## 版本历史

### v3.0.0
- 初始 API 版本
- 支持任务管理、代理配置、刮削源管理
- WebSocket 实时推送
- 完整的错误处理机制