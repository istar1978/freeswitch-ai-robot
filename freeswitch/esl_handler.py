import asyncio
import socket
from typing import Dict, Optional
from config.settings import config
from utils.logger import setup_logger
from core.conversation_manager import ConversationManager

logger = setup_logger(__name__)

class FreeSwitchHandler:
    def __init__(self):
        self.sessions: Dict[str, ConversationManager] = {}
        self.running = False
        self.connected = False
        self.connection = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动FreeSWITCH处理器"""
        self.running = True
        logger.info("FreeSWITCH处理器启动")

        # 启动连接管理
        await self._ensure_connection()

        # 启动心跳检查
        self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())

    async def stop(self):
        """停止FreeSWITCH处理器"""
        self.running = False

        # 取消任务
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.reconnect_task:
            self.reconnect_task.cancel()

        # 断开连接
        await self._disconnect()

        # 清理所有会话
        for session_id, manager in self.sessions.items():
            await manager.stop()
        self.sessions.clear()
        logger.info("FreeSWITCH处理器停止")

    async def _ensure_connection(self):
        """确保连接到FreeSWITCH"""
        if self.connected:
            return True

        for attempt in range(config.freeswitch.reconnect_attempts):
            try:
                logger.info(f"尝试连接FreeSWITCH (尝试 {attempt + 1}/{config.freeswitch.reconnect_attempts})")

                # 这里应该是实际的ESL连接
                # 简化实现，使用socket连接测试
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((config.freeswitch.host, config.freeswitch.port))
                sock.close()

                if result == 0:
                    self.connected = True
                    logger.info("FreeSWITCH连接成功")
                    return True
                else:
                    logger.warning(f"FreeSWITCH连接失败: 端口 {config.freeswitch.port} 无响应")

            except Exception as e:
                logger.error(f"FreeSWITCH连接异常: {e}")

            if attempt < config.freeswitch.reconnect_attempts - 1:
                await asyncio.sleep(config.freeswitch.reconnect_interval)

        logger.error("FreeSWITCH连接失败，启动重连任务")
        if not self.reconnect_task or self.reconnect_task.done():
            self.reconnect_task = asyncio.create_task(self._reconnect_loop())
        return False

    async def _disconnect(self):
        """断开FreeSWITCH连接"""
        if self.connection:
            # 实际实现中关闭ESL连接
            pass
        self.connected = False
        logger.info("FreeSWITCH连接已断开")

    async def _heartbeat_monitor(self):
        """心跳监控"""
        while self.running:
            try:
                if not await self._check_connection():
                    logger.warning("FreeSWITCH连接丢失，尝试重连")
                    await self._ensure_connection()
                else:
                    logger.debug("FreeSWITCH连接正常")

            except Exception as e:
                logger.error(f"心跳检查异常: {e}")

            await asyncio.sleep(config.freeswitch.heartbeat_interval)

    async def _check_connection(self) -> bool:
        """检查连接状态"""
        if not self.connected:
            return False

        try:
            # 简化实现：检查端口是否可达
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((config.freeswitch.host, config.freeswitch.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _reconnect_loop(self):
        """重连循环"""
        while self.running and not self.connected:
            logger.info("执行FreeSWITCH重连...")
            await self._ensure_connection()
            if not self.connected:
                await asyncio.sleep(config.freeswitch.reconnect_interval * 2)
        
    async def handle_incoming_call(self, session_id: str, caller_id: str = None):
        """处理来电"""
        logger.info(f"处理来电: {session_id}, 主叫: {caller_id}")

        # 检查连接状态
        if not await self._ensure_connection():
            logger.error("FreeSWITCH连接不可用，无法处理来电")
            return False

        if session_id in self.sessions:
            logger.warning(f"会话 {session_id} 已存在")
            return False

        try:
            # 创建对话管理器
            manager = ConversationManager(session_id)

            # 设置回调
            manager.on_audio_output = lambda audio: self._send_audio(session_id, audio)
            manager.on_state_change = lambda state: self._on_state_change(session_id, state)
            manager.on_hangup = lambda: self._on_hangup(session_id)

            self.sessions[session_id] = manager

            # 开始对话
            await manager.start()

            logger.info(f"来电处理成功: {session_id}")
            return True

        except Exception as e:
            logger.error(f"处理来电失败 {session_id}: {e}")
            # 清理失败的会话
            if session_id in self.sessions:
                del self.sessions[session_id]
            return False
        
    async def _send_audio(self, session_id: str, audio_data: bytes):
        """发送音频到FreeSWITCH"""
        logger.debug(f"发送音频到会话 {session_id}, 长度: {len(audio_data)}")
        # 实际实现应该通过ESL发送音频数据
        
    async def _on_state_change(self, session_id: str, state: str):
        """处理状态变化"""
        logger.debug(f"会话 {session_id} 状态变化: {state}")
        
    async def _on_hangup(self, session_id: str):
        """处理挂机"""
        logger.info(f"会话 {session_id} 挂机")
        if session_id in self.sessions:
            await self.sessions[session_id].stop()
            del self.sessions[session_id]
