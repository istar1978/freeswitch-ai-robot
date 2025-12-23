#!/usr/bin/env python3
import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from config.settings import config
from utils.logger import setup_logger
from storage.redis_client import redis_client
from freeswitch.esl_handler import FreeSwitchHandler
from core.health_checker import HealthChecker

logger = setup_logger(__name__)

class AIRobotApplication:
    def __init__(self):
        self.fs_handler = FreeSwitchHandler()
        self.health_checker = HealthChecker()
        self.running = False
        
    async def startup(self):
        """启动应用"""
        logger.info("AI机器人应用启动中...")
        
        # 连接Redis
        await redis_client.connect()
        
        # 启动健康检查
        asyncio.create_task(self.health_checker.start_monitoring())
        
        # 启动FreeSWITCH处理器
        await self.fs_handler.start()
        
        self.running = True
        logger.info("AI机器人应用启动完成")
        
    async def shutdown(self):
        """关闭应用"""
        logger.info("AI机器人应用关闭中...")
        self.running = False
        await self.fs_handler.stop()
        logger.info("AI机器人应用已关闭")
        
    async def run(self):
        """运行主循环"""
        await self.startup()
        
        # 设置信号处理
        loop = asyncio.get_event_loop()
        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
        
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        finally:
            await self.shutdown()

async def main():
    app = AIRobotApplication()
    try:
        await app.run()
    except Exception as e:
        logger.error(f"应用运行异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
