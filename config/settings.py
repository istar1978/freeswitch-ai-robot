import os
import logging
from dataclasses import dataclass
from typing import Dict, Any, Tuple

@dataclass
class ASRConfig:
    ws_url: str = os.getenv("ASR_WS_URL", "ws://localhost:10095")
    sample_rate: int = 16000
    vad_threshold: int = 800
    max_wait_time: int = 5000
    chunk_size: int = 1024
    reconnect_attempts: int = 3

@dataclass
class LLMConfig:
    api_url: str = os.getenv("LLM_API_URL", "http://localhost:8080/v1/chat/completions")
    timeout: int = 10
    max_tokens: int = 500
    temperature: float = 0.7
    model: str = os.getenv("LLM_MODEL", "deepseek-chat")
    quick_query_tokens: int = 50

@dataclass
class TTSConfig:
    api_url: str = os.getenv("TTS_API_URL", "http://localhost:8000/tts")
    voice: str = "default"
    sample_rate: int = 24000
    format: str = "wav"
    chunk_size: int = 4096

@dataclass
class RedisConfig:
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", 6379))
    db: int = int(os.getenv("REDIS_DB", 0))
    password: str = os.getenv("REDIS_PASSWORD", "")
    max_connections: int = 20

@dataclass
class FreeSwitchConfig:
    host: str = os.getenv("FS_HOST", "localhost")
    port: int = int(os.getenv("FS_PORT", 8021))
    password: str = os.getenv("FS_PASSWORD", "ClueCon")
    audio_sample_rate: int = 8000
    audio_channels: int = 1
    reconnect_attempts: int = 3
    reconnect_interval: int = 5
    heartbeat_interval: int = 30
    dialplan_context: str = os.getenv("FS_DIALPLAN_CONTEXT", "ai-robot")
    dialplan_extension: str = os.getenv("FS_DIALPLAN_EXTENSION", "ai-robot")
    dialplan_priority: int = 1

@dataclass
class SystemConfig:
    fallback_retry_count: int = 3
    system_failure_threshold: int = 5
    health_check_interval: int = 30
    session_timeout: int = 3600
    max_concurrent_calls: int = 100
    max_conversation_history: int = 10
    
    wait_keywords: Tuple[str, ...] = ("等一下", "稍等", "等等", "慢点", "等会")
    interrupt_keywords: Tuple[str, ...] = ("不对", "错了", "不是", "停", "打断一下")
    
    fallback_responses: Tuple[str, ...] = (
        "请稍等，我正在思考",
        "嗯，让我想想",
        "这个问题需要多考虑一下",
        "请稍等片刻"
    )
    
    system_responses: Dict[str, str] = None
    
    def __post_init__(self):
        if self.system_responses is None:
            self.system_responses = {
                "greeting": "您好，我是AI助手，请问有什么可以帮您？",
                "waiting": "好的，我稍等一下",
                "system_busy": "系统暂时繁忙，请稍后再试",
                "goodbye": "感谢您的来电，再见"
            }

class Config:
    asr = ASRConfig()
    llm = LLMConfig()
    tts = TTSConfig()
    redis = RedisConfig()
    freeswitch = FreeSwitchConfig()
    system = SystemConfig()
    
    # 日志配置
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = '/var/log/ai-robot/application.log'

config = Config()
