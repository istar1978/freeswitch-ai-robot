import asyncio
import wave
import io
import tempfile
import os
from typing import Callable, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AudioStreamHandler:
    """音频流处理器 - 处理FreeSWITCH音频流"""
    
    def __init__(self, instance, session_id: str):
        """
        Args:
            instance: FreeSwitchInstance实例
            session_id: 会话session ID (UUID)
        """
        self.instance = instance
        self.session_id = session_id
        self.streaming = False
        self.audio_buffer = asyncio.Queue()
        self.temp_files = []
        self._stream_task: Optional[asyncio.Task] = None
        
    async def start_streaming(self):
        """开始音频流"""
        if self.streaming:
            logger.warning(f"会话 {self.session_id} 音频流已经开启")
            return
            
        self.streaming = True
        self._stream_task = asyncio.create_task(self._process_audio_stream())
        logger.info(f"会话 {self.session_id} 音频流开始")
        
    async def stop_streaming(self):
        """停止音频流"""
        if not self.streaming:
            return
            
        self.streaming = False
        
        # 等待处理任务完成
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        
        # 清理音频缓冲
        while not self.audio_buffer.empty():
            try:
                self.audio_buffer.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        # 清理临时文件
        await self._cleanup_temp_files()
        
        logger.info(f"会话 {self.session_id} 音频流停止")
        
    async def send_audio(self, audio_data: bytes):
        """发送音频数据到FreeSWITCH
        
        Args:
            audio_data: PCM音频数据 (16kHz, 16-bit, mono)
        """
        if not self.streaming:
            logger.warning(f"会话 {self.session_id} 音频流未开启，跳过音频数据")
            return
            
        try:
            # 将音频数据放入队列
            await self.audio_buffer.put(audio_data)
            logger.debug(f"会话 {self.session_id} 音频数据入队: {len(audio_data)} bytes")
        except Exception as e:
            logger.error(f"发送音频失败: {e}")
            
    async def _process_audio_stream(self):
        """处理音频流 - 从队列中读取并播放"""
        while self.streaming:
            try:
                # 从队列获取音频数据
                audio_data = await asyncio.wait_for(
                    self.audio_buffer.get(),
                    timeout=1.0
                )
                
                # 播放音频
                await self._play_audio_chunk(audio_data)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"处理音频流异常: {e}")
                await asyncio.sleep(0.1)
                
    async def _play_audio_chunk(self, audio_data: bytes):
        """播放音频块
        
        Args:
            audio_data: PCM音频数据
        """
        try:
            # 创建临时WAV文件
            temp_file = await self._create_wav_file(audio_data)
            
            if temp_file:
                # 通过ESL播放音频文件
                await self.instance.play_audio(self.session_id, temp_file)
                
                # 记录临时文件以便后续清理
                self.temp_files.append(temp_file)
                
                # 如果临时文件太多，清理旧文件
                if len(self.temp_files) > 100:
                    await self._cleanup_old_files(50)
                    
        except Exception as e:
            logger.error(f"播放音频块失败: {e}")
            
    async def _create_wav_file(self, pcm_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        """创建WAV文件
        
        Args:
            pcm_data: PCM音频数据
            sample_rate: 采样率
            
        Returns:
            临时文件路径
        """
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
                
            # 写入WAV数据
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_data)
                
            logger.debug(f"创建WAV文件: {temp_path}, 大小: {len(pcm_data)} bytes")
            return temp_path
            
        except Exception as e:
            logger.error(f"创建WAV文件失败: {e}")
            return None
            
    async def _cleanup_temp_files(self):
        """清理所有临时文件"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"删除临时文件失败 {temp_file}: {e}")
        
        self.temp_files.clear()
        
    async def _cleanup_old_files(self, keep_count: int):
        """清理旧临时文件，保留最近的N个"""
        files_to_delete = self.temp_files[:-keep_count]
        for temp_file in files_to_delete:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"删除旧文件失败 {temp_file}: {e}")
        
        self.temp_files = self.temp_files[-keep_count:]


class AudioStream:
    """[已弃用] 简单的音频流 - 保留以保持兼容性"""
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
