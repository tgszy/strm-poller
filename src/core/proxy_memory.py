import asyncio
import aiohttp
import psutil
import logging
import platform
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta

# 尝试导入resource模块（仅Unix/Linux系统可用）
try:
    import resource
except ImportError:
    resource = None

logger = logging.getLogger(__name__)

@dataclass
class ProxyConfig:
    """代理配置"""
    enabled: bool = False
    type: str = 'http'  # http, https, socks5
    host: str = 'localhost'
    port: int = 8080
    username: Optional[str] = None
    password: Optional[str] = None
    test_url: str = 'https://httpbin.org/ip'
    timeout: int = 10
    
    def get_proxy_url(self) -> str:
        """获取代理URL"""
        if not self.enabled:
            return ''
            
        # 验证必要的代理参数
        if not self.host or not self.port:
            logger.error("代理配置不完整：缺少主机或端口")
            return ''
            
        # 规范化代理类型
        proxy_type = self.type or 'http'
        if proxy_type.startswith('http') and not proxy_type.endswith('s'):
            proxy_type = 'http'
        elif proxy_type.startswith('http') and proxy_type.endswith('s'):
            proxy_type = 'https'
        elif proxy_type.startswith('socks'):
            if proxy_type == 'socks':
                proxy_type = 'socks5'  # 默认为SOCKS5
            elif proxy_type not in ['socks4', 'socks5']:
                proxy_type = 'socks5'  # 未知类型默认为SOCKS5
        else:
            proxy_type = 'http'  # 默认为HTTP
            
        # 构建代理URL
        try:
            auth = ''
            if self.username and self.password:
                # 对用户名和密码进行URL编码
                import urllib.parse
                username = urllib.parse.quote(self.username)
                password = urllib.parse.quote(self.password)
                auth = f"{username}:{password}@"
                
            return f"{proxy_type}://{auth}{self.host}:{self.port}"
        except Exception as e:
            logger.error(f"构建代理URL失败: {e}")
            return ''
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'enabled': self.enabled,
            'type': self.type,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'password': self.password,
            'test_url': self.test_url,
            'timeout': self.timeout
        }

class ProxyManager:
    """代理管理器"""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.session = None
        self.last_test = None
        self.is_working = False
        
    async def init_session(self):
        """初始化HTTP会话"""
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        
        if self.config.enabled and self.config.type == 'socks5':
            try:
                from aiohttp_socks import ProxyConnector
                connector = ProxyConnector.from_url(self.config.get_proxy_url())
            except ImportError:
                logger.warning("SOCKS5代理需要安装aiohttp-socks包，使用默认连接器")
                connector = aiohttp.TCPConnector(ssl=False)
        else:
            connector = aiohttp.TCPConnector(ssl=False)
            
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'STRM-Poller/3.0'}
        )
        
    async def close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            
    async def test_proxy(self) -> Dict[str, Any]:
        """测试代理连接"""
        if not self.config.enabled:
            return {
                'success': False,
                'message': '代理未启用',
                'response_time': 0,
                'timestamp': datetime.now().isoformat()
            }
            
    async def test_proxy_url(self, proxy_url: str) -> Dict[str, Any]:
        """测试指定的代理URL"""
        start_time = datetime.now()
        
        try:
            # 创建一个临时会话进行测试
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            
            # 检查代理类型
            connector = aiohttp.TCPConnector(ssl=False)
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'User-Agent': 'STRM-Poller/3.0'}
            ) as temp_session:
                async with temp_session.get(
                    self.config.test_url,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    response_time = (datetime.now() - start_time).total_seconds()
                    
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'message': f'代理测试成功，响应时间: {response_time:.2f}s',
                            'response_time': response_time,
                            'ip': data.get('origin', 'Unknown'),
                            'timestamp': datetime.now().isoformat()
                        }
                    else:
                        return {
                            'success': False,
                            'message': f'代理测试失败，HTTP状态码: {response.status}',
                            'response_time': response_time,
                            'timestamp': datetime.now().isoformat()
                        }
            
        except asyncio.TimeoutError:
            response_time = (datetime.now() - start_time).total_seconds()
            return {
                'success': False,
                'message': f'代理测试超时 ({self.config.timeout}s)',
                'response_time': response_time,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            return {
                'success': False,
                'message': f'代理测试异常: {str(e)}',
                'response_time': response_time,
                'timestamp': datetime.now().isoformat()
            }
            
    async def test_proxy(self) -> Dict[str, Any]:
        """测试代理连接"""
        if not self.config.enabled:
            return {
                'success': False,
                'message': '代理未启用',
                'response_time': 0,
                'timestamp': datetime.now().isoformat()
            }
        
        start_time = datetime.now()
        
        try:
            # 构建代理URL
            proxy_url = self.config.get_proxy_url()
            if not proxy_url:
                return {
                    'success': False,
                    'message': '无法构建代理URL',
                    'response_time': 0,
                    'timestamp': datetime.now().isoformat()
                }
            
            logger.info(f"开始测试代理连接: {proxy_url}")
            
            # 测试URL，如果配置了则使用配置的，否则使用默认的
            test_url = self.config.test_url or "https://www.baidu.com"  # 改用百度以提高成功率
            
            # 创建一个新的aiohttp会话进行测试
            timeout = aiohttp.ClientTimeout(total=self.config.timeout or 15)  # 增加超时时间
            
            # 使用代理发送请求
            async with aiohttp.ClientSession(timeout=timeout, headers={'User-Agent': 'STRM-Poller/3.0'}) as session:
                try:
                    # 方法1: 直接使用proxy参数
                    async with session.get(test_url, proxy=proxy_url, ssl=False, allow_redirects=True) as response:
                        response_time = (datetime.now() - start_time).total_seconds()
                        
                        if response.status in [200, 301, 302]:  # 允许重定向状态码
                            try:
                                data = await response.json()
                                ip = data.get('origin', 'Unknown')
                            except:
                                ip = 'Unknown'
                            
                            self.is_working = True
                            self.last_test = datetime.now()
                            
                            return {
                                'success': True,
                                'message': f'代理测试成功，响应时间: {response_time:.2f}s',
                                'response_time': response_time,
                                'ip': ip,
                                'status_code': response.status,
                                'proxy_used': proxy_url,
                                'timestamp': datetime.now().isoformat()
                            }
                        else:
                            logger.warning(f"代理返回非成功状态码: {response.status}")
                            self.is_working = False
                            response_time = (datetime.now() - start_time).total_seconds()
                            return {
                                'success': False,
                                'message': f'代理测试失败，HTTP状态码: {response.status}',
                                'response_time': response_time,
                                'status_code': response.status,
                                'timestamp': datetime.now().isoformat()
                            }
                except Exception as e1:
                    # 如果方法1失败，尝试方法2: 不使用proxy参数的备用方法
                    logger.warning(f"方法1测试失败，尝试方法2: {str(e1)}")
                    start_time = datetime.now()  # 重置计时
                    
                    # 对于局域网代理，尝试使用TCPConnector
                    conn = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(connector=conn, timeout=timeout, headers={'User-Agent': 'STRM-Poller/3.0'}) as fallback_session:
                        async with fallback_session.get(test_url, allow_redirects=True) as response:
                            response_time = (datetime.now() - start_time).total_seconds()
                            
                            if response.status in [200, 301, 302]:
                                try:
                                    data = await response.json()
                                    ip = data.get('origin', 'Unknown')
                                except:
                                    ip = 'Unknown'
                                
                                self.is_working = True
                                self.last_test = datetime.now()
                                
                                return {
                                    'success': True,
                                    'message': '代理测试成功(备用方法)',
                                    'response_time': response_time,
                                    'ip': ip,
                                    'status_code': response.status,
                                    'proxy_used': proxy_url,
                                    'timestamp': datetime.now().isoformat()
                                }
                            else:
                                self.is_working = False
                                return {
                                    'success': False,
                                    'message': f'代理测试失败，HTTP状态码: {response.status}',
                                    'response_time': response_time,
                                    'status_code': response.status,
                                    'timestamp': datetime.now().isoformat()
                                }
        except aiohttp.ClientConnectorError as e:
            self.is_working = False
            logger.error(f"代理连接错误: {str(e)}")
            response_time = (datetime.now() - start_time).total_seconds()
            return {
                'success': False,
                'message': f'连接错误: {str(e)}',
                'response_time': response_time,
                'proxy_url': proxy_url,
                'timestamp': datetime.now().isoformat()
            }
        except asyncio.TimeoutError:
            self.is_working = False
            logger.error(f"代理连接超时: {proxy_url}")
            response_time = (datetime.now() - start_time).total_seconds()
            return {
                'success': False,
                'message': '连接超时，可能是代理不可达或网络问题',
                'response_time': response_time,
                'proxy_url': proxy_url,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            self.is_working = False
            logger.error(f"代理测试异常: {str(e)}")
            response_time = (datetime.now() - start_time).total_seconds()
            return {
                'success': False,
                'message': f'未知错误: {str(e)}',
                'response_time': response_time,
                'proxy_url': proxy_url,
                'timestamp': datetime.now().isoformat()
            }
            
    def get_status(self) -> Dict[str, Any]:
        """获取代理状态"""
        return {
            'enabled': self.config.enabled,
            'type': self.config.type,
            'host': self.config.host,
            'port': self.config.port,
            'is_working': self.is_working,
            'last_test': self.last_test.isoformat() if self.last_test else None,
            'config': self.config.to_dict()
        }

class MemoryManager:
    """内存管理器"""
    
    def __init__(self, max_memory_mb: int = 1024):
        self.max_memory_mb = max_memory_mb
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.warning_threshold = 0.8  # 80%警告阈值
        self.critical_threshold = 0.95  # 95%严重阈值
        self.last_check = None
        self.memory_stats = {}
        
    def set_memory_limit(self):
        """设置内存限制"""
        # 检查操作系统类型，仅在Unix/Linux系统上设置内存限制
        if platform.system() in ['Windows', 'Darwin'] or not resource:
            logger.warning(f"内存限制功能在当前系统({platform.system()})上不可用，仅在Unix/Linux系统上支持")
            return False
            
        try:
            # 设置进程的内存限制
            resource.setrlimit(resource.RLIMIT_AS, (self.max_memory_bytes, self.max_memory_bytes))
            logger.info(f"内存限制已设置: {self.max_memory_mb}MB")
            
            # 设置数据段限制
            resource.setrlimit(resource.RLIMIT_DATA, (self.max_memory_bytes, self.max_memory_bytes))
            
            # 设置堆栈限制
            stack_limit = min(self.max_memory_bytes // 4, 8 * 1024 * 1024)  # 最大8MB栈空间
            resource.setrlimit(resource.RLIMIT_STACK, (stack_limit, stack_limit))
            
            return True
            
        except Exception as e:
            logger.error(f"设置内存限制失败: {e}")
            return False
            
    def check_memory_usage(self) -> Dict[str, Any]:
        """检查内存使用情况"""
        try:
            # 获取当前进程内存信息
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # 获取系统内存信息
            system_memory = psutil.virtual_memory()
            
            current_usage_mb = memory_info.rss / (1024 * 1024)
            usage_percentage = current_usage_mb / self.max_memory_mb
            system_percentage = memory_info.rss / system_memory.total * 100
            
            self.memory_stats = {
                'current_usage_mb': round(current_usage_mb, 2),
                'max_memory_mb': self.max_memory_mb,
                'usage_percentage': round(usage_percentage * 100, 2),
                'system_percentage': round(system_percentage, 2),
                'available_mb': round(system_memory.available / (1024 * 1024), 2),
                'rss_bytes': memory_info.rss,
                'vms_bytes': memory_info.vms,
                'timestamp': datetime.now().isoformat()
            }
            
            self.last_check = datetime.now()
            
            # 检查警告级别
            if usage_percentage >= self.critical_threshold:
                level = 'critical'
                message = f"内存使用严重警告: {current_usage_mb:.1f}MB ({usage_percentage*100:.1f}%)"
                logger.error(message)
            elif usage_percentage >= self.warning_threshold:
                level = 'warning'
                message = f"内存使用警告: {current_usage_mb:.1f}MB ({usage_percentage*100:.1f}%)"
                logger.warning(message)
            else:
                level = 'normal'
                message = f"内存使用正常: {current_usage_mb:.1f}MB ({usage_percentage*100:.1f}%)"
                
            self.memory_stats['level'] = level
            self.memory_stats['message'] = message
            
            return self.memory_stats
            
        except Exception as e:
            logger.error(f"检查内存使用失败: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
    def should_trigger_gc(self) -> bool:
        """是否应该触发垃圾回收"""
        if not self.memory_stats:
            return False
            
        usage_percentage = self.memory_stats.get('usage_percentage', 0)
        return usage_percentage >= self.warning_threshold
        
    def get_recommendations(self) -> List[str]:
        """获取内存优化建议"""
        recommendations = []
        
        if not self.memory_stats:
            return recommendations
            
        usage_percentage = self.memory_stats.get('usage_percentage', 0)
        
        if usage_percentage >= self.critical_threshold:
            recommendations.append("内存使用已达到严重级别，建议立即释放内存")
            recommendations.append("考虑重启应用或清理缓存")
            
        elif usage_percentage >= self.warning_threshold:
            recommendations.append("内存使用较高，建议清理不必要的缓存")
            recommendations.append("考虑调整内存限制或优化代码")
            
        if self.memory_stats.get('system_percentage', 0) > 80:
            recommendations.append("系统内存使用率较高，建议检查其他进程")
            
        return recommendations
        
    def get_status(self) -> Dict[str, Any]:
        """获取内存状态"""
        stats = self.memory_stats.copy() if self.memory_stats else {}
        stats.update({
            'max_memory_mb': self.max_memory_mb,
            'warning_threshold': self.warning_threshold,
            'critical_threshold': self.critical_threshold,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'recommendations': self.get_recommendations()
        })
        
        return stats

class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self, memory_manager: MemoryManager, proxy_manager: Optional[ProxyManager] = None):
        self.memory_manager = memory_manager
        self.proxy_manager = proxy_manager
        self.monitoring = False
        self.monitor_task = None
        self.check_interval = 30  # 30秒检查一次
        self.alert_callbacks = []
        
    def add_alert_callback(self, callback):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
        
    async def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("资源监控已启动")
        
    async def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("资源监控已停止")
        
    async def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 检查内存使用
                memory_stats = self.memory_manager.check_memory_usage()
                
                # 触发告警
                if memory_stats.get('level') in ['warning', 'critical']:
                    await self._trigger_alerts('memory', memory_stats)
                    
                # 检查代理状态
                if self.proxy_manager and self.proxy_manager.config.enabled:
                    # 每小时测试一次代理
                    if self.proxy_manager.last_test is None or \
                       datetime.now() - self.proxy_manager.last_test > timedelta(hours=1):
                        await self.proxy_manager.test_proxy()
                        
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _trigger_alerts(self, alert_type: str, data: Dict[str, Any]):
        """触发告警"""
        alert_info = {
            'type': alert_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_info)
                else:
                    callback(alert_info)
            except Exception as e:
                logger.error(f"告警回调失败: {e}")
                
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            'memory': self.memory_manager.get_status(),
            'proxy': self.proxy_manager.get_status() if self.proxy_manager else None,
            'monitoring': self.monitoring,
            'check_interval': self.check_interval,
            'timestamp': datetime.now().isoformat()
        }
        
        return status