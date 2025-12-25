# outbound/outbound_manager.py
import asyncio
import json
import csv
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import aiohttp
from config.settings import config
from utils.logger import setup_logger
from core.conversation_manager import ConversationManager

logger = setup_logger(__name__)

class OutboundStatus(Enum):
    """外呼状态"""
    PENDING = "pending"
    CALLING = "calling"
    CONNECTED = "connected"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"

@dataclass
class OutboundTask:
    """外呼任务"""
    task_id: str
    phone_number: str
    customer_name: str
    customer_data: Dict
    priority: int = 1
    max_attempts: int = 3
    attempt_count: int = 0
    status: OutboundStatus = OutboundStatus.PENDING
    created_time: datetime = None
    last_attempt_time: Optional[datetime] = None
    completed_time: Optional[datetime] = None
    result: Optional[Dict] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now()
        if self.result is None:
            self.result = {}

    def to_dict(self):
        """转换为字典"""
        data = asdict(self)
        data["status"] = self.status.value
        data["created_time"] = self.created_time.isoformat()
        if self.last_attempt_time:
            data["last_attempt_time"] = self.last_attempt_time.isoformat()
        if self.completed_time:
            data["completed_time"] = self.completed_time.isoformat()
        return data

    def can_attempt(self) -> bool:
        """是否可以尝试呼叫"""
        return self.attempt_count < self.max_attempts and self.status not in [
            OutboundStatus.COMPLETED, OutboundStatus.CONNECTED
        ]

    def record_attempt(self, success: bool = False, result: Dict = None, error: str = None):
        """记录尝试结果"""
        self.attempt_count += 1
        self.last_attempt_time = datetime.now()

        if success:
            self.status = OutboundStatus.CONNECTED
            self.result.update(result or {})
        elif self.attempt_count >= self.max_attempts:
            self.status = OutboundStatus.FAILED
            self.error_message = error or "Max attempts reached"
            self.completed_time = datetime.now()
        else:
            # 根据错误类型设置状态
            if "busy" in (error or "").lower():
                self.status = OutboundStatus.BUSY
            elif "no answer" in (error or "").lower():
                self.status = OutboundStatus.NO_ANSWER
            else:
                self.status = OutboundStatus.FAILED

class OutboundManager:
    """外呼管理器"""

    def __init__(self, fs_handler=None):
        self.fs_handler = fs_handler
        self.tasks: Dict[str, OutboundTask] = {}
        self.active_calls: Dict[str, ConversationManager] = {}
        self.running = False
        self.task_queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动外呼管理器"""
        self.running = True
        self.worker_task = asyncio.create_task(self._process_queue())
        logger.info("外呼管理器已启动")

    async def stop(self):
        """停止外呼管理器"""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()

        # 结束所有活跃呼叫
        for session_id, manager in self.active_calls.items():
            await manager.stop()

        self.active_calls.clear()
        logger.info("外呼管理器已停止")

    async def load_tasks_from_csv(self, csv_file: str, phone_column: str = "phone",
                                 name_column: str = "name") -> int:
        """从CSV文件加载任务"""
        loaded_count = 0
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    phone = row.get(phone_column, "").strip()
                    name = row.get(name_column, "").strip()

                    if phone and name:
                        task = OutboundTask(
                            task_id=f"csv_{int(time.time())}_{loaded_count}",
                            phone_number=phone,
                            customer_name=name,
                            customer_data=row
                        )
                        await self.add_task(task)
                        loaded_count += 1

            logger.info(f"从CSV加载了 {loaded_count} 个外呼任务")
            return loaded_count

        except Exception as e:
            logger.error(f"加载CSV任务失败: {e}")
            return 0

    async def load_tasks_from_json(self, json_file: str) -> int:
        """从JSON文件加载任务"""
        loaded_count = 0
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            tasks_data = data if isinstance(data, list) else data.get("tasks", [])

            for task_data in tasks_data:
                task = OutboundTask(**task_data)
                await self.add_task(task)
                loaded_count += 1

            logger.info(f"从JSON加载了 {loaded_count} 个外呼任务")
            return loaded_count

        except Exception as e:
            logger.error(f"加载JSON任务失败: {e}")
            return 0

    async def add_task(self, task: OutboundTask):
        """添加外呼任务"""
        self.tasks[task.task_id] = task
        await self.task_queue.put(task.task_id)
        logger.info(f"添加外呼任务: {task.task_id} -> {task.phone_number}")

    async def _process_queue(self):
        """处理任务队列"""
        while self.running:
            try:
                # 获取任务
                task_id = await self.task_queue.get()
                task = self.tasks.get(task_id)

                if not task or not task.can_attempt():
                    self.task_queue.task_done()
                    continue

                # 执行外呼
                await self._execute_call(task)
                self.task_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"处理外呼任务异常: {e}")
                await asyncio.sleep(1)

    async def _execute_call(self, task: OutboundTask):
        """执行外呼"""
        logger.info(f"开始外呼: {task.phone_number} ({task.customer_name})")

        try:
            # 这里应该集成实际的FreeSWITCH外呼逻辑
            # 简化实现：模拟外呼过程

            task.status = OutboundStatus.CALLING
            task.last_attempt_time = datetime.now()

            # 模拟呼叫过程
            await asyncio.sleep(2)  # 模拟拨号时间

            # 模拟接通
            if task.attempt_count == 0:  # 第一次尝试成功
                await self._handle_connected_call(task)
            else:
                # 后续尝试可能失败
                task.record_attempt(False, error="Simulated call failure")

        except Exception as e:
            logger.error(f"外呼执行异常: {e}")
            task.record_attempt(False, error=str(e))

    async def _handle_connected_call(self, task: OutboundTask):
        """处理接通的呼叫"""
        session_id = f"outbound_{task.task_id}_{int(time.time())}"

        try:
            # 创建对话管理器
            manager = ConversationManager(session_id)

            # 设置外呼特定的回调
            manager.on_audio_output = lambda audio: self._send_audio_to_freeswitch(session_id, audio)
            manager.on_state_change = lambda state: self._on_call_state_change(session_id, state)
            manager.on_hangup = lambda: self._on_call_hangup(session_id)

            self.active_calls[session_id] = manager

            # 开始对话（外呼场景）
            await manager.start()

            # 等待对话完成或超时
            await asyncio.sleep(30)  # 外呼对话超时时间

            # 结束呼叫
            await manager.stop()
            del self.active_calls[session_id]

            # 记录成功结果
            task.record_attempt(True, {
                "session_id": session_id,
                "duration": 30,
                "conversation_completed": True
            })

        except Exception as e:
            logger.error(f"处理接通呼叫异常: {e}")
            task.record_attempt(False, error=str(e))

    async def _send_audio_to_freeswitch(self, session_id: str, audio_data: bytes):
        """发送音频到FreeSWITCH"""
        # 实际实现需要集成FreeSWITCH外呼音频发送
        logger.debug(f"发送音频到外呼会话 {session_id}")

    async def _on_call_state_change(self, session_id: str, state: str):
        """外呼状态变化"""
        logger.debug(f"外呼会话 {session_id} 状态: {state}")

    async def _on_call_hangup(self, session_id: str):
        """外呼挂机"""
        logger.info(f"外呼会话 {session_id} 结束")
        if session_id in self.active_calls:
            await self.active_calls[session_id].stop()
            del self.active_calls[session_id]

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        return task.to_dict() if task else None

    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        return [task.to_dict() for task in self.tasks.values()]

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.tasks)
        pending = sum(1 for t in self.tasks.values() if t.status == OutboundStatus.PENDING)
        calling = sum(1 for t in self.tasks.values() if t.status == OutboundStatus.CALLING)
        connected = sum(1 for t in self.tasks.values() if t.status == OutboundStatus.CONNECTED)
        completed = sum(1 for t in self.tasks.values() if t.status == OutboundStatus.COMPLETED)
        failed = sum(1 for t in self.tasks.values() if t.status == OutboundStatus.FAILED)

        return {
            "total_tasks": total,
            "pending": pending,
            "calling": calling,
            "connected": connected,
            "completed": completed,
            "failed": failed,
            "active_calls": len(self.active_calls),
            "queue_size": self.task_queue.qsize()
        }