# clients/llm_client.py
import aiohttp
import json
import asyncio
from typing import AsyncGenerator, List, Dict, Any
from config.settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

class LLMClient:
    def __init__(self):
        self.session: aiohttp.ClientSession = None
        self.timeout = aiohttp.ClientTimeout(total=config.llm.timeout)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def streaming_query(self, messages: List[Dict[str, str]], 
                            max_tokens: int = None) -> AsyncGenerator[str, None]:
        """流式查询LLM"""
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            
        payload = {
            "model": config.llm.model,
            "messages": messages,
            "stream": True,
            "temperature": config.llm.temperature,
            "max_tokens": max_tokens or config.llm.max_tokens
        }
        
        try:
            async with self.session.post(
                config.llm.api_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"LLM请求失败: {response.status} - {error_text}")
                    yield "抱歉，我暂时无法处理您的请求。"
                    return
                    
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                            
                        try:
                            chunk_data = json.loads(data)
                            if 'choices' in chunk_data and chunk_data['choices']:
                                delta = chunk_data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    yield delta['content']
                        except json.JSONDecodeError:
                            continue
                            
        except asyncio.TimeoutError:
            logger.error("LLM请求超时")
            yield "思考时间过长，请稍等。"
        except Exception as e:
            logger.error(f"LLM请求异常: {e}")
            yield "服务暂时不可用，请稍后再试。"
            
    async def quick_query(self, messages: List[Dict[str, str]], 
                         max_tokens: int = 50) -> str:
        """快速查询（用于意图判断等简单任务）"""
        result = ""
        async for chunk in self.streaming_query(messages, max_tokens):
            result += chunk
        return result
