import asyncio
import socket
from typing import Dict, Optional, List
from config.settings import config
from utils.logger import setup_logger
from core.conversation_manager import ConversationManager

logger = setup_logger(__name__)

class FreeSwitchInstance:
    """FreeSWITCH实例"""

    def __init__(self, instance_id: str, host: str, port: int, password: str, scenario_mapping: Dict[str, str]):
        self.instance_id = instance_id
        self.host = host
        self.port = port
        self.password = password
        self.scenario_mapping = scenario_mapping
        self.connected = False
        self.connection = None
        self.sessions: Dict[str, ConversationManager] = {}

    async def connect(self) -> bool:
        """连接到FreeSWITCH实例"""
        try:
            # 这里应该是实际的ESL连接实现
            # 暂时使用socket连接测试
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, self.port))
            sock.close()

            if result == 0:
                self.connected = True
                logger.info(f"FreeSWITCH实例 {self.instance_id} 连接成功")
                return True
            else:
                logger.warning(f"FreeSWITCH实例 {self.instance_id} 连接失败: 端口 {self.port} 无响应")
                return False

        except Exception as e:
            logger.error(f"FreeSWITCH实例 {self.instance_id} 连接异常: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self.connection:
            # 实际实现中关闭ESL连接
            pass
        self.connected = False
        logger.info(f"FreeSWITCH实例 {self.instance_id} 连接已断开")

    def get_scenario_for_entry_point(self, entry_point: str) -> Optional[str]:
        """根据入口点获取场景ID"""
        return self.scenario_mapping.get(entry_point)

class FreeSwitchHandler:
    """FreeSWITCH处理器 - 支持多实例"""

    def __init__(self):
        self.instances: Dict[str, FreeSwitchInstance] = {}
        self.running = False
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动FreeSWITCH处理器"""
        self.running = True
        logger.info("FreeSWITCH处理器启动")

        # 从数据库加载实例配置
        await self._load_instances_from_db()

        # 启动心跳检查
        self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())

    async def stop(self):
        """停止FreeSWITCH处理器"""
        self.running = False

        # 取消任务
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.reconnect_task:
            self.reconnect_task.cancel()

        # 断开所有实例连接
        for instance in self.instances.values():
            await instance.disconnect()

        self.instances.clear()
        logger.info("FreeSWITCH处理器停止")

    async def _load_instances_from_db(self):
        """从数据库加载FreeSWITCH实例配置"""
        try:
            from storage.mysql_client import mysql_client
            configs = await mysql_client.get_freeswitch_configs()

            for config in configs:
                if config.is_active:
                    instance = FreeSwitchInstance(
                        instance_id=config.instance_id,
                        host=config.host,
                        port=config.port,
                        password=config.password,
                        scenario_mapping=config.scenario_mapping or {}
                    )
                    self.instances[config.instance_id] = instance
                    logger.info(f"已加载FreeSWITCH实例: {config.instance_id}")

        except Exception as e:
            logger.error(f"从数据库加载FreeSWITCH实例失败: {e}")
            # 创建默认实例
            await self._create_default_instance()

    async def _create_default_instance(self):
        """创建默认FreeSWITCH实例"""
        instance = FreeSwitchInstance(
            instance_id="default",
            host=config.freeswitch.host,
            port=config.freeswitch.port,
            password=config.freeswitch.password,
            scenario_mapping={"default": "default"}
        )
        self.instances["default"] = instance
        logger.info("已创建默认FreeSWITCH实例")

    async def _heartbeat_monitor(self):
        """心跳监控所有实例"""
        while self.running:
            try:
                for instance_id, instance in self.instances.items():
                    if not await self._check_instance_connection(instance):
                        logger.warning(f"FreeSWITCH实例 {instance_id} 连接丢失，尝试重连")
                        await instance.connect()
                    else:
                        logger.debug(f"FreeSWITCH实例 {instance_id} 连接正常")

            except Exception as e:
                logger.error(f"心跳检查异常: {e}")

            await asyncio.sleep(config.freeswitch.heartbeat_interval)

    async def _check_instance_connection(self, instance: FreeSwitchInstance) -> bool:
        """检查实例连接状态"""
        if not instance.connected:
            return False

        try:
            # 检查端口是否可达
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((instance.host, instance.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def handle_incoming_call(self, session_id: str, instance_id: str = "default", scenario_id: str = None, caller_id: str = None):
        """处理来电"""
        logger.info(f"处理来电: {session_id}, 实例: {instance_id}, 场景: {scenario_id}, 主叫: {caller_id}")

        # 获取实例
        instance = self.instances.get(instance_id)
        if not instance:
            logger.error(f"FreeSWITCH实例不存在: {instance_id}")
            return False

        # 检查连接状态
        if not instance.connected and not await instance.connect():
            logger.error(f"FreeSWITCH实例 {instance_id} 连接不可用，无法处理来电")
            return False

        if session_id in instance.sessions:
            logger.warning(f"会话 {session_id} 已存在")
            return False

        try:
            # 如果没有指定场景ID，根据入口点确定场景
            if not scenario_id:
                # 这里应该从呼叫信息中获取入口点
                # 暂时使用默认场景
                scenario_id = "default"

            # 创建对话管理器
            manager = ConversationManager(session_id, caller_id, scenario_id)

            # 设置回调
            manager.on_audio_output = lambda audio: self._send_audio(instance_id, session_id, audio)
            manager.on_state_change = lambda state: self._on_state_change(instance_id, session_id, state)
            manager.on_hangup = lambda: self._on_hangup(instance_id, session_id)

            # 启动对话管理器
            await manager.start()

            # 保存会话
            instance.sessions[session_id] = manager

            logger.info(f"来电处理成功: {session_id}")
            return True

        except Exception as e:
            logger.error(f"处理来电异常: {e}")
            return False

    async def handle_outbound_call(self, target_number: str, instance_id: str = "default", scenario_id: str = "default"):
        """处理呼出"""
        logger.info(f"处理呼出: {target_number}, 实例: {instance_id}, 场景: {scenario_id}")

        # 获取实例
        instance = self.instances.get(instance_id)
        if not instance:
            logger.error(f"FreeSWITCH实例不存在: {instance_id}")
            return False

        # 检查连接状态
        if not instance.connected and not await instance.connect():
            logger.error(f"FreeSWITCH实例 {instance_id} 连接不可用，无法处理呼出")
            return False

        try:
            session_id = f"outbound_{target_number}_{int(asyncio.get_event_loop().time())}"

            # 创建对话管理器
            manager = ConversationManager(session_id, target_number, scenario_id)

            # 设置回调
            manager.on_audio_output = lambda audio: self._send_audio(instance_id, session_id, audio)
            manager.on_state_change = lambda state: self._on_state_change(instance_id, session_id, state)
            manager.on_hangup = lambda: self._on_hangup(instance_id, session_id)

            # 启动对话管理器
            await manager.start()

            # 保存会话
            instance.sessions[session_id] = manager

            # 发起呼叫
            await self._initiate_outbound_call(instance, session_id, target_number, scenario_id)

            logger.info(f"呼出处理成功: {session_id}")
            return True

        except Exception as e:
            logger.error(f"处理呼出异常: {e}")
            return False

    async def _initiate_outbound_call(self, instance: FreeSwitchInstance, session_id: str, target_number: str, scenario_id: str):
        """发起呼出呼叫"""
        # 这里应该实现实际的ESL呼出逻辑
        # 暂时记录日志
        logger.info(f"发起呼出呼叫: {session_id} -> {target_number} (场景: {scenario_id})")

    def _send_audio(self, instance_id: str, session_id: str, audio_data: bytes):
        """发送音频数据"""
        # 这里应该实现实际的音频流发送
        logger.debug(f"发送音频: 实例={instance_id}, 会话={session_id}, 大小={len(audio_data)}")

    def _on_state_change(self, instance_id: str, session_id: str, state: str):
        """状态变化回调"""
        logger.info(f"会话状态变化: 实例={instance_id}, 会话={session_id}, 状态={state}")

    def _on_hangup(self, instance_id: str, session_id: str):
        """挂断回调"""
        logger.info(f"会话挂断: 实例={instance_id}, 会话={session_id}")

        # 获取实例和会话
        instance = self.instances.get(instance_id)
        if instance and session_id in instance.sessions:
            # 清理会话
            manager = instance.sessions[session_id]
            asyncio.create_task(manager.stop())
            del instance.sessions[session_id]

    def get_active_sessions(self, instance_id: str = None) -> Dict[str, int]:
        """获取活跃会话统计"""
        if instance_id:
            instance = self.instances.get(instance_id)
            return {instance_id: len(instance.sessions) if instance else 0}
        else:
            return {iid: len(instance.sessions) for iid, instance in self.instances.items()}

    def get_instance_status(self) -> Dict[str, Dict]:
        """获取所有实例状态"""
        status = {}
        for instance_id, instance in self.instances.items():
            status[instance_id] = {
                'connected': instance.connected,
                'host': instance.host,
                'port': instance.port,
                'active_sessions': len(instance.sessions),
                'scenario_mapping': instance.scenario_mapping
            }
        return status
        
    async def _send_audio(self, instance_id: str, session_id: str, audio_data: bytes):
        """发送音频到FreeSWITCH"""
        logger.debug(f"发送音频到会话 {session_id} (实例: {instance_id}), 长度: {len(audio_data)}")
        # 实际实现应该通过ESL发送音频数据
        
    async def _on_state_change(self, instance_id: str, session_id: str, state: str):
        """处理状态变化"""
        logger.debug(f"会话 {session_id} (实例: {instance_id}) 状态变化: {state}")
        
    async def _on_hangup(self, instance_id: str, session_id: str):
        """处理挂机"""
        logger.info(f"会话 {session_id} 挂机 (实例: {instance_id})")
        instance = self.instances.get(instance_id)
        if instance and session_id in instance.sessions:
            await instance.sessions[session_id].stop()
            del instance.sessions[session_id]
