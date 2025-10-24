import asyncio
import httpx
from typing import Dict, List, Optional, Set
from abc import ABC, abstractmethod
from .config import settings
from .logger import logger


class BaseNotifier(ABC):
    """通知器基类"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get('enabled', False)
    
    @abstractmethod
    async def send(self, title: str, message: str, event_type: str) -> bool:
        """发送通知"""
        pass
    
    def _should_notify(self, event_type: str) -> bool:
        """检查是否应该发送该类型的通知"""
        # 从配置中获取需要通知的事件类型
        events = self.config.get('events', [])
        return 'all' in events or event_type in events


class WechatWorkNotifier(BaseNotifier):
    """微信企业机器人通知器"""
    
    async def send(self, title: str, message: str, event_type: str) -> bool:
        if not self.enabled or not self._should_notify(event_type):
            return False
        
        webhook_url = self.config.get('webhook_url')
        if not webhook_url:
            logger.error("微信企业机器人webhook_url未配置")
            return False
        
        try:
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"## {title}\n\n{message}"
                }
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(webhook_url, json=data)
                if response.status_code == 200:
                    logger.info(f"微信企业机器人通知发送成功")
                    return True
                else:
                    logger.error(f"微信企业机器人通知发送失败: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"微信企业机器人通知异常: {e}")
            return False


class TelegramNotifier(BaseNotifier):
    """Telegram通知器"""
    
    async def send(self, title: str, message: str, event_type: str) -> bool:
        if not self.enabled or not self._should_notify(event_type):
            return False
        
        bot_token = self.config.get('bot_token')
        chat_id = self.config.get('chat_id')
        
        if not bot_token or not chat_id:
            logger.error("Telegram bot_token或chat_id未配置")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": f"*{title}*\n\n{message}",
                "parse_mode": "Markdown"
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=data)
                if response.status_code == 200:
                    logger.info(f"Telegram通知发送成功")
                    return True
                else:
                    logger.error(f"Telegram通知发送失败: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Telegram通知异常: {e}")
            return False


class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.notifiers: List[BaseNotifier] = []
        self._init_notifiers()
    
    def _init_notifiers(self):
        """初始化通知器"""
        try:
            # 微信企业机器人配置 - 支持嵌套配置和扁平化配置
            if hasattr(settings, 'notify') and hasattr(settings.notify, 'wechat'):
                wc_config = settings.notify.wechat
                wechat_config = {
                    'enabled': getattr(wc_config, 'enabled', False),
                    'webhook_url': getattr(wc_config, 'webhook_url', ''),
                    'events': getattr(wc_config, 'events', [])
                }
            else:
                # 保持向后兼容的扁平化配置
                wechat_config = {
                    'enabled': getattr(settings, 'notify_wechat_enabled', False),
                    'webhook_url': getattr(settings, 'notify_wechat_webhook_url', ''),
                    'events': getattr(settings, 'notify_wechat_events', [])
                }
            self.notifiers.append(WechatWorkNotifier(wechat_config))
            
            # Telegram配置 - 支持嵌套配置和扁平化配置
            if hasattr(settings, 'notify') and hasattr(settings.notify, 'telegram'):
                tg_config = settings.notify.telegram
                telegram_config = {
                    'enabled': getattr(tg_config, 'enabled', False),
                    'bot_token': getattr(tg_config, 'bot_token', ''),
                    'chat_id': getattr(tg_config, 'chat_id', ''),
                    'events': getattr(tg_config, 'events', [])
                }
            else:
                # 保持向后兼容的扁平化配置
                telegram_config = {
                    'enabled': getattr(settings, 'notify_telegram_enabled', False),
                    'bot_token': getattr(settings, 'notify_telegram_bot_token', ''),
                    'chat_id': getattr(settings, 'notify_telegram_chat_id', ''),
                    'events': getattr(settings, 'notify_telegram_events', [])
                }
            self.notifiers.append(TelegramNotifier(telegram_config))
            
            logger.info("通知管理器初始化成功")
        except Exception as e:
            logger.error(f"通知管理器初始化失败: {e}")
            # 初始化失败时使用默认配置
            self.notifiers = []
            self.notifiers.append(WechatWorkNotifier({'enabled': False}))
            self.notifiers.append(TelegramNotifier({'enabled': False}))
    
    async def notify(self, title: str, message: str, event_type: str):
        """发送通知到所有已配置的通知器"""
        if not self.notifiers:
            return
        
        tasks = []
        for notifier in self.notifiers:
            tasks.append(notifier.send(title, message, event_type))
        
        await asyncio.gather(*tasks)


# 全局通知管理器实例
notification_manager = NotificationManager()


# 通知事件类型常量
class NotificationEvents:
    """通知事件类型"""
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    FILE_PROCESSED = "file_processed"
    FILE_FAILED = "file_failed"
    SYSTEM_STARTED = "system_started"
    SYSTEM_ERROR = "system_error"