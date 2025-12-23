import audioop
import re
from typing import Union, List

class AudioUtils:
    @staticmethod
    def resample_audio(audio_data: bytes, from_rate: int, to_rate: int, channels: int = 1) -> bytes:
        """音频重采样"""
        try:
            return audioop.ratecv(
                audio_data, 2, channels, from_rate, to_rate, None
            )[0]
        except Exception:
            return audio_data
            
    @staticmethod
    def normalize_volume(audio_data: bytes, target_level: int = 8000) -> bytes:
        """音量标准化"""
        try:
            current_max = max(audioop.max(audio_data, 2), 1)
            factor = target_level / current_max
            return audioop.mul(audio_data, 2, min(factor, 2.0))
        except Exception:
            return audio_data

class TextUtils:
    @staticmethod
    def is_sentence_boundary(text: str) -> bool:
        """判断句子边界"""
        boundary_patterns = [r'[。！？；.!?;]\s*$', r'\n\s*$']
        return any(re.search(pattern, text) for pattern in boundary_patterns)
        
    @staticmethod
    def contains_keywords(text: str, keywords: List[str]) -> bool:
        """检查是否包含关键词"""
        return any(keyword in text for keyword in keywords)
        
    @staticmethod
    def truncate_text(text: str, max_length: int = 500) -> str:
        """截断文本"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

# 工具类实例
audio_utils = AudioUtils()
text_utils = TextUtils()
