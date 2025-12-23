import aiohttp
import json
import asyncio
from typing import AsyncGenerator
from config.settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

class TTSClient:
    def __init__(self):
        self.session: aiohttp.ClientSession = None
        self.timeout = aiohttp.ClientTimeout(total=30)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def streaming_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """流式语音合成"""
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            
        payload = {
            "text": text,
            "voice": config.tts.voice,
            "sample_rate": config.tts.sample_rate,
            "format": config.tts.format
        }
        
        try:
            async with self.session.post(
                config.tts.api_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"TTS请求失败: {response.status} - {error_text}")
                    return
                    
                async for chunk in response.content.iter_chunked(config.tts.chunk_size):
                    if chunk:
                        yield chunk
                        
        except asyncio.TimeoutError:
            logger.error("TTS请求超时")
        except Exception as e:
            logger.error(f"TTS请求异常: {e}")
            
    async def quick_synthesize(self, text: str) -> bytes:
        """快速语音合成"""
        result = b""
        async for chunk in self.streaming_synthesize(text):
            result += chunk
        return result
