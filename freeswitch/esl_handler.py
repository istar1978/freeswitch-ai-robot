import asyncio
import socket
import uuid
from typing import Dict, Optional, List, Callable
from datetime import datetime
import greenswitch
from config.settings import config
from utils.logger import setup_logger
from core.conversation_manager import ConversationManager
from freeswitch.audio_stream import AudioStreamHandler

logger = setup_logger(__name__)

class FreeSwitchInstance:
    """FreeSWITCH实例 - 支持真实ESL连接"""

    def __init__(self, instance_id: str, host: str, port: int, password: str, scenario_mapping: Dict[str, str]):
        self.instance_id = instance_id
        self.host = host
        self.port = port
        self.password = password
        self.scenario_mapping = scenario_mapping
        self.connected = False
        self.connection: Optional[greenswitch.InboundESL] = None
        self.sessions: Dict[str, Dict] = {}  # session_id -> {manager, stream, call_data}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.last_error = None
        self._event_handlers: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """连接到FreeSWITCH ESL实例"""
        async with self._lock:
            try:
                if self.connected and self.connection:
                    return True

                logger.info(f"正在连接FreeSWITCH实例 {self.instance_id} at {self.host}:{self.port}")
                
                # 创建ESL连接
                self.connection = greenswitch.InboundESL(host=self.host, port=self.port, password=self.password)
                
                # 连接并认证
                await asyncio.get_event_loop().run_in_executor(None, self.connection.connect)
                
                if not self.connection.connected:
                    raise ConnectionError("ESL连接失败")
                
                # 订阅所有事件
                await self._subscribe_events()
                
                self.connected = True
                self.reconnect_attempts = 0
                self.last_error = None
                logger.info(f"FreeSWITCH实例 {self.instance_id} 连接成功")
                
                # 启动事件监听
                asyncio.create_task(self._event_loop())
                
                return True

            except Exception as e:
                self.last_error = str(e)
                self.reconnect_attempts += 1
                logger.error(f"FreeSWITCH实例 {self.instance_id} 连接失败 (尝试 {self.reconnect_attempts}/{self.max_reconnect_attempts}): {e}")
                return False

    async def _subscribe_events(self):
        """订阅FreeSWITCH事件"""
        try:
            # 订阅所有通道事件
            events = [
                'CHANNEL_CREATE',
                'CHANNEL_ANSWER',
                'CHANNEL_HANGUP',
                'CHANNEL_HANGUP_COMPLETE',
                'DTMF',
                'CUSTOM'
            ]
            
            for event in events:
                await asyncio.get_event_loop().run_in_executor(
                    None, 
                    self.connection.send,
                    f'event plain {event}'
                )
            
            logger.info(f"已订阅事件: {', '.join(events)}")
            
        except Exception as e:
            logger.error(f"订阅事件失败: {e}")

    async def _event_loop(self):
        """事件循环 - 监听FreeSWITCH事件"""
        while self.connected:
            try:
                # 接收事件
                event = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.connection.recvEvent
                )
                
                if not event:
                    await asyncio.sleep(0.01)
                    continue
                
                # 处理事件
                await self._handle_event(event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"事件循环异常: {e}")
                await asyncio.sleep(1)

    async def _handle_event(self, event):
        """处理FreeSWITCH事件"""
        try:
            event_name = event.getHeader('Event-Name')
            unique_id = event.getHeader('Unique-ID')
            
            if not event_name:
                return
            
            logger.debug(f"收到事件: {event_name}, UUID: {unique_id}")
            
            # 分发到对应的处理器
            handler = self._event_handlers.get(event_name)
            if handler:
                await handler(event)
            
            # 内置事件处理
            if event_name == 'CHANNEL_CREATE':
                await self._on_channel_create(event)
            elif event_name == 'CHANNEL_ANSWER':
                await self._on_channel_answer(event)
            elif event_name == 'CHANNEL_HANGUP':
                await self._on_channel_hangup(event)
            elif event_name == 'DTMF':
                await self._on_dtmf(event)
                
        except Exception as e:
            logger.error(f"处理事件异常: {e}", exc_info=True)

    async def _on_channel_create(self, event):
        """通道创建事件"""
        unique_id = event.getHeader('Unique-ID')
        caller_number = event.getHeader('Caller-Caller-ID-Number')
        called_number = event.getHeader('Caller-Destination-Number')
        direction = event.getHeader('Call-Direction')
        
        logger.info(f"通道创建: {unique_id}, 主叫: {caller_number}, 被叫: {called_number}, 方向: {direction}")

    async def _on_channel_answer(self, event):
        """通道接听事件"""
        unique_id = event.getHeader('Unique-ID')
        logger.info(f"通道接听: {unique_id}")
        
        # 如果有对应的会话，开始音频流
        if unique_id in self.sessions:
            session_data = self.sessions[unique_id]
            if 'stream' in session_data:
                await session_data['stream'].start_streaming()

    async def _on_channel_hangup(self, event):
        """通道挂断事件"""
        unique_id = event.getHeader('Unique-ID')
        hangup_cause = event.getHeader('Hangup-Cause')
        
        logger.info(f"通道挂断: {unique_id}, 原因: {hangup_cause}")
        
        # 清理会话
        if unique_id in self.sessions:
            await self._cleanup_session(unique_id, hangup_cause)

    async def _on_dtmf(self, event):
        """DTMF事件"""
        unique_id = event.getHeader('Unique-ID')
        digit = event.getHeader('DTMF-Digit')
        
        logger.debug(f"收到DTMF: {unique_id}, 按键: {digit}")
        
        # 可以根据DTMF实现交互式菜单
        if unique_id in self.sessions:
            session_data = self.sessions[unique_id]
            manager = session_data.get('manager')
            if manager and hasattr(manager, 'on_dtmf'):
                await manager.on_dtmf(digit)

    async def _cleanup_session(self, session_id: str, reason: str = None):
        """清理会话资源"""
        try:
            if session_id not in self.sessions:
                return
            
            session_data = self.sessions[session_id]
            
            # 停止对话管理器
            manager = session_data.get('manager')
            if manager:
                try:
                    await asyncio.wait_for(manager.stop(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"会话 {session_id} 停止超时")
                except Exception as e:
                    logger.error(f"停止会话管理器异常: {e}")
            
            # 停止音频流
            stream = session_data.get('stream')
            if stream:
                try:
                    await stream.stop_streaming()
                except Exception as e:
                    logger.error(f"停止音频流异常: {e}")
            
            # 移除会话
            del self.sessions[session_id]
            
            logger.info(f"会话 {session_id} 已清理 (原因: {reason})")
            
        except Exception as e:
            logger.error(f"清理会话异常: {e}", exc_info=True)

    async def disconnect(self):
        """断开ESL连接"""
        async with self._lock:
            try:
                # 清理所有会话
                session_ids = list(self.sessions.keys())
                for session_id in session_ids:
                    await self._cleanup_session(session_id, "实例断开")
                
                # 关闭ESL连接
                if self.connection:
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            self.connection.disconnect
                        )
                    except Exception as e:
                        logger.error(f"关闭ESL连接异常: {e}")
                    
                    self.connection = None
                
                self.connected = False
                logger.info(f"FreeSWITCH实例 {self.instance_id} 连接已断开")
                
            except Exception as e:
                logger.error(f"断开连接异常: {e}", exc_info=True)

    def get_scenario_for_entry_point(self, entry_point: str) -> Optional[str]:
        """根据入口点获取场景ID"""
        return self.scenario_mapping.get(entry_point)

    async def send_api(self, command: str) -> Optional[str]:
        """发送API命令"""
        try:
            if not self.connected or not self.connection:
                logger.error("未ESL连接，无法发送命令")
                return None
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.connection.api,
                command
            )
            
            return response.getBody() if response else None
            
        except Exception as e:
            logger.error(f"发送API命令失败: {e}")
            return None

    async def originate_call(self, destination: str, gateway: str = None, 
                           caller_id: str = None, variables: Dict = None) -> Optional[str]:
        """发起外呼
        
        Args:
            destination: 目标号码
            gateway: SIP网关
            caller_id: 主叫号码
            variables: 自定义变量
            
        Returns:
            通道UUID或None
        """
        try:
            # 构建originate命令
            dial_string = f"sofia/gateway/{gateway}/{destination}" if gateway else f"sofia/internal/{destination}"
            
            # 添加变量
            var_string = ""
            if variables:
                var_list = [f"{k}={v}" for k, v in variables.items()]
                var_string = "{" + ",".join(var_list) + "}"
            
            if caller_id:
                var_string += f"{{origination_caller_id_number={caller_id}}}"
            
            # originate命令
            cmd = f"originate {var_string}{dial_string} &park()"
            
            logger.info(f"发起外呼: {cmd}")
            
            result = await self.send_api(cmd)
            
            if result and "+OK" in result:
                # 提取UUID
                uuid = result.split()[-1] if result else None
                logger.info(f"外呼成功, UUID: {uuid}")
                return uuid
            else:
                logger.error(f"外呼失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"发起外呼异常: {e}", exc_info=True)
            return None

    async def hangup_call(self, uuid: str, cause: str = "NORMAL_CLEARING"):
        """挂断通话"""
        try:
            cmd = f"uuid_kill {uuid} {cause}"
            await self.send_api(cmd)
            logger.info(f"挂断通话: {uuid}, 原因: {cause}")
        except Exception as e:
            logger.error(f"挂断通话异常: {e}")

    async def answer_call(self, uuid: str):
        """接听通话"""
        try:
            cmd = f"uuid_answer {uuid}"
            await self.send_api(cmd)
            logger.info(f"接听通话: {uuid}")
        except Exception as e:
            logger.error(f"接听通话异常: {e}")

    async def play_audio(self, uuid: str, audio_file: str):
        """播放音频"""
        try:
            cmd = f"uuid_broadcast {uuid} {audio_file} aleg"
            await self.send_api(cmd)
            logger.debug(f"播放音频: {uuid} -> {audio_file}")
        except Exception as e:
            logger.error(f"播放音频异常: {e}")

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

    async def handle_incoming_call(self, session_id: str, instance_id: str = "default", 
                                   scenario_id: str = None, caller_id: str = None,
                                   called_number: str = None, call_data: Dict = None) -> bool:
        """处理入呼 - 增强版本带完善异常处理
        
        Args:
            session_id: 通道UUID
            instance_id: FreeSWITCH实例ID
            scenario_id: 场景ID
            caller_id: 主叫号码
            called_number: 被叫号码
            call_data: 额外通话数据
        """
        logger.info(f"处理入呼: {session_id}, 实例: {instance_id}, 场景: {scenario_id}, 主叫: {caller_id}")

        try:
            # 获取实例
            instance = self.instances.get(instance_id)
            if not instance:
                logger.error(f"FreeSWITCH实例不存在: {instance_id}")
                return False

            # 检查连接状态
            if not instance.connected:
                logger.warning(f"实例 {instance_id} 未连接，尝试重连...")
                if not await instance.connect():
                    logger.error(f"FreeSWITCH实例 {instance_id} 连接不可用，无法处理入呼")
                    return False

            # 检查会话是否已存在
            if session_id in instance.sessions:
                logger.warning(f"会话 {session_id} 已存在，跳过")
                return False

            # 确定场景ID
            if not scenario_id:
                # 根据被叫号码查找场景
                scenario_id = instance.get_scenario_for_entry_point(called_number) or "default"
                logger.info(f"根据被叫号码 {called_number} 匹配场景: {scenario_id}")

            # 接听通话
            await instance.answer_call(session_id)
            await asyncio.sleep(0.5)  # 等待接听完成

            # 创建AudioStreamHandler
            audio_stream = AudioStreamHandler(instance, session_id)
            
            # 创建对话管理器
            manager = ConversationManager(
                session_id=session_id,
                caller_number=caller_id,
                scenario_id=scenario_id
            )

            # 设置回调函数
            async def on_audio_output(audio_data: bytes):
                """TTS输出音频回调"""
                try:
                    await audio_stream.send_audio(audio_data)
                except Exception as e:
                    logger.error(f"发送音频失败: {e}")

            async def on_state_change(state: str):
                """状态变化回调"""
                logger.info(f"会话 {session_id} 状态变为: {state}")

            async def on_hangup():
                """挂断回调"""
                logger.info(f"会话 {session_id} 请求挂断")
                try:
                    await instance.hangup_call(session_id)
                    await instance._cleanup_session(session_id, "正常结束")
                except Exception as e:
                    logger.error(f"挂断失败: {e}")

            manager.on_audio_output = on_audio_output
            manager.on_state_change = on_state_change
            manager.on_hangup = on_hangup

            # 保存会话数据
            instance.sessions[session_id] = {
                'manager': manager,
                'stream': audio_stream,
                'call_data': call_data or {},
                'start_time': datetime.now(),
                'direction': 'inbound',
                'caller_number': caller_id,
                'called_number': called_number,
                'scenario_id': scenario_id
            }

            # 启动对话管理器
            try:
                await manager.start()
            except Exception as e:
                logger.error(f"启动对话管理器失败: {e}")
                await instance._cleanup_session(session_id, "启动失败")
                return False

            # 启动音频流
            try:
                await audio_stream.start_streaming()
            except Exception as e:
                logger.error(f"启动音频流失败: {e}")
                await instance._cleanup_session(session_id, "音频流失败")
                return False

            logger.info(f"入呼处理成功: {session_id}")
            return True

        except asyncio.CancelledError:
            logger.warning(f"入呼处理被取消: {session_id}")
            raise
        except Exception as e:
            logger.error(f"处理入呼异常: {e}", exc_info=True)
            # 尝试清理资源
            try:
                instance = self.instances.get(instance_id)
                if instance and session_id in instance.sessions:
                    await instance._cleanup_session(session_id, f"异常: {str(e)}")
            except Exception as cleanup_error:
                logger.error(f"清理异常: {cleanup_error}")
            return False

    async def handle_outbound_call(self, target_number: str, instance_id: str = "default", 
                                   scenario_id: str = "default", gateway: str = None,
                                   caller_id: str = None, variables: Dict = None) -> Optional[str]:
        """处理外呼 - 增强版本带完善异常处理
        
        Args:
            target_number: 目标号码
            instance_id: FreeSWITCH实例ID
            scenario_id: 场景ID
            gateway: SIP网关
            caller_id: 主叫号码
            variables: 自定义变量
            
        Returns:
            会话session_id或None
        """
        logger.info(f"处理外呼: {target_number}, 实例: {instance_id}, 场景: {scenario_id}, 网关: {gateway}")

        try:
            # 获取实例
            instance = self.instances.get(instance_id)
            if not instance:
                logger.error(f"FreeSWITCH实例不存在: {instance_id}")
                return None

            # 检查连接状态
            if not instance.connected:
                logger.warning(f"实例 {instance_id} 未连接，尝试重连...")
                if not await instance.connect():
                    logger.error(f"FreeSWITCH实例 {instance_id} 连接不可用，无法处理外呼")
                    return None

            # 准备变量
            call_variables = variables or {}
            call_variables['ai_scenario_id'] = scenario_id
            call_variables['ai_direction'] = 'outbound'
            call_variables['ai_target_number'] = target_number

            # 发起外呼
            logger.info(f"发起外呼到 {target_number}...")
            uuid = await instance.originate_call(
                destination=target_number,
                gateway=gateway,
                caller_id=caller_id,
                variables=call_variables
            )

            if not uuid:
                logger.error(f"外呼失败: {target_number}")
                return None

            logger.info(f"外呼成功, UUID: {uuid}")

            # 等待接听
            await asyncio.sleep(2.0)

            # 创建AudioStreamHandler
            audio_stream = AudioStreamHandler(instance, uuid)
            
            # 创建对话管理器
            manager = ConversationManager(
                session_id=uuid,
                caller_number=target_number,
                scenario_id=scenario_id
            )

            # 设置回调函数
            async def on_audio_output(audio_data: bytes):
                """TTS输出音频回调"""
                try:
                    await audio_stream.send_audio(audio_data)
                except Exception as e:
                    logger.error(f"发送音频失败: {e}")

            async def on_state_change(state: str):
                """状态变化回调"""
                logger.info(f"外呼会话 {uuid} 状态变为: {state}")

            async def on_hangup():
                """挂断回调"""
                logger.info(f"外呼会话 {uuid} 请求挂断")
                try:
                    await instance.hangup_call(uuid)
                    await instance._cleanup_session(uuid, "外呼正常结束")
                except Exception as e:
                    logger.error(f"挂断失败: {e}")

            manager.on_audio_output = on_audio_output
            manager.on_state_change = on_state_change
            manager.on_hangup = on_hangup

            # 保存会话数据
            instance.sessions[uuid] = {
                'manager': manager,
                'stream': audio_stream,
                'call_data': {'target_number': target_number, 'gateway': gateway},
                'start_time': datetime.now(),
                'direction': 'outbound',
                'caller_number': caller_id,
                'called_number': target_number,
                'scenario_id': scenario_id
            }

            # 启动对话管理器
            try:
                await manager.start()
            except Exception as e:
                logger.error(f"启动对话管理器失败: {e}")
                await instance.hangup_call(uuid)
                await instance._cleanup_session(uuid, "启动失败")
                return None

            # 启动音频流
            try:
                await audio_stream.start_streaming()
            except Exception as e:
                logger.error(f"启动音频流失败: {e}")
                await instance.hangup_call(uuid)
                await instance._cleanup_session(uuid, "音频流失败")
                return None

            logger.info(f"外呼处理成功: {uuid}")
            return uuid

        except asyncio.CancelledError:
            logger.warning(f"外呼处理被取消: {target_number}")
            raise
        except Exception as e:
            logger.error(f"处理外呼异常: {e}", exc_info=True)
            # 尝试清理资源
            try:
                instance = self.instances.get(instance_id)
                if instance and uuid and uuid in instance.sessions:
                    await instance.hangup_call(uuid)
                    await instance._cleanup_session(uuid, f"异常: {str(e)}")
            except Exception as cleanup_error:
                logger.error(f"清理异常: {cleanup_error}")
            return None

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
                'scenario_mapping': instance.scenario_mapping,
                'reconnect_attempts': instance.reconnect_attempts,
                'last_error': instance.last_error
            }
        return status

    def get_session_info(self, session_id: str, instance_id: str = None) -> Optional[Dict]:
        """获取会话信息"""
        if instance_id:
            instances_to_check = [self.instances.get(instance_id)]
        else:
            instances_to_check = self.instances.values()
        
        for instance in instances_to_check:
            if instance and session_id in instance.sessions:
                session_data = instance.sessions[session_id]
                return {
                    'session_id': session_id,
                    'instance_id': instance.instance_id,
                    'direction': session_data.get('direction'),
                    'caller_number': session_data.get('caller_number'),
                    'called_number': session_data.get('called_number'),
                    'scenario_id': session_data.get('scenario_id'),
                    'start_time': session_data.get('start_time').isoformat() if session_data.get('start_time') else None,
                    'duration': (datetime.now() - session_data.get('start_time')).total_seconds() if session_data.get('start_time') else 0
                }
        return None
