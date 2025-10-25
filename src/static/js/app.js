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
            
            try {
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || `请求失败，状态码: ${response.status}`);
                }
                
                return data;
            } catch (jsonError) {
                console.error('JSON解析错误:', jsonError);
                // 如果无法解析JSON，返回文本内容
                const text = await response.text();
                throw new Error(`响应解析失败: ${response.status} ${text}`);
            }
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
        return this.request('/scrapers');
    }

    async updateScraper(scraperName, config) {
        return this.request(`/scrapers/${scraperName}`, {
            method: 'PUT',
            body: JSON.stringify(config)
        });
    }

    async testScraper(scraperName) {
        return this.request(`/scrapers/${scraperName}/test`, { method: 'POST' });
    }

    // 系统设置API
    async getSettings() {
        return this.request('/settings');
    }

    async updateSettings(settings) {
        return this.request('/settings', {
            method: 'PUT',
            body: JSON.stringify(settings)
        });
    }

    async testProxy(proxyUrl) {
        return this.request('/settings/test-proxy', {
            method: 'POST',
            body: JSON.stringify({ proxy_url: proxyUrl })
        });
    }

    // 统计信息API
    async getStats() {
        return this.request('/stats');
    }

    // 日志API
    async getLogs(level = null, limit = 100) {
        const params = new URLSearchParams();
        if (level) params.append('level', level);
        if (limit) params.append('limit', limit);
        
        return this.request(`/logs?${params}`);
    }

    async clearLogs() {
        return this.request('/logs', { method: 'DELETE' });
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
            'logs': '日志查看'
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

        container.innerHTML = `
            <div class="mb-3">
                <p class="text-muted">拖拽调整刮削源优先级，点击配置按钮编辑详细设置</p>
                <div class="d-flex gap-2 flex-wrap" id="scrapers-sortable">
                    ${scrapers.map(scraper => this.renderScraperItem(scraper)).join('')}
                </div>
            </div>
        `;

        // 绑定刮削源操作事件
        scrapers.forEach(scraper => {
            const item = container.querySelector(`[data-scraper="${scraper.name}"]`);
            if (item) {
                this.bindScraperActions(item, scraper);
            }
        });
    }

    renderScraperItem(scraper) {
        return `
            <div class="scraper-item ${!scraper.enabled ? 'disabled' : ''}" 
                 data-scraper="${scraper.name}" data-priority="${scraper.priority}">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1">
                            <i class="bi ${this.getScraperIcon(scraper.name)}"></i>
                            ${scraper.display_name}
                        </h6>
                        <small class="text-muted">优先级: ${scraper.priority}</small>
                    </div>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" data-action="config">
                            <i class="bi bi-gear"></i>
                        </button>
                        <button class="btn btn-outline-success" data-action="test">
                            <i class="bi bi-wifi"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
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
            switch (action) {
                case 'config':
                    this.showScraperConfigModal(scraperName);
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

    showScraperConfigModal(scraperName) {
        // 显示刮削源配置模态框
        const modal = new bootstrap.Modal(document.getElementById('scraperConfigModal'));
        
        // 这里应该加载刮削源的当前配置
        // 为了简化，这里只是显示模态框
        modal.show();
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
            task_timeout: parseInt(document.getElementById('task-timeout').value)
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