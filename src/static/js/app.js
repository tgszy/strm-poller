// WebSocket连接和API客户端
class APIClient {
    constructor() {
        this.ws = null;
        this.wsReconnectInterval = 5000;
        this.wsMaxReconnectAttempts = 5;
        this.wsReconnectAttempts = 0;
        this.baseURL = window.location.origin;
        this.reconnectTimeout = null;
        this.initWebSocket();
    }

    initWebSocket() {
        // 根据当前页面协议自动选择ws或wss
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
        console.log('正在连接WebSocket:', wsUrl);
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket连接已建立');
                this.wsReconnectAttempts = 0;
                this.showNotification('WebSocket连接已建立', 'success');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (e) {
                    console.error('WebSocket消息解析失败:', e, '原始消息:', event.data);
                }
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket连接已关闭:', event.code, event.reason);
                this.reconnectWebSocket();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket错误:', error);
                this.showNotification('WebSocket连接错误，正在重试...', 'error');
            };
        } catch (e) {
            console.error('创建WebSocket连接失败:', e);
            this.showNotification('无法创建WebSocket连接', 'error');
            // 确保触发重连机制
            setTimeout(() => {
                this.reconnectWebSocket();
            }, 1000);
        }
    }

    reconnectWebSocket() {
        if (this.wsReconnectAttempts < this.wsMaxReconnectAttempts) {
            this.wsReconnectAttempts++;
            // 使用指数退避策略，避免频繁重连
            const delay = Math.min(1000 * Math.pow(2, this.wsReconnectAttempts - 1), 30000); // 最大30秒
            console.log(`WebSocket重连尝试 ${this.wsReconnectAttempts}/${this.wsMaxReconnectAttempts}，延迟${delay}ms...`);
            
            // 清除之前可能存在的重连计时器
            if (this.reconnectTimeout) {
                clearTimeout(this.reconnectTimeout);
            }
            
            this.reconnectTimeout = setTimeout(() => {
                // 确保之前的连接已关闭
                if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
                    try {
                        this.ws.close();
                    } catch (e) {
                        console.error('关闭旧WebSocket连接失败:', e);
                    }
                }
                this.initWebSocket();
            }, delay);
        } else {
            console.log('WebSocket重连失败，已达到最大重试次数');
            this.showNotification('WebSocket连接失败，请刷新页面重试', 'error');
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'log':
                this.appendLog(data.message, data.level);
                break;
            case 'task_update':
                this.updateTaskStatus(data.task);
                break;
            case 'stats_update':
                this.updateStats(data.stats);
                break;
            default:
                console.log('未知消息类型:', data.type);
        }
    }

    async request(endpoint, options = {}, retryCount = 0) {
        const MAX_RETRIES = 2;
        const TIMEOUT = 10000; // 10秒超时
        const url = `${this.baseURL}/api${endpoint}`;
        
        try {
            // 添加超时处理
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), TIMEOUT);
            
            const config = {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                signal: controller.signal
            };

            console.log('正在请求API:', url);
            const response = await fetch(url, config);
            
            clearTimeout(timeoutId); // 清除超时
            
            // 检查响应状态
            if (!response.ok) {
                // 尝试解析错误详情
                let errorDetail = `请求失败，状态码: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorDetail = errorData.detail || errorDetail;
                } catch {
                    // 如果无法解析JSON，读取文本内容
                    try {
                        const text = await response.text();
                        if (text) {
                            errorDetail = `${errorDetail} - ${text}`;
                        }
                    } catch {
                        // 忽略文本读取错误
                    }
                }
                throw new Error(errorDetail);
            }
            
            // 解析成功响应
            const data = await response.json();
            return data;
        } catch (error) {
            if (error.name === 'AbortError') {
                console.error('API请求超时:', endpoint);
                this.showNotification('API请求超时，服务可能不可用', 'error');
                throw new Error('API请求超时');
            }
            
            console.error(`API请求错误: ${error.message}`);
            
            // 重试逻辑 - 仅对网络错误重试
            if (retryCount < MAX_RETRIES && !error.message.includes('请求失败') && !error.message.includes('响应解析失败')) {
                retryCount++;
                const delay = 1000 * Math.pow(2, retryCount - 1);
                console.log(`尝试重试请求 (${retryCount}/${MAX_RETRIES})，延迟${delay}ms...`);
                
                await new Promise(resolve => setTimeout(resolve, delay));
                return this.request(endpoint, options, retryCount);
            }
            
            // 显示用户友好的错误消息
            this.showNotification(`API请求失败: ${error.message}`, 'error');
            throw error;
        }
    }

    // 任务管理API
    async getTasks() {
        return this.request('/tasks');
    }

    async createTask(taskData) {
        return this.request('/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });
    }

    async startTask(taskId) {
        return this.request(`/tasks/${taskId}/start`, { method: 'POST' });
    }

    async pauseTask(taskId) {
        return this.request(`/tasks/${taskId}/pause`, { method: 'POST' });
    }

    async cancelTask(taskId) {
        return this.request(`/tasks/${taskId}/cancel`, { method: 'POST' });
    }

    async retryTask(taskId) {
        return this.request(`/tasks/${taskId}/retry`, { method: 'POST' });
    }

    async deleteTask(taskId) {
        return this.request(`/tasks/${taskId}`, { method: 'DELETE' });
    }

    // 刮削源配置API
    async getScrapers() {
        return this.request('/scraper-configs');
    }

    async updateScraper(scraperName, config) {
        // 首先获取所有刮削源配置，找到对应名称的配置ID
        const scrapers = await this.getScrapers();
        const scraper = scrapers.find(s => s.name === scraperName);
        if (!scraper) {
            throw new Error(`刮削源 ${scraperName} 不存在`);
        }
        
        return this.request(`/scraper-configs/${scraper.id}`, {
            method: 'PUT',
            body: JSON.stringify(config)
        });
    }

    async testScraper(scraperName) {
        // 刮削源测试功能需要后端支持，暂时返回成功
        return { success: true, message: '刮削源测试功能暂未实现' };
    }

    async updateScrapersPriority(updates) {
        // 批量更新刮削源优先级
        return this.request('/scrapers/priority', {
            method: 'PUT',
            body: JSON.stringify({ updates: updates })
        });
    }

    // 系统设置API
    async getSettings() {
        const configs = await this.request('/system-configs');
        // 将配置数组转换为对象格式
        const settings = {};
        configs.forEach(config => {
            settings[config.key] = config.value;
        });
        return settings;
    }

    async updateSettings(settings) {
        // 将设置对象转换为配置数组格式
        const configUpdates = Object.entries(settings).map(([key, value]) => ({
            key: key,
            value: value,
            description: `系统设置: ${key}`
        }));
        
        // 批量更新配置
        const results = [];
        for (const config of configUpdates) {
            const result = await this.request('/system-configs', {
                method: 'PUT',
                body: JSON.stringify(config)
            });
            results.push(result);
        }
        return results;
    }

    async testProxy(proxyUrl) {
        return this.request('/proxy/test', {
            method: 'POST',
            body: JSON.stringify({ proxy_url: proxyUrl })
        });
    }

    // 统计信息API
    async getStats() {
        // 获取系统统计信息和任务统计信息
        const [systemStats, taskStats] = await Promise.all([
            this.request('/stats/system'),
            this.request('/stats/tasks')
        ]);
        
        // 合并统计信息
        return {
            ...systemStats,
            ...taskStats
        };
    }

    // 日志API
    async getLogs(level = null, limit = 100) {
        // 日志功能暂未实现，返回空数组
        return [];
    }

    async clearLogs() {
        // 日志功能暂未实现，返回成功
        return { success: true, message: '日志功能暂未实现' };
    }

    // 工具方法
    appendLog(message, level = 'info') {
        const logTerminal = document.getElementById('log-terminal');
        const fullLogTerminal = document.getElementById('full-log-terminal');
        
        if (logTerminal) {
            this.addLogEntry(logTerminal, message, level);
        }
        
        if (fullLogTerminal) {
            this.addLogEntry(fullLogTerminal, message, level);
        }
    }

    addLogEntry(container, message, level) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${level}`;
        logEntry.innerHTML = `[${timestamp}] ${message}`;
        
        if (container.children.length === 1 && container.children[0].classList.contains('text-muted')) {
            container.innerHTML = '';
        }
        
        container.appendChild(logEntry);
        container.scrollTop = container.scrollHeight;
    }

    updateTaskStatus(task) {
        // 更新任务状态显示
        const taskElement = document.querySelector(`[data-task-id="${task.id}"]`);
        if (taskElement) {
            const statusBadge = taskElement.querySelector('.status-badge');
            const progressBar = taskElement.querySelector('.progress-bar');
            
            if (statusBadge) {
                statusBadge.className = `status-badge status-${task.status}`;
                statusBadge.textContent = this.getStatusText(task.status);
            }
            
            if (progressBar) {
                progressBar.style.width = `${task.progress || 0}%`;
                progressBar.textContent = `${task.progress || 0}%`;
            }
        }
    }

    updateStats(stats) {
        // 更新统计信息
        const elements = {
            'total-tasks': stats.total_tasks,
            'running-tasks': stats.running_tasks,
            'completed-tasks': stats.completed_tasks,
            'failed-tasks': stats.failed_tasks,
            'cpu-usage': `${stats.cpu_usage}%`,
            'memory-usage': `${stats.memory_usage}%`,
            'disk-usage': `${stats.disk_usage}%`
        };

        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        });

        // 更新进度条
        const progressBars = {
            'cpu-progress': stats.cpu_usage,
            'memory-progress': stats.memory_usage,
            'disk-progress': stats.disk_usage
        };

        Object.entries(progressBars).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.style.width = `${value}%`;
            }
        });
    }

    getStatusText(status) {
        const statusMap = {
            'pending': '待处理',
            'running': '运行中',
            'paused': '已暂停',
            'completed': '已完成',
            'failed': '失败',
            'cancelled': '已取消'
        };
        return statusMap[status] || status;
    }

    showNotification(message, type = 'info') {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }
}

// 页面管理器
class PageManager {
    constructor(apiClient) {
        this.api = apiClient;
        this.currentPage = 'dashboard';
        this.refreshInterval = null;
        this.init();
    }

    init() {
        this.setupNavigation();
        this.setupEventListeners();
        this.loadDashboard();
        this.startAutoRefresh();
    }

    setupNavigation() {
        const navLinks = document.querySelectorAll('[data-page]');
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = link.getAttribute('data-page');
                this.switchPage(page);
            });
        });
    }

    setupEventListeners() {
        // 刷新按钮
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.loadCurrentPage();
        });

        // 任务表单
        document.getElementById('create-task-btn').addEventListener('click', () => {
            this.createTask();
        });

        // 代理测试
        document.getElementById('test-proxy-btn').addEventListener('click', () => {
            this.testProxy();
        });

        // 代理表单
        document.getElementById('proxy-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveProxySettings();
        });

        // 系统设置表单
        document.getElementById('system-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveSystemSettings();
        });

        // 日志操作
        document.getElementById('clear-logs-btn').addEventListener('click', () => {
            this.clearLogs();
        });

        document.getElementById('export-logs-btn').addEventListener('click', () => {
            this.exportLogs();
        });

        // 通知设置表单
        document.getElementById('notifications-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveNotificationSettings();
        });

        // 规则设置表单
        document.getElementById('subcategory-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveRuleSettings();
        });

        document.getElementById('rename-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveRuleSettings();
        });

        // 默认策略和格式加载按钮
        document.getElementById('load-default-strategy').addEventListener('click', () => {
            this.loadDefaultSubcategoryStrategy();
        });

        document.getElementById('load-movie-default').addEventListener('click', () => {
            this.loadDefaultMovieFormat();
        });

        document.getElementById('load-tv-default').addEventListener('click', () => {
            this.loadDefaultTVFormat();
        });

        // 重置按钮
        document.getElementById('reset-strategy').addEventListener('click', () => {
            document.getElementById('subcategory-strategy').value = '';
        });

        document.getElementById('reset-movie-format').addEventListener('click', () => {
            document.getElementById('movie-rename-format').value = '';
        });

        document.getElementById('reset-tv-format').addEventListener('click', () => {
            document.getElementById('tv-show-format').value = '';
            document.getElementById('tv-season-format').value = '';
            document.getElementById('tv-episode-format').value = '';
        });
        
        // 刮削源配置模态框事件监听器
        document.getElementById('scraper-config-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveScraperConfig();
        });
        
        document.getElementById('test-scraper-btn').addEventListener('click', () => {
            this.testScraperConnection();
        });
        
        document.getElementById('scraper-help-btn').addEventListener('click', () => {
            if (this.currentScraper) {
                const scraperType = this.currentScraper.type || this.currentScraper.name.toLowerCase();
                this.showScraperHelp(scraperType);
            }
        });
        
        // 帮助按钮事件监听器
        document.addEventListener('click', (e) => {
            if (e.target.closest('[data-help]')) {
                const helpType = e.target.closest('[data-help]').dataset.help;
                this.showScraperHelp(helpType);
            }
        });
    }

    switchPage(page) {
        // 更新导航状态
        document.querySelectorAll('.sidebar .nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.querySelector(`[data-page="${page}"]`).classList.add('active');

        // 隐藏所有页面
        document.querySelectorAll('.page-content').forEach(content => {
            content.style.display = 'none';
        });

        // 显示目标页面
        const pageElement = document.getElementById(`${page}-page`);
        if (pageElement) {
            pageElement.style.display = 'block';
        }

        // 更新页面标题
        const titles = {
            'dashboard': '仪表盘',
            'tasks': '任务管理',
            'scrapers': '刮削源',
            'settings': '系统设置',
            'logs': '日志查看',
            'notifications': '通知设置',
            'rules': '规则设置'
        };
        document.getElementById('page-title').textContent = titles[page];

        this.currentPage = page;
        this.loadCurrentPage();
    }

    loadCurrentPage() {
        switch (this.currentPage) {
            case 'dashboard':
                this.loadDashboard();
                break;
            case 'tasks':
                this.loadTasks();
                break;
            case 'scrapers':
                this.loadScrapers();
                break;
            case 'settings':
                this.loadSettings();
                break;
            case 'logs':
                this.loadLogs();
                break;
            case 'notifications':
                this.loadNotifications();
                break;
            case 'rules':
                this.loadRules();
                break;
        }
    }

    async loadDashboard() {
        try {
            const stats = await this.api.getStats();
            this.api.updateStats(stats);
        } catch (error) {
            console.error('加载仪表盘数据失败:', error);
        }
    }

    async loadTasks() {
        try {
            const tasks = await this.api.getTasks();
            this.renderTasksTable(tasks);
        } catch (error) {
            console.error('加载任务列表失败:', error);
        }
    }

    renderTasksTable(tasks) {
        const tbody = document.getElementById('tasks-table-body');
        if (!tbody) return;

        if (tasks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暂无任务</td></tr>';
            return;
        }

        tbody.innerHTML = tasks.map(task => `
            <tr data-task-id="${task.id}">
                <td>
                    <strong>${task.name}</strong>
                    <br><small class="text-muted">${task.source_path}</small>
                </td>
                <td>
                    <span class="status-badge status-${task.status}">
                        ${this.api.getStatusText(task.status)}
                    </span>
                </td>
                <td>
                    <div class="progress" style="height: 8px;">
                        <div class="progress-bar" style="width: ${task.progress || 0}%">
                            ${task.progress || 0}%
                        </div>
                    </div>
                </td>
                <td>
                    ${task.processed_files || 0} / ${task.total_files || 0}
                </td>
                <td>
                    <small>${new Date(task.created_at).toLocaleString()}</small>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        ${this.getTaskActionButtons(task)}
                    </div>
                </td>
            </tr>
        `).join('');

        // 绑定任务操作事件
        tasks.forEach(task => {
            const row = tbody.querySelector(`[data-task-id="${task.id}"]`);
            if (row) {
                this.bindTaskActions(row, task);
            }
        });
    }

    getTaskActionButtons(task) {
        const buttons = [];
        
        switch (task.status) {
            case 'pending':
                buttons.push(`<button class="btn btn-outline-success btn-sm" data-action="start">开始</button>`);
                buttons.push(`<button class="btn btn-outline-danger btn-sm" data-action="cancel">取消</button>`);
                break;
            case 'running':
                buttons.push(`<button class="btn btn-outline-warning btn-sm" data-action="pause">暂停</button>`);
                buttons.push(`<button class="btn btn-outline-danger btn-sm" data-action="cancel">取消</button>`);
                break;
            case 'paused':
                buttons.push(`<button class="btn btn-outline-success btn-sm" data-action="resume">继续</button>`);
                buttons.push(`<button class="btn btn-outline-danger btn-sm" data-action="cancel">取消</button>`);
                break;
            case 'failed':
                buttons.push(`<button class="btn btn-outline-warning btn-sm" data-action="retry">重试</button>`);
                buttons.push(`<button class="btn btn-outline-danger btn-sm" data-action="delete">删除</button>`);
                break;
            case 'completed':
                buttons.push(`<button class="btn btn-outline-info btn-sm" data-action="view">查看</button>`);
                buttons.push(`<button class="btn btn-outline-danger btn-sm" data-action="delete">删除</button>`);
                break;
            default:
                buttons.push(`<button class="btn btn-outline-danger btn-sm" data-action="delete">删除</button>`);
        }
        
        return buttons.join('');
    }

    bindTaskActions(row, task) {
        const buttons = row.querySelectorAll('[data-action]');
        buttons.forEach(button => {
            button.addEventListener('click', async () => {
                const action = button.getAttribute('data-action');
                await this.handleTaskAction(task.id, action);
            });
        });
    }

    async handleTaskAction(taskId, action) {
        try {
            switch (action) {
                case 'start':
                case 'resume':
                    await this.api.startTask(taskId);
                    this.api.showNotification('任务已开始', 'success');
                    break;
                case 'pause':
                    await this.api.pauseTask(taskId);
                    this.api.showNotification('任务已暂停', 'warning');
                    break;
                case 'cancel':
                    await this.api.cancelTask(taskId);
                    this.api.showNotification('任务已取消', 'info');
                    break;
                case 'retry':
                    await this.api.retryTask(taskId);
                    this.api.showNotification('任务已重试', 'success');
                    break;
                case 'delete':
                    if (confirm('确定要删除此任务吗？')) {
                        await this.api.deleteTask(taskId);
                        this.api.showNotification('任务已删除', 'success');
                    }
                    break;
            }
            
            // 刷新任务列表
            setTimeout(() => this.loadTasks(), 500);
        } catch (error) {
            console.error(`任务操作失败: ${action}`, error);
            this.api.showNotification(`操作失败: ${error.message}`, 'error');
        }
    }

    async createTask() {
        const form = document.getElementById('task-form');
        const formData = new FormData(form);
        
        const taskData = {
            name: document.getElementById('task-name').value,
            source_path: document.getElementById('source-path').value,
            destination_path: document.getElementById('destination-path').value,
            organize_strategy: document.getElementById('organize-strategy').value
        };

        try {
            await this.api.createTask(taskData);
            this.api.showNotification('任务创建成功', 'success');
            
            // 关闭模态框
            const modal = bootstrap.Modal.getInstance(document.getElementById('taskModal'));
            modal.hide();
            
            // 重置表单
            form.reset();
            
            // 刷新任务列表
            this.loadTasks();
        } catch (error) {
            console.error('创建任务失败:', error);
            this.api.showNotification(`创建任务失败: ${error.message}`, 'error');
        }
    }

    async loadScrapers() {
        try {
            const scrapers = await this.api.getScrapers();
            this.renderScrapersList(scrapers);
        } catch (error) {
            console.error('加载刮削源失败:', error);
        }
    }

    renderScrapersList(scrapers) {
        const container = document.getElementById('scrapers-list');
        if (!container) return;

        // 按优先级排序（升序：优先级0在最前面，优先级4在最后面）
        const sortedScrapers = [...scrapers].sort((a, b) => (a.priority || 0) - (b.priority || 0));

        container.innerHTML = `
            <div class="mb-3">
                <p class="text-muted">点击卡片打开刮削源配置界面，拖拽调整优先级</p>
                <div class="row" id="scrapers-sortable">
                    ${sortedScrapers.map(scraper => this.renderScraperItem(scraper)).join('')}
                </div>
            </div>
        `;

        // 绑定刮削源操作事件和卡片点击事件
        sortedScrapers.forEach(scraper => {
            const item = container.querySelector(`[data-scraper="${scraper.name}"]`);
            if (item) {
                this.bindScraperActions(item, scraper);
                
                // 添加点击卡片打开配置的功能
                item.addEventListener('click', (e) => {
                    // 防止按钮点击事件冒泡
                    if (!e.target.closest('[data-action]')) {
                        this.showScraperConfigModal(scraper);
                    }
                });
                
                // 添加悬停效果
                item.style.cursor = 'pointer';
                item.addEventListener('mouseenter', () => {
                    item.style.transform = 'translateY(-2px)';
                    item.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
                    item.style.transition = 'all 0.2s ease';
                });
                item.addEventListener('mouseleave', () => {
                    item.style.transform = 'translateY(0)';
                    item.style.boxShadow = 'none';
                });
            }
        });

        // 初始化拖动排序功能
        this.initDragAndDrop();
    }

    initDragAndDrop() {
        const container = document.getElementById('scrapers-sortable');
        if (!container) return;

        const items = container.querySelectorAll('.scraper-item');
        let draggedItem = null;

        // 为每个刮削源项添加拖动事件
        items.forEach(item => {
            // 拖动开始
            item.addEventListener('dragstart', (e) => {
                draggedItem = item;
                item.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', item.getAttribute('data-scraper'));
            });

            // 拖动结束
            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
                items.forEach(i => i.classList.remove('drag-over'));
                draggedItem = null;
            });

            // 拖动经过
            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                
                if (draggedItem && draggedItem !== item) {
                    const rect = item.getBoundingClientRect();
                    const next = (e.clientY - rect.top) / rect.height > 0.5;
                    
                    items.forEach(i => i.classList.remove('drag-over'));
                    item.classList.add('drag-over');
                }
            });

            // 拖动进入
            item.addEventListener('dragenter', (e) => {
                e.preventDefault();
                if (draggedItem && draggedItem !== item) {
                    item.classList.add('drag-over');
                }
            });

            // 拖动离开
            item.addEventListener('dragleave', () => {
                item.classList.remove('drag-over');
            });

            // 放置
            item.addEventListener('drop', (e) => {
                e.preventDefault();
                if (draggedItem && draggedItem !== item) {
                    const rect = item.getBoundingClientRect();
                    const next = (e.clientY - rect.top) / rect.height > 0.5;
                    
                    if (next) {
                        container.insertBefore(draggedItem, item.nextSibling);
                    } else {
                        container.insertBefore(draggedItem, item);
                    }
                    
                    // 更新优先级
                    this.updateScrapersPriority();
                }
                item.classList.remove('drag-over');
            });
        });
    }

    async updateScrapersPriority() {
        const container = document.getElementById('scrapers-sortable');
        if (!container) return;

        const items = container.querySelectorAll('.scraper-item');
        const updates = [];

        // 从上到下优先级递减
        items.forEach((item, index) => {
            const scraperId = item.getAttribute('data-scraper-id');
            const priority = items.length - index; // 顶部优先级最高
            
            // 更新显示的优先级
            const priorityElement = item.querySelector('small');
            if (priorityElement) {
                priorityElement.textContent = `优先级: ${priority}`;
            }
            
            // 收集更新数据
            if (scraperId) {
                updates.push({
                    id: parseInt(scraperId),
                    priority: priority
                });
            }
        });

        // 发送更新请求
        try {
            await this.api.updateScrapersPriority({updates: updates});
            this.api.showNotification('刮削源优先级已更新', 'success');
        } catch (error) {
            console.error('更新刮削源优先级失败:', error);
            this.api.showNotification('更新优先级失败', 'error');
        }
    }

    renderScraperItem(scraper) {
        // 确保刮削源名称正确显示，优先使用display_name，如果没有则使用name
        const displayName = scraper.display_name || scraper.name || '未知刮削源';
        
        // 检查配置状态
        const configStatus = this.getScraperConfigStatus(scraper);
        
        return `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="card scraper-card ${!scraper.enabled ? 'disabled' : ''}" 
                     data-scraper-id="${scraper.id}" data-scraper="${scraper.name}" data-priority="${scraper.priority}">
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-2">
                            <i class="bi ${this.getScraperIcon(scraper.name)} fs-4 me-2"></i>
                            <h5 class="card-title mb-0">${displayName}</h5>
                        </div>
                        
                        <div class="mb-3">
                            <span class="badge ${configStatus.badgeClass} mb-1">${configStatus.text}</span>
                            <div class="text-muted small">
                                <i class="bi bi-sort-numeric-down"></i> 优先级: ${scraper.priority}
                            </div>
                            ${configStatus.details ? `<div class="text-muted small">${configStatus.details}</div>` : ''}
                        </div>
                        
                        <div class="d-flex justify-content-between">
                            <button class="btn btn-outline-primary btn-sm" data-action="config">
                                <i class="bi bi-gear"></i> 配置
                            </button>
                            <button class="btn btn-outline-success btn-sm" data-action="test">
                                <i class="bi bi-wifi"></i> 测试
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    getScraperConfigStatus(scraper) {
        const scraperType = scraper.type || scraper.name.toLowerCase();
        
        switch(scraperType) {
            case 'tmdb':
                if (scraper.api_key && scraper.api_key.trim()) {
                    return {
                        text: '已配置',
                        badgeClass: 'bg-success',
                        details: `API密钥: ${scraper.api_key.substring(0, 8)}...`
                    };
                }
                break;
                
            case 'douban':
                if (scraper.cookie && scraper.cookie.trim()) {
                    return {
                        text: '已配置',
                        badgeClass: 'bg-success',
                        details: 'Cookie已设置'
                    };
                }
                break;
                
            case 'bangumi':
                if (scraper.app_id && scraper.app_id.trim() && scraper.app_secret && scraper.app_secret.trim()) {
                    return {
                        text: '已配置',
                        badgeClass: 'bg-success',
                        details: 'App ID/Secret已设置'
                    };
                }
                break;
                
            case 'imdb':
                if (scraper.api_key && scraper.api_key.trim()) {
                    return {
                        text: '已配置',
                        badgeClass: 'bg-success',
                        details: `API密钥: ${scraper.api_key.substring(0, 8)}...`
                    };
                }
                break;
                
            case 'tvdb':
                if (scraper.api_key && scraper.api_key.trim()) {
                    return {
                        text: '已配置',
                        badgeClass: 'bg-success',
                        details: `API密钥: ${scraper.api_key.substring(0, 8)}...`
                    };
                }
                break;
        }
        
        return {
            text: '未配置',
            badgeClass: 'bg-warning',
            details: '点击配置按钮设置API密钥或账户信息'
        };
    }

    getScraperIcon(name) {
        const iconMap = {
            'tmdb': 'bi-film',
            'douban': 'bi-book',
            'bangumi': 'bi-tv',
            'imdb': 'bi-star',
            'tvdb': 'bi-collection-play'
        };
        return iconMap[name] || 'bi-search';
    }

    bindScraperActions(item, scraper) {
        const buttons = item.querySelectorAll('[data-action]');
        buttons.forEach(button => {
            button.addEventListener('click', async () => {
                const action = button.getAttribute('data-action');
                await this.handleScraperAction(scraper.name, action);
            });
        });
    }

    async handleScraperAction(scraperName, action) {
        try {
            // 获取完整的刮削源信息
            const scrapers = await this.api.getScrapers();
            const scraper = scrapers.find(s => s.name === scraperName);
            
            if (!scraper) {
                throw new Error(`刮削源 ${scraperName} 不存在`);
            }
            
            switch (action) {
                case 'config':
                    this.showScraperConfigModal(scraper);
                    break;
                case 'test':
                    const result = await this.api.testScraper(scraperName);
                    this.api.showNotification(`刮削源测试${result.success ? '成功' : '失败'}`, 
                                             result.success ? 'success' : 'error');
                    break;
            }
        } catch (error) {
            console.error(`刮削源操作失败: ${action}`, error);
            this.api.showNotification(`操作失败: ${error.message}`, 'error');
        }
    }

    showScraperConfigModal(scraper) {
        const modal = new bootstrap.Modal(document.getElementById('scraperConfigModal'));
        
        // 设置模态框标题，确保刮削源名称正确显示
        const displayName = scraper.display_name || scraper.name || '未知刮削源';
        document.getElementById('scraper-config-title').textContent = `${displayName} 配置`;
        
        // 重置测试状态
        this.resetScraperTestStatus();
        
        // 填充基本信息
        document.getElementById('scraper-enabled').checked = scraper.enabled || false;
        document.getElementById('scraper-priority').value = scraper.priority || 0;
        document.getElementById('scraper-timeout').value = scraper.timeout || 30;
        document.getElementById('scraper-retry').value = scraper.retry || 3;
        document.getElementById('scraper-delay').value = scraper.delay || 1000;
        
        // 隐藏所有配置区域
        document.querySelectorAll('.scraper-config-section').forEach(section => {
            section.style.display = 'none';
        });
        
        // 根据刮削源类型显示对应的配置区域
        const scraperType = scraper.type || scraper.name.toLowerCase();
        const configSection = document.getElementById(`${scraperType}-config`);
        if (configSection) {
            configSection.style.display = 'block';
            
            // 填充特定配置
            switch(scraperType) {
                case 'tmdb':
                    document.getElementById('tmdb-api-url').value = scraper.api_url || 'https://api.tmdb.org';
                    document.getElementById('tmdb-api-key').value = scraper.api_key || '';
                    document.getElementById('tmdb-language').value = scraper.language || 'zh-CN';
                    break;
                case 'douban':
                    document.getElementById('douban-api-url').value = scraper.api_url || 'https://api.douban.com';
                    document.getElementById('douban-cookie').value = scraper.cookie || '';
                    break;
                case 'bangumi':
                    document.getElementById('bangumi-api-url').value = scraper.api_url || 'https://api.bgm.tv';
                    document.getElementById('bangumi-app-id').value = scraper.app_id || '';
                    document.getElementById('bangumi-app-secret').value = scraper.app_secret || '';
                    break;
                case 'imdb':
                    document.getElementById('imdb-api-url').value = scraper.api_url || 'https://imdb-api.com';
                    document.getElementById('imdb-api-key').value = scraper.api_key || '';
                    break;
                case 'tvdb':
                    document.getElementById('tvdb-api-url').value = scraper.api_url || 'https://api.thetvdb.com';
                    document.getElementById('tvdb-api-key').value = scraper.api_key || '';
                    break;
            }
        }
        
        // 保存当前刮削源信息
        this.currentScraper = scraper;
        
        modal.show();
    }
    
    // 重置刮削源测试状态
    resetScraperTestStatus() {
        document.getElementById('scraper-test-status').textContent = '未测试';
        document.getElementById('scraper-test-status').className = 'badge bg-secondary';
        document.getElementById('scraper-test-latency').textContent = '';
        document.getElementById('scraper-test-result').style.display = 'none';
        document.getElementById('scraper-test-error').style.display = 'none';
    }
    
    // 测试刮削源连接
    async testScraperConnection() {
        if (!this.currentScraper) return;
        
        const testBtn = document.getElementById('test-scraper-btn');
        const testStatus = document.getElementById('scraper-test-status');
        const testLatency = document.getElementById('scraper-test-latency');
        const testResult = document.getElementById('scraper-test-result');
        const testError = document.getElementById('scraper-test-error');
        
        // 更新测试状态
        testBtn.disabled = true;
        testBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 测试中...';
        testStatus.textContent = '测试中';
        testStatus.className = 'badge bg-warning';
        testLatency.textContent = '';
        testResult.style.display = 'none';
        testError.style.display = 'none';
        
        try {
            const startTime = Date.now();
            
            // 构建测试数据
            const testData = {
                scraper_id: this.currentScraper.id,
                config: this.getScraperConfigFromForm()
            };
            
            const response = await fetch('/api/scrapers/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(testData)
            });
            
            const endTime = Date.now();
            const latency = endTime - startTime;
            
            if (response.ok) {
                const result = await response.json();
                
                testStatus.textContent = '连接成功';
                testStatus.className = 'badge bg-success';
                testLatency.textContent = `延迟: ${latency}ms`;
                testResult.style.display = 'block';
                
                if (result.message) {
                    testResult.querySelector('.alert').innerHTML = 
                        `<i class="bi bi-check-circle"></i> ${result.message}`;
                }
            } else {
                const error = await response.json();
                throw new Error(error.detail || '连接测试失败');
            }
        } catch (error) {
            testStatus.textContent = '连接失败';
            testStatus.className = 'badge bg-danger';
            testLatency.textContent = '';
            testError.style.display = 'block';
            document.getElementById('scraper-error-message').textContent = error.message;
        } finally {
            testBtn.disabled = false;
            testBtn.innerHTML = '<i class="bi bi-wifi"></i> 测试连接';
        }
    }
    
    // 从表单获取刮削源配置
    getScraperConfigFromForm() {
        const config = {
            enabled: document.getElementById('scraper-enabled').checked,
            priority: parseInt(document.getElementById('scraper-priority').value),
            timeout: parseInt(document.getElementById('scraper-timeout').value),
            retry: parseInt(document.getElementById('scraper-retry').value),
            delay: parseInt(document.getElementById('scraper-delay').value)
        };
        
        // 根据刮削源类型添加特定配置
        const scraperType = this.currentScraper.type || this.currentScraper.name.toLowerCase();
        
        switch(scraperType) {
            case 'tmdb':
                config.api_url = document.getElementById('tmdb-api-url').value;
                config.api_key = document.getElementById('tmdb-api-key').value;
                config.language = document.getElementById('tmdb-language').value;
                break;
            case 'douban':
                config.api_url = document.getElementById('douban-api-url').value;
                config.cookie = document.getElementById('douban-cookie').value;
                break;
            case 'bangumi':
                config.api_url = document.getElementById('bangumi-api-url').value;
                config.app_id = document.getElementById('bangumi-app-id').value;
                config.app_secret = document.getElementById('bangumi-app-secret').value;
                break;
            case 'imdb':
                config.api_url = document.getElementById('imdb-api-url').value;
                config.api_key = document.getElementById('imdb-api-key').value;
                break;
            case 'tvdb':
                config.api_url = document.getElementById('tvdb-api-url').value;
                config.api_key = document.getElementById('tvdb-api-key').value;
                break;
        }
        
        return config;
    }
    
    // 显示刮削源帮助信息
    showScraperHelp(scraperType) {
        const helpMessages = {
            tmdb: `如何获取TMDB API Key：
1. 访问 https://www.themoviedb.org/settings/api
2. 登录您的TMDB账户
3. 点击"API"选项卡
4. 填写申请表格并提交
5. 获取API Key后在此处填写`,
            
            douban: `如何获取豆瓣Cookie：
1. 登录豆瓣网站 (https://www.douban.com)
2. 打开浏览器开发者工具 (F12)
3. 切换到Network/网络选项卡
4. 刷新页面或进行任何操作
5. 找到任意请求，复制Cookie字段
6. 将完整的Cookie字符串粘贴到此处`,
            
            bangumi: `如何获取Bangumi API：
1. 访问 https://bgm.tv/dev/app
2. 登录您的Bangumi账户
3. 创建新的应用程序
4. 填写应用信息并提交
5. 获取App ID和App Secret
6. 在此处填写对应的信息`,
            
            imdb: `如何获取IMDb API Key：
1. 访问 https://developer.imdb.com
2. 注册IMDb开发者账户
3. 创建新的应用程序
4. 获取API Key
5. 在此处填写API Key`,
            
            tvdb: `如何获取TVDB API Key：
1. 访问 https://thetvdb.com/api-information
2. 注册TVDB开发者账户
3. 创建API密钥
4. 获取API Key
5. 在此处填写API Key`
        };
        
        const message = helpMessages[scraperType] || '暂无帮助信息';
        alert(message);
    }

    async loadSettings() {
        try {
            const settings = await this.api.getSettings();
            this.renderSettings(settings);
        } catch (error) {
            console.error('加载设置失败:', error);
        }
    }

    renderSettings(settings) {
        // 渲染代理设置
        document.getElementById('proxy-enabled').checked = settings.proxy_enabled || false;
        document.getElementById('proxy-url').value = settings.proxy_url || '';
        
        // 渲染系统设置
        document.getElementById('max-memory').value = settings.max_memory || 1024;
        document.getElementById('max-workers').value = settings.max_workers || 4;
        document.getElementById('task-timeout').value = settings.task_timeout || 3600;
        
        // 渲染二级分类策略
        if (settings.subcategory_strategy) {
            document.getElementById('subcategory-strategy').value = settings.subcategory_strategy;
        } else {
            // 设置默认的二级分类策略配置
            const defaultStrategy = `movie:
  动画电影:
    genre_ids: '16'
  华语电影:
    original_language: 'zh,cn,bo,za'
  外语电影:

tv:
  国漫:
    genre_ids: '16'
    origin_country: 'CN,TW,HK'
  日番:
    genre_ids: '16'
    origin_country: 'JP'
  纪录片:
    genre_ids: '99'
  儿童:
    genre_ids: '10762'
  综艺:
    genre_ids: '10764,10767'
  国产剧:
    origin_country: 'CN,TW,HK'
  欧美剧:
    origin_country: 'US,FR,GB,DE,ES,IT,NL,PT,RU,UK'
  日韩剧:
    origin_country: 'JP,KP,KR,TH,IN,SG'
  未分类:`;
            document.getElementById('subcategory-strategy').value = defaultStrategy;
        }
    }

    async testProxy() {
        const proxyUrl = document.getElementById('proxy-url').value;
        if (!proxyUrl) {
            this.api.showNotification('请输入代理地址', 'warning');
            return;
        }

        try {
            const result = await this.api.testProxy(proxyUrl);
            this.api.showNotification(`代理测试${result.success ? '成功' : '失败'}`, 
                                     result.success ? 'success' : 'error');
        } catch (error) {
            console.error('代理测试失败:', error);
            this.api.showNotification(`代理测试失败: ${error.message}`, 'error');
        }
    }

    async saveProxySettings() {
        const settings = {
            proxy_enabled: document.getElementById('proxy-enabled').checked,
            proxy_url: document.getElementById('proxy-url').value
        };

        try {
            await this.api.updateSettings(settings);
            this.api.showNotification('代理设置已保存', 'success');
        } catch (error) {
            console.error('保存代理设置失败:', error);
            this.api.showNotification(`保存失败: ${error.message}`, 'error');
        }
    }

    async saveSystemSettings() {
        const settings = {
            max_memory: parseInt(document.getElementById('max-memory').value),
            max_workers: parseInt(document.getElementById('max-workers').value),
            task_timeout: parseInt(document.getElementById('task-timeout').value),
            subcategory_strategy: document.getElementById('subcategory-strategy').value
        };

        try {
            await this.api.updateSettings(settings);
            this.api.showNotification('系统设置已保存', 'success');
        } catch (error) {
            console.error('保存系统设置失败:', error);
            this.api.showNotification(`保存失败: ${error.message}`, 'error');
        }
    }

    async loadLogs() {
        try {
            const logs = await this.api.getLogs();
            this.renderLogs(logs);
        } catch (error) {
            console.error('加载日志失败:', error);
        }
    }

    renderLogs(logs) {
        const container = document.getElementById('full-log-terminal');
        if (!container) return;

        container.innerHTML = '';
        
        if (logs.length === 0) {
            container.innerHTML = '<div class="text-muted">暂无日志</div>';
            return;
        }

        logs.forEach(log => {
            this.api.addLogEntry(container, log.message, log.level);
        });
    }

    async clearLogs() {
        if (confirm('确定要清空所有日志吗？')) {
            try {
                await this.api.clearLogs();
                this.api.showNotification('日志已清空', 'success');
                this.loadLogs();
            } catch (error) {
                console.error('清空日志失败:', error);
                this.api.showNotification(`清空日志失败: ${error.message}`, 'error');
            }
        }
    }

    exportLogs() {
        // 导出日志功能
        this.api.getLogs(null, 1000).then(logs => {
            const logContent = logs.map(log => 
                `[${new Date(log.timestamp).toLocaleString()}] [${log.level.toUpperCase()}] ${log.message}`
            ).join('\n');
            
            const blob = new Blob([logContent], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `strm-poller-logs-${new Date().toISOString().slice(0, 10)}.txt`;
            a.click();
            URL.revokeObjectURL(url);
            
            this.api.showNotification('日志导出成功', 'success');
        }).catch(error => {
            console.error('导出日志失败:', error);
            this.api.showNotification(`导出日志失败: ${error.message}`, 'error');
        });
    }

    startAutoRefresh() {
        // 每30秒自动刷新一次
        this.refreshInterval = setInterval(() => {
            if (this.currentPage === 'dashboard') {
                this.loadDashboard();
            }
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    // 通知设置页面加载方法
    async loadNotifications() {
        try {
            const settings = await this.api.getSettings();
            this.renderNotifications(settings);
        } catch (error) {
            console.error('加载通知设置失败:', error);
        }
    }

    renderNotifications(settings) {
        // 渲染微信企业机器人设置
        document.getElementById('wechat-enabled').checked = settings.wechat_enabled || false;
        document.getElementById('wechat-webhook').value = settings.wechat_webhook || '';
        document.getElementById('wechat-mentions').value = settings.wechat_mentions || '';
        
        // 渲染Telegram设置
        document.getElementById('telegram-enabled').checked = settings.telegram_enabled || false;
        document.getElementById('telegram-token').value = settings.telegram_token || '';
        document.getElementById('telegram-chat-id').value = settings.telegram_chat_id || '';
        
        // 渲染事件类型设置
        const eventTypes = ['task_start', 'task_complete', 'task_failed', 'task_paused', 'task_cancelled', 'system_error'];
        eventTypes.forEach(eventType => {
            const checkbox = document.getElementById(`event-${eventType}`);
            if (checkbox) {
                checkbox.checked = settings.notification_events ? settings.notification_events.includes(eventType) : true;
            }
        });
    }

    // 规则设置页面加载方法
    async loadRules() {
        try {
            const settings = await this.api.getSettings();
            this.renderRules(settings);
        } catch (error) {
            console.error('加载规则设置失败:', error);
        }
    }

    renderRules(settings) {
        // 渲染二级分类策略
        document.getElementById('subcategory-enabled').checked = settings.subcategory_enabled || false;
        if (settings.subcategory_strategy) {
            document.getElementById('subcategory-strategy').value = settings.subcategory_strategy;
        }
        
        // 渲染重命名格式设置
        document.getElementById('movie-rename-format').value = settings.movie_rename_format || '{title} ({year})';
        document.getElementById('tv-show-format').value = settings.tv_show_format || '{title} ({year})';
        document.getElementById('tv-season-format').value = settings.tv_season_format || 'Season {season:02d}';
        document.getElementById('tv-episode-format').value = settings.tv_episode_format || 'S{season:02d}E{episode:02d}';
    }

    // 保存通知设置
    async saveNotificationSettings() {
        const settings = {
            wechat_enabled: document.getElementById('wechat-enabled').checked,
            wechat_webhook: document.getElementById('wechat-webhook').value,
            wechat_mentions: document.getElementById('wechat-mentions').value,
            telegram_enabled: document.getElementById('telegram-enabled').checked,
            telegram_token: document.getElementById('telegram-token').value,
            telegram_chat_id: document.getElementById('telegram-chat-id').value,
            notification_events: []
        };

        // 收集选中的事件类型
        const eventTypes = ['task_start', 'task_complete', 'task_failed', 'task_paused', 'task_cancelled', 'system_error'];
        eventTypes.forEach(eventType => {
            const checkbox = document.getElementById(`event-${eventType}`);
            if (checkbox && checkbox.checked) {
                settings.notification_events.push(eventType);
            }
        });

        try {
            await this.api.updateSettings(settings);
            this.api.showNotification('通知设置已保存', 'success');
        } catch (error) {
            console.error('保存通知设置失败:', error);
            this.api.showNotification(`保存失败: ${error.message}`, 'error');
        }
    }

    // 保存规则设置
    async saveRuleSettings() {
        const settings = {
            subcategory_enabled: document.getElementById('subcategory-enabled').checked,
            subcategory_strategy: document.getElementById('subcategory-strategy').value,
            movie_rename_format: document.getElementById('movie-rename-format').value,
            tv_show_format: document.getElementById('tv-show-format').value,
            tv_season_format: document.getElementById('tv-season-format').value,
            tv_episode_format: document.getElementById('tv-episode-format').value
        };

        try {
            await this.api.updateSettings(settings);
            this.api.showNotification('规则设置已保存', 'success');
        } catch (error) {
            console.error('保存规则设置失败:', error);
            this.api.showNotification(`保存失败: ${error.message}`, 'error');
        }
    }

    // 加载默认二级分类策略
    loadDefaultSubcategoryStrategy() {
        const defaultStrategy = `movie:
  动画电影:
    genre_ids: '16'
  华语电影:
    original_language: 'zh,cn,bo,za'
  外语电影:

tv:
  国漫:
    genre_ids: '16'
    origin_country: 'CN,TW,HK'
  日番:
    genre_ids: '16'
    origin_country: 'JP'
  纪录片:
    genre_ids: '99'
  儿童:
    genre_ids: '10762'
  综艺:
    genre_ids: '10764,10767'
  国产剧:
    origin_country: 'CN,TW,HK'
  欧美剧:
    origin_country: 'US,FR,GB,DE,ES,IT,NL,PT,RU,UK'
  日韩剧:
    origin_country: 'JP,KP,KR,TH,IN,SG'
  未分类:`;
        document.getElementById('subcategory-strategy').value = defaultStrategy;
        this.api.showNotification('已加载默认二级分类策略', 'info');
    }

    // 加载默认电影重命名格式
    loadDefaultMovieFormat() {
        document.getElementById('movie-rename-format').value = '{title} ({year})';
        this.api.showNotification('已加载默认电影重命名格式', 'info');
    }

    // 加载默认电视剧重命名格式
    loadDefaultTVFormat() {
        document.getElementById('tv-show-format').value = '{title} ({year})';
        document.getElementById('tv-season-format').value = 'Season {season:02d}';
        document.getElementById('tv-episode-format').value = 'S{season:02d}E{episode:02d}';
        this.api.showNotification('已加载默认电视剧重命名格式', 'info');
    }

    // 保存刮削源配置
    async saveScraperConfig() {
        if (!this.currentScraper) {
            this.api.showNotification('请先选择刮削源', 'error');
            return;
        }

        try {
            const config = this.getScraperConfigFromForm();
            
            // 构建保存数据
            const saveData = {
                scraper_id: this.currentScraper.id,
                config: config
            };

            const response = await fetch('/api/scrapers/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(saveData)
            });

            if (!response.ok) {
                throw new Error(`保存失败: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                this.api.showNotification('刮削源配置已保存', 'success');
                
                // 关闭模态框
                const modal = bootstrap.Modal.getInstance(document.getElementById('scraperConfigModal'));
                if (modal) {
                    modal.hide();
                }
                
                // 重新加载刮削源列表
                this.loadScrapers();
            } else {
                throw new Error(result.message || '保存失败');
            }
        } catch (error) {
            console.error('保存刮削源配置失败:', error);
            this.api.showNotification(`保存失败: ${error.message}`, 'error');
        }
    }
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    const apiClient = new APIClient();
    const pageManager = new PageManager(apiClient);
    
    // 页面卸载时清理资源
    window.addEventListener('beforeunload', () => {
        pageManager.stopAutoRefresh();
        if (apiClient.ws) {
            apiClient.ws.close();
        }
    });
    
    console.log('STRM Poller WebUI 已初始化');
});