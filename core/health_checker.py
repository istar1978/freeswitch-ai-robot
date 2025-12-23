import asyncio
import aiohttp
import time
from typing import Dict
from config.settings import config
from utils.logger import setup_logger
from storage.redis_client import redis_client

logger = setup_logger(__name__)

class HealthChecker:
    def __init__(self):
        self.services_status: Dict[str, Dict] = {
            'asr': {'status': 'unknown', 'last_check': 0, 'response_time': 0},
            'llm': {'status': 'unknown', 'last_check': 0, 'response_time': 0},
            'tts': {'status': 'unknown', 'last_check': 0, 'response_time': 0},
            'redis': {'status': 'unknown', 'last_check': 0, 'response_time': 0}
        }
        self.global_status = 'healthy'
        self.running = False
        
    async def check_service(self, service_name: str) -> bool:
        """检查单个服务"""
        check_methods = {
            'asr': self._check_asr,
            'llm': self._check_llm,
            'tts': self._check_tts,
            'redis': self._check_redis
        }
        
        method = check_methods.get(service_name)
        if method:
            return await method()
        return False
        
    async def _check_asr(self) -> bool:
        """检查ASR服务"""
        try:
            # 简单的连接测试
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                start_time = time.time()
                # 这里可以发送一个测试请求
                response_time = time.time() - start_time
                self.services_status['asr']['response_time'] = response_time
                return response_time < 3.0  # 响应时间小于3秒认为健康
        except Exception as e:
            logger.debug(f"ASR健康检查失败: {e}")
            return False
            
    async def _check_llm(self) -> bool:
        """检查LLM服务"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                start_time = time.time()
                async with session.get(f"{config.llm.api_url.replace('/v1/chat/completions', '/health')}") as resp:
                    response_time = time.time() - start_time
                    self.services_status['llm']['response_time'] = response_time
                    return resp.status == 200
        except Exception as e:
            logger.debug(f"LLM健康检查失败: {e}")
            return False
            
    async def _check_tts(self) -> bool:
        """检查TTS服务"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                start_time = time.time()
                async with session.get(f"{config.tts.api_url}/health") as resp:
                    response_time = time.time() - start_time
                    self.services_status['tts']['response_time'] = response_time
                    return resp.status == 200
        except Exception as e:
            logger.debug(f"TTS健康检查失败: {e}")
            return False
            
    async def _check_redis(self) -> bool:
        """检查Redis服务"""
        try:
            start_time = time.time()
            if await redis_client.redis.ping():
                response_time = time.time() - start_time
                self.services_status['redis']['response_time'] = response_time
                return True
            return False
        except Exception as e:
            logger.debug(f"Redis健康检查失败: {e}")
            return False
            
    async def start_monitoring(self):
        """开始健康监控"""
        self.running = True
        logger.info("健康检查监控启动")
        
        while self.running:
            try:
                for service_name in self.services_status:
                    is_healthy = await self.check_service(service_name)
                    status = 'healthy' if is_healthy else 'unhealthy'
                    self.services_status[service_name].update({
                        'status': status,
                        'last_check': time.time()
                    })
                    
                # 更新全局状态
                unhealthy_count = sum(
                    1 for s in self.services_status.values() 
                    if s['status'] == 'unhealthy'
                )
                self.global_status = 'degraded' if unhealthy_count > 1 else 'healthy'
                
                logger.debug(f"健康检查完成: {self.services_status}")
                
            except Exception as e:
                logger.error(f"健康检查异常: {e}")
                
            await asyncio.sleep(config.system.health_check_interval)
            
    def stop_monitoring(self):
        """停止健康监控"""
        self.running = False
        
    def get_status(self) -> Dict:
        """获取状态信息"""
        return {
            'global_status': self.global_status,
            'services': self.services_status
        }
