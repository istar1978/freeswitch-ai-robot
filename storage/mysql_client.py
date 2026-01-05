# storage/mysql_client.py
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, select
from datetime import datetime
from config.settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemConfig(Base):
    __tablename__ = 'system_configs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CallRecord(Base):
    __tablename__ = 'call_records'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)
    caller_number = Column(String(50))
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    duration = Column(Integer)  # seconds
    conversation_log = Column(Text)  # JSON string of conversation history
    status = Column(String(20), default='active')  # active, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)

class Scenario(Base):
    __tablename__ = 'scenarios'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    entry_points = Column(JSON)  # List of entry point strings
    system_prompt = Column(Text, nullable=False)
    welcome_message = Column(Text, nullable=False)
    fallback_responses = Column(JSON)  # List of fallback response strings
    max_turns = Column(Integer, default=10)
    timeout_seconds = Column(Integer, default=300)
    custom_settings = Column(JSON)  # Dict of custom settings
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FreeSwitchConfig(Base):
    __tablename__ = 'freeswitch_configs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    host = Column(String(100), nullable=False)
    port = Column(Integer, default=8021)
    password = Column(String(100), nullable=False)
    scenario_mapping = Column(JSON)  # Dict mapping entry points to scenario IDs
    gateway_ids = Column(JSON)  # List of gateway IDs associated with this instance
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Gateway(Base):
    __tablename__ = 'gateways'
    id = Column(Integer, primary_key=True, autoincrement=True)
    gateway_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    gateway_type = Column(String(20), nullable=False)  # 'sip', 'pstn', etc.
    profile = Column(String(50), default='external')  # Sofia profile name
    username = Column(String(100))
    password = Column(String(100))
    realm = Column(String(100))
    proxy = Column(String(100))
    register = Column(Boolean, default=False)
    retry_seconds = Column(Integer, default=30)
    caller_id_in_from = Column(Boolean, default=False)
    contact_params = Column(String(255))
    max_channels = Column(Integer, default=100)
    codecs = Column(JSON, default=['PCMU', 'PCMA', 'G729'])  # List of supported codecs
    freeswitch_instances = Column(JSON)  # List of FreeSWITCH instance IDs
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EntryPoint(Base):
    __tablename__ = 'entry_points'
    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_point_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    dialplan_pattern = Column(String(255), nullable=False)  # Dialplan pattern like "^1000$"
    scenario_id = Column(String(100), nullable=False)
    gateway_id = Column(String(100))  # Associated gateway for outbound calls
    freeswitch_instances = Column(JSON)  # List of FreeSWITCH instance IDs
    priority = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OutboundCampaign(Base):
    __tablename__ = 'outbound_campaigns'
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    gateway_id = Column(String(100), nullable=False)
    scenario_id = Column(String(100), nullable=False)
    data_fields = Column(JSON)  # List of field definitions for data import
    status = Column(String(20), default='draft')  # draft, active, paused, completed
    total_contacts = Column(Integer, default=0)
    completed_contacts = Column(Integer, default=0)
    successful_calls = Column(Integer, default=0)
    failed_calls = Column(Integer, default=0)
    max_concurrent_calls = Column(Integer, default=10)
    call_timeout = Column(Integer, default=30)  # seconds
    retry_attempts = Column(Integer, default=3)
    retry_interval = Column(Integer, default=300)  # seconds
    schedule_start = Column(DateTime)
    schedule_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OutboundContact(Base):
    __tablename__ = 'outbound_contacts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String(100), nullable=False)
    contact_data = Column(JSON)  # Contact information and custom fields
    phone_number = Column(String(50), nullable=False)
    status = Column(String(20), default='pending')  # pending, calling, completed, failed
    attempts = Column(Integer, default=0)
    last_attempt = Column(DateTime)
    next_attempt = Column(DateTime)
    call_result = Column(String(50))  # answered, no_answer, busy, failed, etc.
    call_duration = Column(Integer)  # seconds
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MySQLClient:
    def __init__(self):
        self.engine = None
        self.session_maker = None

    async def connect(self):
        """连接到MySQL数据库"""
        try:
            database_url = f"mysql+aiomysql://{config.mysql.user}:{config.mysql.password}@{config.mysql.host}:{config.mysql.port}/{config.mysql.database}"
            self.engine = create_async_engine(database_url, echo=False)
            self.session_maker = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

            # 创建表
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("MySQL数据库连接成功")
        except Exception as e:
            logger.error(f"MySQL数据库连接失败: {e}")
            raise

    async def disconnect(self):
        """断开数据库连接"""
        if self.engine:
            await self.engine.dispose()
            logger.info("MySQL数据库连接已断开")

    async def get_session(self):
        """获取数据库会话"""
        return self.session_maker()

    # ========== 配置加载到Redis ==========
    
    async def load_all_configs_to_redis(self):
        """启动时将所有配置加载到Redis"""
        try:
            from storage.redis_client import redis_client
            
            logger.info("开始加载配置到Redis...")
            
            # 清除旧缓存
            await redis_client.clear_all_configs()
            
            # 加载场景配置
            scenarios = await self.get_scenarios()
            for scenario in scenarios:
                config_data = self._scenario_to_dict(scenario)
                await redis_client.set_config('scenario', scenario.scenario_id, config_data)
            logger.info(f"已加载 {len(scenarios)} 个场景配置")
            
            # 加载FreeSWITCH配置
            fs_configs = await self.get_freeswitch_configs()
            for fs_config in fs_configs:
                config_data = self._freeswitch_config_to_dict(fs_config)
                await redis_client.set_config('freeswitch', fs_config.instance_id, config_data)
            logger.info(f"已加载 {len(fs_configs)} 个FreeSWITCH配置")
            
            # 加载网关配置
            gateways = await self.get_gateways()
            for gateway in gateways:
                config_data = self._gateway_to_dict(gateway)
                await redis_client.set_config('gateway', gateway.gateway_id, config_data)
            logger.info(f"已加载 {len(gateways)} 个网关配置")
            
            # 加载入口点配置
            entry_points = await self.get_entry_points()
            for entry_point in entry_points:
                config_data = self._entry_point_to_dict(entry_point)
                await redis_client.set_config('entry_point', entry_point.entry_point_id, config_data)
            logger.info(f"已加载 {len(entry_points)} 个入口点配置")
            
            # 加载外呼活动配置
            campaigns = await self.get_outbound_campaigns()
            for campaign in campaigns:
                config_data = self._campaign_to_dict(campaign)
                await redis_client.set_config('campaign', campaign.campaign_id, config_data)
            logger.info(f"已加载 {len(campaigns)} 个外呼活动配置")
            
            logger.info("所有配置已加载到Redis")
            return True
            
        except Exception as e:
            logger.error(f"加载配置到Redis失败: {e}")
            return False
    
    def _scenario_to_dict(self, scenario) -> dict:
        """将Scenario对象转换为dict"""
        return {
            'id': scenario.id,
            'scenario_id': scenario.scenario_id,
            'name': scenario.name,
            'description': scenario.description,
            'entry_points': scenario.entry_points,
            'system_prompt': scenario.system_prompt,
            'welcome_message': scenario.welcome_message,
            'fallback_responses': scenario.fallback_responses,
            'max_turns': scenario.max_turns,
            'timeout_seconds': scenario.timeout_seconds,
            'custom_settings': scenario.custom_settings,
            'is_active': scenario.is_active,
            'created_at': scenario.created_at.isoformat() if scenario.created_at else None,
            'updated_at': scenario.updated_at.isoformat() if scenario.updated_at else None
        }
    
    def _freeswitch_config_to_dict(self, config) -> dict:
        """将FreeSwitchConfig对象转换为dict"""
        return {
            'id': config.id,
            'instance_id': config.instance_id,
            'name': config.name,
            'host': config.host,
            'port': config.port,
            'password': config.password,
            'scenario_mapping': config.scenario_mapping,
            'gateway_ids': config.gateway_ids,
            'is_active': config.is_active,
            'created_at': config.created_at.isoformat() if config.created_at else None,
            'updated_at': config.updated_at.isoformat() if config.updated_at else None
        }
    
    def _gateway_to_dict(self, gateway) -> dict:
        """将Gateway对象转换为dict"""
        return {
            'id': gateway.id,
            'gateway_id': gateway.gateway_id,
            'name': gateway.name,
            'description': gateway.description,
            'gateway_type': gateway.gateway_type,
            'profile': gateway.profile,
            'username': gateway.username,
            'password': gateway.password,
            'realm': gateway.realm,
            'proxy': gateway.proxy,
            'register': gateway.register,
            'retry_seconds': gateway.retry_seconds,
            'caller_id_in_from': gateway.caller_id_in_from,
            'contact_params': gateway.contact_params,
            'max_channels': gateway.max_channels,
            'codecs': gateway.codecs,
            'freeswitch_instances': gateway.freeswitch_instances,
            'is_active': gateway.is_active,
            'created_at': gateway.created_at.isoformat() if gateway.created_at else None,
            'updated_at': gateway.updated_at.isoformat() if gateway.updated_at else None
        }
    
    def _entry_point_to_dict(self, entry_point) -> dict:
        """将EntryPoint对象转换为dict"""
        return {
            'id': entry_point.id,
            'entry_point_id': entry_point.entry_point_id,
            'name': entry_point.name,
            'description': entry_point.description,
            'dialplan_pattern': entry_point.dialplan_pattern,
            'scenario_id': entry_point.scenario_id,
            'gateway_id': entry_point.gateway_id,
            'freeswitch_instances': entry_point.freeswitch_instances,
            'priority': entry_point.priority,
            'is_active': entry_point.is_active,
            'created_at': entry_point.created_at.isoformat() if entry_point.created_at else None,
            'updated_at': entry_point.updated_at.isoformat() if entry_point.updated_at else None
        }
    
    def _campaign_to_dict(self, campaign) -> dict:
        """将OutboundCampaign对象转换为dict"""
        return {
            'id': campaign.id,
            'campaign_id': campaign.campaign_id,
            'name': campaign.name,
            'description': campaign.description,
            'gateway_id': campaign.gateway_id,
            'scenario_id': campaign.scenario_id,
            'data_fields': campaign.data_fields,
            'status': campaign.status,
            'total_contacts': campaign.total_contacts,
            'completed_contacts': campaign.completed_contacts,
            'successful_calls': campaign.successful_calls,
            'failed_calls': campaign.failed_calls,
            'max_concurrent_calls': campaign.max_concurrent_calls,
            'call_timeout': campaign.call_timeout,
            'retry_attempts': campaign.retry_attempts,
            'retry_interval': campaign.retry_interval,
            'schedule_start': campaign.schedule_start.isoformat() if campaign.schedule_start else None,
            'schedule_end': campaign.schedule_end.isoformat() if campaign.schedule_end else None,
            'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
            'updated_at': campaign.updated_at.isoformat() if campaign.updated_at else None
        }

    # 场景管理方法
    async def create_scenario(self, scenario_data: dict):
        """创建场景"""
        session = await self.get_session()
        async with session:
            scenario = Scenario(**scenario_data)
            session.add(scenario)
            await session.commit()
            await session.refresh(scenario)
            
            # 同步到Redis
            from storage.redis_client import redis_client
            config_data = self._scenario_to_dict(scenario)
            await redis_client.set_config('scenario', scenario.scenario_id, config_data)
            
            return scenario

    async def get_scenarios(self):
        """获取所有场景"""
        # 先尝试从Redis获取
        from storage.redis_client import redis_client
        configs = await redis_client.get_all_configs('scenario')
        
        if configs:
            return configs
        
        # Redis没有则从MySQL获取
        session = await self.get_session()
        async with session:
            result = await session.execute(select(Scenario))
            return result.scalars().all()

    async def get_scenario(self, scenario_id: str):
        """根据ID获取场景"""
        # 先尝试从Redis获取
        from storage.redis_client import redis_client
        config = await redis_client.get_config('scenario', scenario_id)
        
        if config:
            return config
        
        # Redis没有则从MySQL获取
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(Scenario).where(Scenario.scenario_id == scenario_id)
            )
            scenario = result.scalar_one_or_none()
            
            # 同步到Redis
            if scenario:
                config_data = self._scenario_to_dict(scenario)
                await redis_client.set_config('scenario', scenario_id, config_data)
                return config_data
            return None

    async def update_scenario(self, scenario_id: str, update_data: dict):
        """更新场景"""
        from storage.redis_client import redis_client
        
        # 先更新Redis
        existing_config = await redis_client.get_config('scenario', scenario_id)
        if existing_config:
            existing_config.update(update_data)
            await redis_client.set_config('scenario', scenario_id, existing_config)
            # 加入异步同步队列
            await redis_client.queue_config_sync('scenario', scenario_id, existing_config)
        
        # 更新MySQL
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(Scenario).where(Scenario.scenario_id == scenario_id)
            )
            scenario = result.scalar_one_or_none()
            if scenario:
                for key, value in update_data.items():
                    if hasattr(scenario, key):
                        setattr(scenario, key, value)
                await session.commit()
                await session.refresh(scenario)
                return self._scenario_to_dict(scenario)
            return None

    async def delete_scenario(self, scenario_id: str):
        """删除场景"""
        from storage.redis_client import redis_client
        
        # 从Redis删除
        await redis_client.delete_config('scenario', scenario_id)
        
        # 从MySQL删除
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(Scenario).where(Scenario.scenario_id == scenario_id)
            )
            scenario = result.scalar_one_or_none()
            if scenario:
                await session.delete(scenario)
                await session.commit()
                return True
            return False

    # FreeSWITCH配置管理方法
    async def create_freeswitch_config(self, config_data: dict):
        """创建FreeSWITCH配置"""
        session = await self.get_session()
        async with session:
            config = FreeSwitchConfig(**config_data)
            session.add(config)
            await session.commit()
            await session.refresh(config)
            return config

    async def get_freeswitch_configs(self):
        """获取所有FreeSWITCH配置"""
        session = await self.get_session()
        async with session:
            result = await session.execute(select(FreeSwitchConfig))
            return result.scalars().all()

    async def get_freeswitch_config(self, instance_id: str):
        """根据实例ID获取FreeSWITCH配置"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(FreeSwitchConfig).where(FreeSwitchConfig.instance_id == instance_id)
            )
            return result.scalar_one_or_none()

    async def update_freeswitch_config(self, instance_id: str, update_data: dict):
        """更新FreeSWITCH配置"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(FreeSwitchConfig).where(FreeSwitchConfig.instance_id == instance_id)
            )
            config = result.scalar_one_or_none()
            if config:
                for key, value in update_data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                await session.commit()
                await session.refresh(config)
            return config

    async def delete_freeswitch_config(self, instance_id: str):
        """删除FreeSWITCH配置"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(FreeSwitchConfig).where(FreeSwitchConfig.instance_id == instance_id)
            )
            config = result.scalar_one_or_none()
            if config:
                await session.delete(config)
                await session.commit()
                return True
            return False

    # 网关管理方法
    async def create_gateway(self, gateway_data: dict):
        """创建网关"""
        session = await self.get_session()
        async with session:
            gateway = Gateway(**gateway_data)
            session.add(gateway)
            await session.commit()
            await session.refresh(gateway)
            return gateway

    async def get_gateways(self):
        """获取所有网关"""
        session = await self.get_session()
        async with session:
            result = await session.execute(select(Gateway))
            return result.scalars().all()

    async def get_gateway(self, gateway_id: str):
        """根据ID获取网关"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(Gateway).where(Gateway.gateway_id == gateway_id)
            )
            return result.scalar_one_or_none()

    async def update_gateway(self, gateway_id: str, update_data: dict):
        """更新网关"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(Gateway).where(Gateway.gateway_id == gateway_id)
            )
            gateway = result.scalar_one_or_none()
            if gateway:
                for key, value in update_data.items():
                    if hasattr(gateway, key):
                        setattr(gateway, key, value)
                await session.commit()
                await session.refresh(gateway)
            return gateway

    async def delete_gateway(self, gateway_id: str):
        """删除网关"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(Gateway).where(Gateway.gateway_id == gateway_id)
            )
            gateway = result.scalar_one_or_none()
            if gateway:
                await session.delete(gateway)
                await session.commit()
                return True
            return False

    # 入口点管理方法
    async def create_entry_point(self, entry_point_data: dict):
        """创建入口点"""
        session = await self.get_session()
        async with session:
            entry_point = EntryPoint(**entry_point_data)
            session.add(entry_point)
            await session.commit()
            await session.refresh(entry_point)
            return entry_point

    async def get_entry_points(self):
        """获取所有入口点"""
        session = await self.get_session()
        async with session:
            result = await session.execute(select(EntryPoint))
            return result.scalars().all()

    async def get_entry_point(self, entry_point_id: str):
        """根据ID获取入口点"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(EntryPoint).where(EntryPoint.entry_point_id == entry_point_id)
            )
            return result.scalar_one_or_none()

    async def update_entry_point(self, entry_point_id: str, update_data: dict):
        """更新入口点"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(EntryPoint).where(EntryPoint.entry_point_id == entry_point_id)
            )
            entry_point = result.scalar_one_or_none()
            if entry_point:
                for key, value in update_data.items():
                    if hasattr(entry_point, key):
                        setattr(entry_point, key, value)
                await session.commit()
                await session.refresh(entry_point)
            return entry_point

    async def delete_entry_point(self, entry_point_id: str):
        """删除入口点"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(EntryPoint).where(EntryPoint.entry_point_id == entry_point_id)
            )
            entry_point = result.scalar_one_or_none()
            if entry_point:
                await session.delete(entry_point)
                await session.commit()
                return True
            return False

    # 外呼活动管理方法
    async def create_outbound_campaign(self, campaign_data: dict):
        """创建外呼活动"""
        session = await self.get_session()
        async with session:
            campaign = OutboundCampaign(**campaign_data)
            session.add(campaign)
            await session.commit()
            await session.refresh(campaign)
            return campaign

    async def get_outbound_campaigns(self):
        """获取所有外呼活动"""
        session = await self.get_session()
        async with session:
            result = await session.execute(select(OutboundCampaign))
            return result.scalars().all()

    async def get_outbound_campaign(self, campaign_id: str):
        """根据ID获取外呼活动"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(OutboundCampaign).where(OutboundCampaign.campaign_id == campaign_id)
            )
            return result.scalar_one_or_none()

    async def update_outbound_campaign(self, campaign_id: str, update_data: dict):
        """更新外呼活动"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(OutboundCampaign).where(OutboundCampaign.campaign_id == campaign_id)
            )
            campaign = result.scalar_one_or_none()
            if campaign:
                for key, value in update_data.items():
                    if hasattr(campaign, key):
                        setattr(campaign, key, value)
                await session.commit()
                await session.refresh(campaign)
            return campaign

    async def delete_outbound_campaign(self, campaign_id: str):
        """删除外呼活动"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(OutboundCampaign).where(OutboundCampaign.campaign_id == campaign_id)
            )
            campaign = result.scalar_one_or_none()
            if campaign:
                await session.delete(campaign)
                await session.commit()
                return True
            return False

    # 外呼联系人管理方法
    async def create_outbound_contact(self, contact_data: dict):
        """创建外呼联系人"""
        session = await self.get_session()
        async with session:
            contact = OutboundContact(**contact_data)
            session.add(contact)
            await session.commit()
            await session.refresh(contact)
            return contact

    async def get_outbound_contacts(self, campaign_id: str = None):
        """获取外呼联系人"""
        session = await self.get_session()
        async with session:
            if campaign_id:
                result = await session.execute(
                    select(OutboundContact).where(OutboundContact.campaign_id == campaign_id)
                )
            else:
                result = await session.execute(select(OutboundContact))
            return result.scalars().all()

    async def update_outbound_contact(self, contact_id: int, update_data: dict):
        """更新外呼联系人"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(OutboundContact).where(OutboundContact.id == contact_id)
            )
            contact = result.scalar_one_or_none()
            if contact:
                for key, value in update_data.items():
                    if hasattr(contact, key):
                        setattr(contact, key, value)
                await session.commit()
                await session.refresh(contact)
            return contact

    async def delete_outbound_contacts(self, campaign_id: str):
        """删除活动的所有联系人"""
        session = await self.get_session()
        async with session:
            await session.execute(
                select(OutboundContact).where(OutboundContact.campaign_id == campaign_id).delete()
            )
            await session.commit()
            return True

    # ========== 通话记录缓存和同步 ==========
    
    async def create_call_record_from_redis(self, call_data: dict):
        """从Redis数据创建通话记录到MySQL"""
        try:
            session = await self.get_session()
            async with session:
                call_record = CallRecord(
                    session_id=call_data.get('session_id'),
                    caller_number=call_data.get('caller_number'),
                    start_time=call_data.get('start_time'),
                    conversation_log=call_data.get('conversation_log', '')
                )
                session.add(call_record)
                await session.commit()
                await session.refresh(call_record)
                logger.debug(f"通话记录已同步到MySQL: {call_record.id}")
                return call_record.id
        except Exception as e:
            logger.error(f"创建通话记录失败: {e}")
            return None
    
    async def update_call_record_from_redis(self, session_id: str, call_data: dict):
        """从Redis数据更新通话记录到MySQL"""
        try:
            session = await self.get_session()
            async with session:
                result = await session.execute(
                    select(CallRecord).where(CallRecord.session_id == session_id)
                )
                call_record = result.scalar_one_or_none()
                
                if call_record:
                    # 更新现有记录
                    if 'end_time' in call_data:
                        call_record.end_time = call_data['end_time']
                    if 'duration' in call_data:
                        call_record.duration = call_data['duration']
                    if 'conversation_log' in call_data:
                        call_record.conversation_log = call_data['conversation_log']
                    if 'status' in call_data:
                        call_record.status = call_data['status']
                    await session.commit()
                    logger.debug(f"通话记录已更新: {call_record.id}")
                else:
                    # 创建新记录
                    await self.create_call_record_from_redis(call_data)
                    
        except Exception as e:
            logger.error(f"更新通话记录失败: {e}")
    
    async def update_config_from_redis(self, config_type: str, config_id: str, config_data: dict):
        """从Redis更新配置到MySQL"""
        try:
            if config_type == 'scenario':
                await self._update_scenario_to_mysql(config_id, config_data)
            elif config_type == 'freeswitch':
                await self._update_freeswitch_config_to_mysql(config_id, config_data)
            elif config_type == 'gateway':
                await self._update_gateway_to_mysql(config_id, config_data)
            elif config_type == 'entry_point':
                await self._update_entry_point_to_mysql(config_id, config_data)
            elif config_type == 'campaign':
                await self._update_campaign_to_mysql(config_id, config_data)
        except Exception as e:
            logger.error(f"更新配置到MySQL失败: {e}")
    
    async def _update_scenario_to_mysql(self, scenario_id: str, config_data: dict):
        """更新场景到MySQL"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(Scenario).where(Scenario.scenario_id == scenario_id)
            )
            scenario = result.scalar_one_or_none()
            if scenario:
                for key, value in config_data.items():
                    if hasattr(scenario, key) and key not in ['id', 'created_at']:
                        setattr(scenario, key, value)
                await session.commit()
    
    async def _update_freeswitch_config_to_mysql(self, instance_id: str, config_data: dict):
        """更新FreeSWITCH配置到MySQL"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(FreeSwitchConfig).where(FreeSwitchConfig.instance_id == instance_id)
            )
            config = result.scalar_one_or_none()
            if config:
                for key, value in config_data.items():
                    if hasattr(config, key) and key not in ['id', 'created_at']:
                        setattr(config, key, value)
                await session.commit()
    
    async def _update_gateway_to_mysql(self, gateway_id: str, config_data: dict):
        """更新网关到MySQL"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(Gateway).where(Gateway.gateway_id == gateway_id)
            )
            gateway = result.scalar_one_or_none()
            if gateway:
                for key, value in config_data.items():
                    if hasattr(gateway, key) and key not in ['id', 'created_at']:
                        setattr(gateway, key, value)
                await session.commit()
    
    async def _update_entry_point_to_mysql(self, entry_point_id: str, config_data: dict):
        """更新入口点到MySQL"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(EntryPoint).where(EntryPoint.entry_point_id == entry_point_id)
            )
            entry_point = result.scalar_one_or_none()
            if entry_point:
                for key, value in config_data.items():
                    if hasattr(entry_point, key) and key not in ['id', 'created_at']:
                        setattr(entry_point, key, value)
                await session.commit()
    
    async def _update_campaign_to_mysql(self, campaign_id: str, config_data: dict):
        """更新外呼活动到MySQL"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(OutboundCampaign).where(OutboundCampaign.campaign_id == campaign_id)
            )
            campaign = result.scalar_one_or_none()
            if campaign:
                for key, value in config_data.items():
                    if hasattr(campaign, key) and key not in ['id', 'created_at']:
                        setattr(campaign, key, value)
                await session.commit()

# 全局MySQL客户端实例
mysql_client = MySQLClient()