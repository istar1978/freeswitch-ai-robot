# storage/redis_client.py
import redis.asyncio as redis
import json
import asyncio
from typing import Any, Optional
from config.settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

class RedisClient:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self._connected = False
        
    async def connect(self):
        """连接Redis"""
        try:
            self.redis = redis.Redis(
                host=config.redis.host,
                port=config.redis.port,
                db=config.redis.db,
                password=config.redis.password,
                decode_responses=True,
                health_check_interval=30
            )
            await self.redis.ping()
            self._connected = True
            logger.info("Redis连接成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self._connected = False
            
    async def set_session_data(self, session_id: str, key: str, value: Any, expire: int = 3600):
        """设置会话数据"""
        if not self._connected:
            return False
            
        try:
            redis_key = f"session:{session_id}:{key}"
            await self.redis.setex(redis_key, expire, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"设置会话数据失败: {e}")
            return False
            
    async def get_session_data(self, session_id: str, key: str) -> Optional[Any]:
        """获取会话数据"""
        if not self._connected:
            return None
            
        try:
            redis_key = f"session:{session_id}:{key}"
            data = await self.redis.get(redis_key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"获取会话数据失败: {e}")
            return None
            
    async def increment_failure_count(self, service_name: str) -> int:
        """增加服务失败计数"""
        if not self._connected:
            return 0
            
        try:
            key = f"failure_count:{service_name}"
            count = await self.redis.incr(key)
            await self.redis.expire(key, 3600)  # 1小时过期
            return count
        except Exception as e:
            logger.error(f"增加失败计数失败: {e}")
            return 0
            
    async def get_failure_count(self, service_name: str) -> int:
        """获取服务失败计数"""
        if not self._connected:
            return 0
            
        try:
            key = f"failure_count:{service_name}"
            count = await self.redis.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"获取失败计数失败: {e}")
            return 0

# 全局Redis实例
redis_client = RedisClient()
