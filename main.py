#!/usr/bin/env python3
import asyncio
import signal
import sys
import time
from contextlib import asynccontextmanager
from config.settings import config
from utils.logger import setup_logger
from storage.redis_client import redis_client
from freeswitch.esl_handler import FreeSwitchHandler
from freeswitch.dialplan_generator import DialplanGenerator
from core.health_checker import HealthChecker
from api.server import APIServer
from tests.call_tester import CallTester
from outbound.outbound_manager import OutboundManager
from scenarios.scenario_manager import ScenarioManager

logger = setup_logger(__name__)

class AIRobotApplication:
    def __init__(self):
        self.fs_handler = FreeSwitchHandler()
        self.health_checker = HealthChecker()
        self.dialplan_generator = DialplanGenerator()
        self.api_server = APIServer(self.fs_handler, self.call_tester, self.outbound_manager, self.scenario_manager)
        self.call_tester = CallTester()
        self.outbound_manager = OutboundManager(self.fs_handler)
        self.scenario_manager = ScenarioManager()
        self.running = False
        self.restart_count = 0
        self.max_restarts = 5
        self.restart_delay = 10

    async def startup(self):
        """启动应用"""
        logger.info("AI机器人应用启动中...")

        try:
            # 连接Redis
            await redis_client.connect()

            # 生成拨号计划文件
            try:
                self.dialplan_generator.save_dialplan_files()
                logger.info("拨号计划文件生成成功")
            except Exception as e:
                logger.warning(f"拨号计划文件生成失败: {e}")

            # 启动健康检查
            asyncio.create_task(self.health_checker.start_monitoring())

            # 启动FreeSWITCH处理器
            await self.fs_handler.start()

            # 启动API服务器
            await self.api_server.start()

            # 启动外呼管理器
            await self.outbound_manager.start()

            # 加载场景配置
            await self.scenario_manager.load_scenarios()

            self.running = True
            logger.info("AI机器人应用启动完成")

        except Exception as e:
            logger.error(f"应用启动失败: {e}")
            raise

    async def shutdown(self, signal_name: str = None):
        """关闭应用"""
        logger.info(f"AI机器人应用关闭中... (信号: {signal_name})")
        self.running = False

        try:
            await self.api_server.stop()
            await self.fs_handler.stop()
            await self.outbound_manager.stop()
            logger.info("AI机器人应用已关闭")
        except Exception as e:
            logger.error(f"应用关闭异常: {e}")

    async def run(self):
        """运行主循环"""
        await self.startup()

        # 设置信号处理
        loop = asyncio.get_event_loop()
        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._signal_handler(s)))

        try:
            while self.running:
                # 定期检查服务健康状态
                await self._check_service_health()
                await asyncio.sleep(30)  # 每30秒检查一次

        except Exception as e:
            logger.error(f"主循环异常: {e}")
            await self._handle_critical_error(e)
        finally:
            await self.shutdown()

    async def _signal_handler(self, signal):
        """信号处理"""
        signal_name = signal.name if hasattr(signal, 'name') else str(signal)
        logger.info(f"收到信号: {signal_name}")
        await self.shutdown(signal_name)

    async def _check_service_health(self):
        """检查服务健康状态"""
        try:
            status = self.health_checker.get_status()
            if status['global_status'] == 'unhealthy':
                logger.warning("检测到服务不健康，可能需要重启")
                # 这里可以添加告警通知逻辑
        except Exception as e:
            logger.error(f"健康检查异常: {e}")

    async def _handle_critical_error(self, error: Exception):
        """处理严重错误"""
        logger.error(f"发生严重错误: {error}")

        if self.restart_count < self.max_restarts:
            self.restart_count += 1
            logger.info(f"尝试重启应用 ({self.restart_count}/{self.max_restarts})")

            try:
                await asyncio.sleep(self.restart_delay)
                await self.restart()
            except Exception as restart_error:
                logger.error(f"重启失败: {restart_error}")
                sys.exit(1)
        else:
            logger.error("达到最大重启次数，退出应用")
            sys.exit(1)

    async def restart(self):
        """重启应用"""
        logger.info("开始重启应用...")

        try:
            # 停止当前服务
            await self.shutdown("restart")

            # 等待一段时间
            await asyncio.sleep(2)

            # 重新初始化
            self.fs_handler = FreeSwitchHandler()
            self.health_checker = HealthChecker()
            self.api_server = APIServer(self.fs_handler, self.call_tester, self.outbound_manager, self.scenario_manager)
            self.outbound_manager = OutboundManager(self.fs_handler)
            self.scenario_manager = ScenarioManager()

            # 重新启动
            await self.startup()
            logger.info("应用重启成功")

        except Exception as e:
            logger.error(f"应用重启失败: {e}")
            raise

async def main():
    """主函数"""
    app = None
    while True:
        try:
            app = AIRobotApplication()
            await app.run()
            break  # 正常退出

        except Exception as e:
            logger.error(f"应用运行异常: {e}")

            if app and app.restart_count >= app.max_restarts:
                logger.error("达到最大重启次数，退出")
                sys.exit(1)

            # 等待后重试
            logger.info("等待后重试...")
            await asyncio.sleep(5)

        except KeyboardInterrupt:
            logger.info("收到键盘中断，退出")
            if app:
                await app.shutdown("keyboard_interrupt")
            sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
