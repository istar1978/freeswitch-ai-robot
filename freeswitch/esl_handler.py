import asyncio
from typing import Dict, Optional
from config.settings import config
from utils.logger import setup_logger
from core.conversation_manager import ConversationManager

logger = setup_logger(__name__)

class FreeSwitchHandler:
    def __init__(self):
        self.sessions: Dict[str, ConversationManager] = {}
        self.running = False
        
    async def start(self):
        """启动FreeSWITCH处理器"""
        self.running = True
        logger.info("FreeSWITCH处理器启动")
        # 这里应该连接FreeSWITCH ESL接口
        # 简化实现，仅模拟
        
    async def stop(self):
        """停止FreeSWITCH处理器"""
        self.running = False
        # 清理所有会话
        for session_id, manager in self.sessions.items():
            await manager.stop()
        self.sessions.clear()
        logger.info("FreeSWITCH处理器停止")
        
    async def handle_incoming_call(self, session_id: str):
        """处理来电"""
        logger.info(f"处理来电: {session_id}")
        
        if session_id in self.sessions:
            logger.warning(f"会话 {session_id} 已存在")
            return
            
        # 创建对话管理器
        manager = ConversationManager(session_id)
        
        # 设置回调
        manager.on_audio_output = lambda audio: self._send_audio(session_id, audio)
        manager.on_state_change = lambda state: self._on_state_change(session_id, state)
        manager.on_hangup = lambda: self._on_hangup(session_id)
        
        self.sessions[session_id] = manager
        
        # 开始对话
        await manager.start()
        
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
