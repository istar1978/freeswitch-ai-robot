# storage/redis_client.py
import redis.asyncio as redis
import json
import asyncio
from typing import Any, Optional, Dict, List
from config.settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

class RedisClient:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self._connected = False
        self._sync_queue = asyncio.Queue()  # 异步同步队列
        self._sync_task: Optional[asyncio.Task] = None
        
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
            
            # 启动异步同步任务
            self._sync_task = asyncio.create_task(self._process_sync_queue())
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self._connected = False
    
    async def disconnect(self):
        """断开Redis连接"""
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        
        if self.redis:
            await self.redis.close()
            self._connected = False
            logger.info("Redis连接已断开")
            
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

    # ========== 配置缓存管理 ==========
    
    async def set_config(self, config_type: str, config_id: str, config_data: Dict, expire: int = 86400):
        """设置配置到Redis
        
        Args:
            config_type: 配置类型 (scenario, freeswitch, gateway, entry_point, campaign)
            config_id: 配置ID
            config_data: 配置数据
            expire: 过期时间(秒), 默认24小时
        """
        if not self._connected:
            return False
            
        try:
            key = f"config:{config_type}:{config_id}"
            await self.redis.setex(key, expire, json.dumps(config_data, default=str))
            
            # 同时添加到配置列表
            list_key = f"config:{config_type}:list"
            await self.redis.sadd(list_key, config_id)
            
            logger.debug(f"配置已缓存: {key}")
            return True
        except Exception as e:
            logger.error(f"设置配置缓存失败: {e}")
            return False
    
    async def get_config(self, config_type: str, config_id: str) -> Optional[Dict]:
        """从Redis获取配置"""
        if not self._connected:
            return None
            
        try:
            key = f"config:{config_type}:{config_id}"
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"获取配置缓存失败: {e}")
            return None
    
    async def get_all_configs(self, config_type: str) -> List[Dict]:
        """获取某类型的所有配置"""
        if not self._connected:
            return []
            
        try:
            list_key = f"config:{config_type}:list"
            config_ids = await self.redis.smembers(list_key)
            
            configs = []
            for config_id in config_ids:
                config = await self.get_config(config_type, config_id)
                if config:
                    configs.append(config)
            
            return configs
        except Exception as e:
            logger.error(f"获取所有配置失败: {e}")
            return []
    
    async def delete_config(self, config_type: str, config_id: str):
        """删除配置缓存"""
        if not self._connected:
            return False
            
        try:
            key = f"config:{config_type}:{config_id}"
            await self.redis.delete(key)
            
            # 从列表中移除
            list_key = f"config:{config_type}:list"
            await self.redis.srem(list_key, config_id)
            
            logger.debug(f"配置缓存已删除: {key}")
            return True
        except Exception as e:
            logger.error(f"删除配置缓存失败: {e}")
            return False
    
    async def clear_all_configs(self, config_type: str = None):
        """清除所有配置缓存"""
        if not self._connected:
            return False
            
        try:
            if config_type:
                # 清除特定类型
                pattern = f"config:{config_type}:*"
            else:
                # 清除所有配置
                pattern = "config:*"
            
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
            
            logger.info(f"配置缓存已清除: {pattern}")
            return True
        except Exception as e:
            logger.error(f"清除配置缓存失败: {e}")
            return False

    # ========== 通话记录缓存管理 ==========
    
    async def create_call_record(self, session_id: str, call_data: Dict):
        """创建通话记录到Redis"""
        if not self._connected:
            return False
            
        try:
            key = f"call:{session_id}"
            await self.redis.setex(key, 7200, json.dumps(call_data, default=str))  # 2小时过期
            
            # 添加到待同步队列
            await self._sync_queue.put({
                'action': 'create_call',
                'session_id': session_id,
                'data': call_data
            })
            
            logger.debug(f"通话记录已缓存: {session_id}")
            return True
        except Exception as e:
            logger.error(f"创建通话记录缓存失败: {e}")
            return False
    
    async def update_call_record(self, session_id: str, update_data: Dict):
        """更新通话记录到Redis"""
        if not self._connected:
            return False
            
        try:
            key = f"call:{session_id}"
            
            # 获取现有数据
            existing_data = await self.redis.get(key)
            if existing_data:
                call_data = json.loads(existing_data)
                call_data.update(update_data)
            else:
                call_data = update_data
            
            # 更新Redis
            await self.redis.setex(key, 7200, json.dumps(call_data, default=str))
            
            # 添加到待同步队列
            await self._sync_queue.put({
                'action': 'update_call',
                'session_id': session_id,
                'data': call_data
            })
            
            logger.debug(f"通话记录已更新: {session_id}")
            return True
        except Exception as e:
            logger.error(f"更新通话记录缓存失败: {e}")
            return False
    
    async def get_call_record(self, session_id: str) -> Optional[Dict]:
        """从Redis获取通话记录"""
        if not self._connected:
            return None
            
        try:
            key = f"call:{session_id}"
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"获取通话记录失败: {e}")
            return None
    
    async def _process_sync_queue(self):
        """处理异步同步队列 - 将Redis数据同步到MySQL"""
        logger.info("异步同步队列已启动")
        
        while True:
            try:
                # 批量处理
                batch = []
                try:
                    # 获取第一个任务
                    item = await asyncio.wait_for(self._sync_queue.get(), timeout=5.0)
                    batch.append(item)
                    
                    # 尝试获取更多任务（非阻塞）
                    while len(batch) < 100:  # 最多批量100条
                        try:
                            item = self._sync_queue.get_nowait()
                            batch.append(item)
                        except asyncio.QueueEmpty:
                            break
                            
                except asyncio.TimeoutError:
                    continue
                
                if batch:
                    await self._sync_batch_to_mysql(batch)
                    
            except asyncio.CancelledError:
                logger.info("异步同步队列已停止")
                break
            except Exception as e:
                logger.error(f"处理同步队列异常: {e}")
                await asyncio.sleep(1)
    
    async def _sync_batch_to_mysql(self, batch: List[Dict]):
        """批量同步数据到MySQL"""
        try:
            from storage.mysql_client import mysql_client
            
            for item in batch:
                action = item.get('action')
                
                try:
                    if action == 'create_call':
                        await mysql_client.create_call_record_from_redis(item['data'])
                    elif action == 'update_call':
                        await mysql_client.update_call_record_from_redis(
                            item['session_id'], 
                            item['data']
                        )
                    elif action == 'update_config':
                        await mysql_client.update_config_from_redis(
                            item['config_type'],
                            item['config_id'],
                            item['data']
                        )
                except Exception as e:
                    logger.error(f"同步单条数据失败: {e}")
            
            logger.debug(f"批量同步完成: {len(batch)}条")
            
        except Exception as e:
            logger.error(f"批量同步到MySQL失败: {e}")
    
    async def queue_config_sync(self, config_type: str, config_id: str, config_data: Dict):
        """将配置更新加入同步队列"""
        try:
            await self._sync_queue.put({
                'action': 'update_config',
                'config_type': config_type,
                'config_id': config_id,
                'data': config_data
            })
            logger.debug(f"配置同步已加入队列: {config_type}:{config_id}")
        except Exception as e:
            logger.error(f"加入配置同步队列失败: {e}")

# 全局Redis实例
redis_client = RedisClient()
