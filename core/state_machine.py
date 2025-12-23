from enum import Enum
from typing import Callable, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

class State(Enum):
    INIT = "init"
    READY = "ready"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"
    SHUTDOWN = "shutdown"

class StateMachine:
    def __init__(self):
        self.state = State.INIT
        self._transitions = {}
        self._on_state_change: Optional[Callable] = None
        
    def add_transition(self, from_state: State, to_state: State, condition: Callable = None):
        """添加状态转换"""
        if from_state not in self._transitions:
            self._transitions[from_state] = []
        self._transitions[from_state].append((to_state, condition))
        
    async def transition(self, to_state: State, data: dict = None):
        """执行状态转换"""
        if data is None:
            data = {}
            
        # 检查转换是否允许
        allowed_transitions = self._transitions.get(self.state, [])
        allowed = any(to_state == transition[0] for transition in allowed_transitions)
        
        if not allowed:
            logger.warning(f"不允许的状态转换: {self.state} -> {to_state}")
            return False
            
        old_state = self.state
        self.state = to_state
        
        logger.debug(f"状态转换: {old_state} -> {to_state}")
        
        if self._on_state_change:
            await self._on_state_change(old_state, to_state, data)
            
        return True
        
    def set_state_change_callback(self, callback: Callable):
        """设置状态变化回调"""
        self._on_state_change = callback
        
    def can_transition(self, to_state: State) -> bool:
        """检查是否可以转换到目标状态"""
        allowed_transitions = self._transitions.get(self.state, [])
        return any(to_state == transition[0] for transition in allowed_transitions)
