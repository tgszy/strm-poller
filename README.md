# STRM Poller - 飞牛NAS Docker版

一个轻量化的媒体预处理服务，专为飞牛NAS设计，支持实时扫描.strm文件、自动整理和刮削元数据。

## 🌟 功能特性

- 🚀 **实时监控**: watchdog实时监听，增/改/移动事件≤1秒响应
- 📁 **智能整理**: 支持分类别、分类型、不整理三种策略  
- 🎬 **多源刮削**: TMDB→豆瓣→Bangumi→IMDb→TVDB，支持拖拽排序和自动回退
- 🌐 **代理支持**: 支持http/https/socks5代理，统一出口
- 📺 **电视剧支持**: 自动识别季/集目录结构
- 🔄 **多任务管理**: 支持创建、启动、暂停、取消任务
- 🔄 **失败重试**: 24小时内最多3次自动重试
- 💾 **内存限制**: 用户可设上限，容器内RLIMIT_AS + Docker -m双保险
- 🌐 **WebUI控制台**: 三栏式响应式设计，实时日志推送
- 📊 **系统监控**: 实时内存使用监控和告警
- 🔧 **灵活配置**: 支持环境变量和配置文件双重配置

## 🚀 快速开始

### Docker运行（推荐）

```bash
docker run -d \
  --name=strm-poller \
  -p 3456:3456 \
  -v /mnt/user/appdata/strm-poller:/config \
  -v /mnt/user/aliyun:/src:ro \
  -v /mnt/user/emby:/dst \
  -e PUID=1000 -e PGID=1000 -e TZ=Asia/Shanghai \
  -e PROXY_ENABLED=true \
  -e PROXY_TYPE=http \
  -e PROXY_HOST=192.168.1.100 \
  -e PROXY_PORT=7890 \
  --memory=1g --memory-swap=1g \
  --restart=unless-stopped \
  ghcr.io/yourname/strm-poller:latest
```

### Docker Compose（推荐）

```yaml
version: '3.8'

services:
  strm-poller:
    image: ghcr.io/yourname/strm-poller:latest
    container_name: strm-poller
    ports:
      - "3456:3456"
    volumes:
      - /mnt/user/appdata/strm-poller:/config
      - /mnt/user/aliyun:/src:ro
      - /mnt/user/emby:/dst
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Asia/Shanghai
      - PROXY_ENABLED=true
      - PROXY_TYPE=http
      - PROXY_HOST=192.168.1.100
      - PROXY_PORT=7890
      - MAX_MEMORY_MB=1024
      - SCRAPER_ORDER=tmdb,douban,bangumi,imdb,tvdb
      - LOG_LEVEL=INFO
    mem_limit: 1g
    memswap_limit: 1g
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3456/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## 📁 路径映射建议

```
/mnt/user/
├─ appdata/strm-poller/   → 配置、数据库、日志
├─ aliyun/strm_unsort/    → 源.strm文件（只读）
└─ emby/library/          → 整理后媒体库
```

## ⚙️ 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PUID` | 1000 | 用户ID |
| `PGID` | 1000 | 用户组ID |
| `TZ` | Asia/Shanghai | 时区 |
| `PROXY_ENABLED` | false | 是否启用代理 |
| `PROXY_TYPE` | http | 代理类型: http/https/socks5 |
| `PROXY_HOST` | localhost | 代理服务器地址 |
| `PROXY_PORT` | 8080 | 代理端口 |
| `PROXY_USERNAME` | - | 代理用户名（可选） |
| `PROXY_PASSWORD` | - | 代理密码（可选） |
| `MAX_MEMORY_MB` | 1024 | 内存限制（MB） |
| `SCRAPER_ORDER` | tmdb,douban,bangumi,imdb,tvdb | 刮削源优先级 |
| `LOG_LEVEL` | INFO | 日志级别 |

## 🔑 刮削源配置

### TMDB配置
1. 访问 [TMDB](https://www.themoviedb.org/settings/api)
2. 注册账号并登录
3. 进入 Settings → API → Create Key
4. 复制 API Key 到配置中

### 豆瓣配置
1. 登录豆瓣账号
2. 按 F12 打开开发者工具
3. 进入 Application → Cookies
4. 复制 `dbcl2` 和 `ck` 的值

### Bangumi配置
1. 访问 [Bangumi](https://bgm.tv/)
2. 注册账号并登录
3. 进入个人设置 → API
4. 申请 API Key

### IMDb配置（可选）
1. 登录 IMDb 账号（可选）
2. 如需要，复制 Cookie 中的相关值

### TVDB配置
1. 访问 [TVDB](https://thetvdb.com/)
2. 注册账号并登录
3. 进入 Account → API Keys
4. 创建新的 API Key

## 🌐 WebUI使用指南

### 首次使用
1. 访问 `http://<NAS_IP>:3456`
2. 首次打开自动弹出「全局设置」向导
3. 配置代理地址并测试连接
4. 添加刮削源 API Key
5. 创建第一个整理任务

### 主界面功能
- **仪表盘**: 显示系统状态、任务统计、刮削源状态
- **任务管理**: 创建、启动、暂停、删除任务
- **刮削源配置**: 管理多个刮削源的启用状态和优先级
- **系统设置**: 代理配置、内存限制、系统参数
- **日志查看**: 实时查看系统日志和任务日志

### 创建任务步骤
1. 点击「新建任务」
2. 输入任务名称
3. 选择源路径（包含 .strm 文件的目录）
4. 选择目标路径（整理后的媒体库存放位置）
5. 选择整理策略（分类别/分类型/不整理）
6. 点击「创建并启动」

## 🔧 高级配置

### 代理配置示例

#### HTTP代理
```yaml
environment:
  - PROXY_ENABLED=true
  - PROXY_TYPE=http
  - PROXY_HOST=192.168.1.100
  - PROXY_PORT=7890
```

#### SOCKS5代理
```yaml
environment:
  - PROXY_ENABLED=true
  - PROXY_TYPE=socks5
  - PROXY_HOST=127.0.0.1
  - PROXY_PORT=1080
```

#### 带认证的代理
```yaml
environment:
  - PROXY_ENABLED=true
  - PROXY_TYPE=http
  - PROXY_HOST=proxy.example.com
  - PROXY_PORT=8080
  - PROXY_USERNAME=myuser
  - PROXY_PASSWORD=mypass
```

### 内存限制配置

```yaml
environment:
  - MAX_MEMORY_MB=2048  # 2GB内存限制
  - WARNING_THRESHOLD=0.8  # 80%警告阈值
  - CRITICAL_THRESHOLD=0.95  # 95%严重阈值
```

### 刮削源优先级配置

```yaml
environment:
  - SCRAPER_ORDER=tmdb,douban,bangumi,imdb,tvdb
```

## 📊 系统监控

### 内存监控
- 实时监控内存使用情况
- 超过警告阈值时发送告警
- 超过严重阈值时自动清理缓存

### 代理监控
- 定期测试代理连接状态
- 代理失效时自动切换直连
- 记录代理使用统计

### 任务监控
- 实时监控任务执行状态
- 失败文件自动重试机制
- 任务进度实时推送

## 🛠️ 开发指南

### 环境搭建
```bash
# 克隆项目
git clone https://github.com/yourname/strm-poller.git
cd strm-poller

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
python -m src.main
```

### 项目结构
```
src/
├── api/          # FastAPI接口
├── core/         # 核心业务逻辑
├── services/     # 监控服务
├── static/       # WebUI静态文件
└── utils/        # 工具函数
```

### 构建Docker镜像
```bash
# 构建镜像
docker build -t strm-poller:latest .

# 多架构构建
./build.sh
```

## 🔍 故障排除

### 常见问题

#### 1. 刮削失败
- 检查网络连接和代理设置
- 验证API Key是否有效
- 查看日志了解具体错误

#### 2. 内存使用过高
- 调整 `MAX_MEMORY_MB` 参数
- 检查是否有内存泄漏
- 重启容器释放内存

#### 3. 任务卡住
- 检查源路径是否有大量文件
- 查看系统资源使用情况
- 重启任务或容器

#### 4. WebUI无法访问
- 检查端口映射是否正确
- 确认防火墙设置
- 查看容器日志

### 日志查看
```bash
# 查看容器日志
docker logs strm-poller

# 实时查看日志
docker logs -f strm-poller

# 查看最后100行日志
docker logs --tail 100 strm-poller
```

## 📈 性能优化

### 系统要求
- **CPU**: 空闲<5%，全量扫<30%
- **内存**: 默认≤1GB（用户可调）
- **磁盘**: 仅写NFO/图片，无转码
- **网络**: 刮削源走代理，支持局域网socks5

### 优化建议
1. 合理设置内存限制
2. 使用SSD存储配置和数据库
3. 定期清理日志文件
4. 合理设置任务并发数

## 📝 版本历史

### v3.0.0 (当前版本)
- ✨ 初始版本发布
- 🎬 支持多源刮削（TMDB、豆瓣、Bangumi、IMDb、TVDB）
- 🌐 完整的代理支持（HTTP/HTTPS/SOCKS5）
- 💾 内存限制和监控功能
- 🌐 现代化的WebUI界面
- 🔄 实时任务管理
- 📊 系统监控和告警

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 支持

- 💬 [GitHub Issues](https://github.com/yourname/strm-poller/issues)
- 📧 邮箱: your-email@example.com
- 💭 讨论区: [GitHub Discussions](https://github.com/yourname/strm-poller/discussions)

---

⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！