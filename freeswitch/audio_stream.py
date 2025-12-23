import asyncio
from typing import Callable, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AudioStream:
    def __init__(self):
        self.audio_callback: Optional[Callable] = None
        self.streaming = False
        
    def set_audio_callback(self, callback: Callable):
        """设置音频回调"""
        self.audio_callback = callback
        
    async def start_streaming(self):
        """开始音频流"""
        self.streaming = True
        logger.info("音频流开始")
        
    async def stop_streaming(self):
        """停止音频流"""
        self.streaming = False
        logger.info("音频流停止")
        
    async def send_audio(self, audio_data: bytes):
        """发送音频数据"""
        if self.streaming and self.audio_callback:
            await self.audio_callback(audio_data)
