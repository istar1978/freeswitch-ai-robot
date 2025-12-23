# core/conversation_manager.py
import asyncio
import time
import random
from typing import Optional, Callable
from enum import Enum
from config.settings import config
from utils.logger import setup_logger
from storage.redis_client import redis_client
from clients.asr_client import FunASRClient
from clients.llm_client import LLMClient
from clients.tts_client import TTSClient

logger = setup_logger(__name__)

class ConversationState(Enum):
    IDLE = "idle"
    ASR_LISTENING = "asr_listening"
    LLM_PROCESSING = "llm_processing"
    TTS_PLAYING = "tts_playing"
    WAITING_USER = "waiting_user"
    ERROR = "error"

class ConversationManager:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = ConversationState.IDLE
        self.current_text = ""
        self.last_voice_time = 0
        self.wait_count = 0
        self.interrupt_count = 0
        self.conversation_history = []
        self.tts_playback_position = 0
        
        # 客户端
        self.asr_client = FunASRClient()
        self.llm_client = LLMClient()
        self.tts_client = TTSClient()
        
        # 回调函数
        self.on_audio_output: Optional[Callable] = None
        self.on_state_change: Optional[Callable] = None
        self.on_hangup: Optional[Callable] = None
        
        # 任务
        self._current_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    async def start(self):
        """开始对话"""
        try:
            logger.info(f"会话 {self.session_id} 开始")
            await self._change_state(ConversationState.ASR_LISTENING)

            # 启动ASR监听
            success = await self.asr_client.start_listening(
                self._send_audio_to_asr,
                self._on_asr_result
            )

            if not success:
                await self._handle_service_failure("asr")
                return

            # 初始问候
            await self._play_greeting()

        except Exception as e:
            logger.error(f"启动对话失败 {self.session_id}: {e}")
            await self._handle_service_failure("system")
            await self._change_state(ConversationState.ERROR)
        
    async def _play_greeting(self):
        """播放问候语"""
        greeting = "您好，我是AI助手，请问有什么可以帮您？"
        await self._synthesize_and_play(greeting)
        
    async def _on_asr_result(self, text: str, is_final: bool, timestamp: int):
        """处理ASR识别结果"""
        if not text.strip():
            return
            
        self.last_voice_time = time.time()
        
        if self.state == ConversationState.TTS_PLAYING:
            # 处理打断
            await self._handle_interrupt(text)
            return
            
        if is_final:
            await self._process_complete_sentence(text)
        else:
            await self._process_partial_result(text)
            
    async def _process_complete_sentence(self, text: str):
        """处理完整句子"""
        logger.info(f"完整识别: {text}")
        
        # 检查是否需要等待
        if any(keyword in text for keyword in config.system.wait_keywords):
            should_wait = await self._check_wait_intent(text)
            if should_wait:
                return
                
        # 添加到历史
        self.conversation_history.append({"role": "user", "content": text})
        
        # 处理用户输入
        await self._change_state(ConversationState.LLM_PROCESSING)
        await self._process_with_llm()
        
    async def _process_partial_result(self, text: str):
        """处理部分结果"""
        # 检查打断关键词
        if any(keyword in text for keyword in config.system.interrupt_keywords):
            await self._handle_interrupt(text)
            
    async def _check_wait_intent(self, text: str) -> bool:
        """检查等待意图"""
        prompt = f"""
        用户说: "{text}"
        请判断用户是否要求暂停或等待？
        只回复"是"或"否"
        """
        
        try:
            response = await self.llm_client.quick_query([
                {"role": "system", "content": "你是一个意图判断助手"},
                {"role": "user", "content": prompt}
            ])
            
            if "是" in response:
                self.wait_count += 1
                if self.wait_count >= 2:
                    await self._ask_follow_up_question()
                else:
                    await self._acknowledge_wait()
                return True
                
        except Exception as e:
            logger.error(f"等待意图判断失败: {e}")
            
        return False
        
    async def _process_with_llm(self):
        """使用LLM处理对话"""
        try:
            full_response = ""
            async for chunk in self.llm_client.streaming_query(self.conversation_history):
                if self._stop_event.is_set():
                    break
                    
                full_response += chunk
                
                # 实时TTS合成（按句子边界）
                if self._is_sentence_boundary(chunk):
                    await self._synthesize_and_play(full_response)
                    full_response = ""
                    
            if full_response:
                await self._synthesize_and_play(full_response)
                
            # 添加助手回复到历史
            if full_response:
                self.conversation_history.append({"role": "assistant", "content": full_response})
                
            await self._change_state(ConversationState.ASR_LISTENING)
            
        except Exception as e:
            logger.error(f"LLM处理失败: {e}")
            await self._play_fallback()
            
    async def _handle_interrupt(self, text: str):
        """处理用户打断"""
        logger.info(f"用户打断: {text}")
        self.interrupt_count += 1
        
        # 停止当前TTS
        self._stop_event.set()
        
        # 记录打断上下文
        interrupt_context = f"用户在第{self.tts_playback_position}字处打断，说: {text}"
        self.conversation_history.append({
            "role": "system", 
            "content": interrupt_context
        })
        
        await self._change_state(ConversationState.ASR_LISTENING)
        self._stop_event.clear()
        
    async def _synthesize_and_play(self, text: str):
        """合成并播放语音"""
        if not text.strip():
            return

        previous_state = self.state
        await self._change_state(ConversationState.TTS_PLAYING)
        self.tts_playback_position = len(text)

        try:
            async for audio_data in self.tts_client.streaming_synthesize(text):
                if self._stop_event.is_set():
                    logger.info("TTS播放被中断")
                    break

                if self.on_audio_output:
                    await self.on_audio_output(audio_data)

            # 恢复到之前的状态或ASR监听状态
            if not self._stop_event.is_set():
                await self._change_state(ConversationState.ASR_LISTENING)

        except Exception as e:
            logger.error(f"TTS合成失败: {e}")
            await self._handle_service_failure("tts")
            # 尝试播放降级回复
            try:
                await self._play_fallback()
            except Exception as fallback_error:
                logger.error(f"降级回复也失败: {fallback_error}")
                # 确保状态正确
                await self._change_state(ConversationState.ERROR)
            
    async def _play_fallback(self):
        """播放降级回复"""
        response = random.choice(config.system.fallback_responses)
        await self._synthesize_and_play(response)
        
    async def _change_state(self, new_state: ConversationState):
        """改变状态"""
        self.state = new_state
        if self.on_state_change:
            await self.on_state_change(new_state.value)
            
    def _is_sentence_boundary(self, text: str) -> bool:
        """判断句子边界"""
        boundary_patterns = ['。', '！', '？', '；', '\n', '.', '!', '?', ';']
        return any(text.endswith(pattern) for pattern in boundary_patterns)
        
    async def _handle_service_failure(self, service_name: str):
        """处理服务失败"""
        failure_count = await redis_client.increment_failure_count(service_name)
        logger.error(f"服务 {service_name} 失败，计数: {failure_count}")
        
        if failure_count >= config.system.system_failure_threshold:
            await self._play_system_unavailable()
            if self.on_hangup:
                await self.on_hangup()
        else:
            await self._play_fallback()
            
    async def _play_system_unavailable(self):
        """播放系统不可用提示"""
        message = "系统暂时不可用，请稍后再试。"
        await self._synthesize_and_play(message)
        
    async def stop(self):
        """停止对话"""
        self._stop_event.set()
        await self.asr_client.stop_listening()
        logger.info(f"会话 {self.session_id} 结束")
