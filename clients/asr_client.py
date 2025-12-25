# clients/asr_client.py
import websockets
import json
import asyncio
import numpy as np
from scipy.signal import resample_poly
from typing import Callable, Optional
from config.settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

class FunASRClient:
    def __init__(self):
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.callback: Optional[Callable] = None
        self._connected = False
        self._listening = False
        
    async def connect(self) -> bool:
        """连接ASR服务"""
        try:
            self.websocket = await websockets.connect(
                config.asr.ws_url,
                ping_interval=30,
                ping_timeout=10
            )
            self._connected = True
            logger.info("ASR服务连接成功")
            return True
        except Exception as e:
            logger.error(f"ASR服务连接失败: {e}")
            self._connected = False
            return False
            
    async def start_listening(self, audio_callback: Callable, text_callback: Callable) -> bool:
        """开始语音识别"""
        if not self._connected:
            if not await self.connect():
                return False
                
        self.callback = text_callback
        self._listening = True
        
        # 启动接收任务
        asyncio.create_task(self._receive_messages())
        
        # 设置音频回调
        audio_callback(self._send_audio)
        
        return True
        
    async def _send_audio(self, audio_data: bytes):
        """发送音频数据到ASR"""
        if not self._connected or not self._listening:
            return
            
        try:
            # 重采样和格式转换
            processed_audio = self._process_audio(audio_data)
            if processed_audio:
                await self.websocket.send(processed_audio)
        except Exception as e:
            logger.error(f"发送音频数据失败: {e}")
            await self._reconnect()
            
    def _process_audio(self, audio_data: bytes) -> bytes:
        """处理音频数据"""
        # 8kHz -> 16kHz 重采样
        try:
            if config.freeswitch.audio_sample_rate != config.asr.sample_rate:
                # 将bytes转换为numpy数组
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # 计算重采样因子
                ratio = config.asr.sample_rate / config.freeswitch.audio_sample_rate
                
                # 使用scipy进行重采样
                resampled = resample_poly(audio_array.astype(float), ratio, 1)
                
                # 转换回bytes
                audio_data = resampled.astype(np.int16).tobytes()
            return audio_data
        except Exception as e:
            logger.error(f"音频处理失败: {e}")
            return b""
            
    async def _receive_messages(self):
        """接收识别结果"""
        while self._listening and self._connected:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                if self.callback:
                    await self.callback(
                        text=data.get('text', ''),
                        is_final=data.get('is_final', False),
                        timestamp=data.get('timestamp', 0)
                    )
                    
            except websockets.ConnectionClosed:
                logger.warning("ASR WebSocket连接断开")
                await self._reconnect()
            except Exception as e:
                logger.error(f"接收ASR消息失败: {e}")
                
    async def _reconnect(self):
        """重新连接"""
        self._connected = False
        self._listening = False
        
        for i in range(3):  # 重试3次
            try:
                await asyncio.sleep(2 ** i)  # 指数退避
                if await self.connect():
                    self._listening = True
                    logger.info("ASR服务重连成功")
                    break
            except Exception as e:
                logger.error(f"ASR重连失败 {i+1}/3: {e}")
                
    async def stop_listening(self):
        """停止监听"""
        self._listening = False
        if self.websocket:
            await self.websocket.close()
