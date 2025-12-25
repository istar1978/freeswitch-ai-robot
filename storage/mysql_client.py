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

    # 场景管理方法
    async def create_scenario(self, scenario_data: dict):
        """创建场景"""
        session = await self.get_session()
        async with session:
            scenario = Scenario(**scenario_data)
            session.add(scenario)
            await session.commit()
            await session.refresh(scenario)
            return scenario

    async def get_scenarios(self):
        """获取所有场景"""
        session = await self.get_session()
        async with session:
            result = await session.execute(select(Scenario))
            return result.scalars().all()

    async def get_scenario(self, scenario_id: str):
        """根据ID获取场景"""
        session = await self.get_session()
        async with session:
            result = await session.execute(
                select(Scenario).where(Scenario.scenario_id == scenario_id)
            )
            return result.scalar_one_or_none()

    async def update_scenario(self, scenario_id: str, update_data: dict):
        """更新场景"""
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
            return scenario

    async def delete_scenario(self, scenario_id: str):
        """删除场景"""
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

# 全局MySQL客户端实例
mysql_client = MySQLClient()