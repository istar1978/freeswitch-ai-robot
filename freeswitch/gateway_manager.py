# freeswitch/gateway_manager.py
from typing import Dict, List, Optional
from pathlib import Path
from utils.logger import setup_logger
from freeswitch.config_manager import fs_config_manager

logger = setup_logger(__name__)


class GatewayXMLGenerator:
    """SIP Gateway XML配置生成器"""
    
    @staticmethod
    def generate_gateway_xml(gateway_data: Dict) -> str:
        """生成网关XML配置"""
        gateway_id = gateway_data.get('gateway_id', 'gateway')
        name = gateway_data.get('name', gateway_id)
        username = gateway_data.get('username', '')
        password = gateway_data.get('password', '')
        realm = gateway_data.get('realm', '')
        proxy = gateway_data.get('proxy', '')
        register = gateway_data.get('register', False)
        retry_seconds = gateway_data.get('retry_seconds', 30)
        caller_id_in_from = gateway_data.get('caller_id_in_from', False)
        contact_params = gateway_data.get('contact_params', '')
        codecs = gateway_data.get('codecs', ['PCMU', 'PCMA', 'G729'])
        
        # 生成codec列表
        codec_list = ','.join(codecs) if isinstance(codecs, list) else codecs
        
        xml_content = f'''<include>
  <!-- {name} - Gateway配置 -->
  <gateway name="{gateway_id}">
    <param name="username" value="{username}"/>
    <param name="password" value="{password}"/>
    <param name="realm" value="{realm}"/>
    <param name="proxy" value="{proxy}"/>
    <param name="register" value="{'true' if register else 'false'}"/>
    <param name="retry-seconds" value="{retry_seconds}"/>
    <param name="caller-id-in-from" value="{'true' if caller_id_in_from else 'false'}"/>
'''
        
        # 可选参数
        if contact_params:
            xml_content += f'    <param name="contact-params" value="{contact_params}"/>\n'
        
        # 编解码器设置
        xml_content += f'    <param name="codec-prefs" value="{codec_list}"/>\n'
        
        # 其他常用参数
        xml_content += '''    <param name="register-transport" value="udp"/>
    <param name="expire-seconds" value="600"/>
    <param name="ping" value="30"/>
    <param name="extension-in-contact" value="true"/>
  </gateway>
</include>
'''
        return xml_content
    
    @staticmethod
    def generate_profile_gateway_include(gateway_id: str) -> str:
        """生成在profile中包含gateway的配置"""
        return f'<X-PRE-PROCESS cmd="include" data="external/{gateway_id}.xml"/>\n'


class GatewayManager:
    """SIP Gateway管理器"""
    
    def __init__(self):
        self.xml_generator = GatewayXMLGenerator()
    
    async def create_gateway_config(self, gateway_data: Dict) -> bool:
        """创建网关配置"""
        try:
            gateway_id = gateway_data.get('gateway_id')
            if not gateway_id:
                logger.error("网关ID不能为空")
                return False
            
            # 生成XML配置
            xml_content = self.xml_generator.generate_gateway_xml(gateway_data)
            
            # 验证XML格式
            if not fs_config_manager.validate_xml(xml_content):
                logger.error(f"网关 {gateway_id} 的XML配置格式无效")
                return False
            
            # 获取配置文件路径
            config_path = fs_config_manager.get_gateway_config_path(gateway_id)
            
            # 备份已存在的配置文件
            if config_path.exists():
                fs_config_manager.backup_config_file(config_path)
            
            # 写入配置文件
            success = fs_config_manager.write_config_file(config_path, xml_content)
            
            if success:
                logger.info(f"网关配置已创建: {gateway_id} -> {config_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"创建网关配置失败: {e}")
            return False
    
    async def update_gateway_config(self, gateway_id: str, gateway_data: Dict) -> bool:
        """更新网关配置"""
        gateway_data['gateway_id'] = gateway_id
        return await self.create_gateway_config(gateway_data)
    
    async def delete_gateway_config(self, gateway_id: str) -> bool:
        """删除网关配置"""
        try:
            config_path = fs_config_manager.get_gateway_config_path(gateway_id)
            
            # 备份后删除
            if config_path.exists():
                fs_config_manager.backup_config_file(config_path)
                success = fs_config_manager.delete_config_file(config_path)
                
                if success:
                    logger.info(f"网关配置已删除: {gateway_id}")
                
                return success
            else:
                logger.warning(f"网关配置文件不存在: {gateway_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除网关配置失败: {e}")
            return False
    
    async def sync_gateways_from_database(self) -> int:
        """从数据库同步所有网关配置到FreeSWITCH"""
        try:
            from storage.mysql_client import mysql_client
            
            # 获取所有活动的网关
            gateways = await mysql_client.get_gateways()
            active_gateways = [g for g in gateways if g.is_active]
            
            success_count = 0
            for gateway in active_gateways:
                gateway_data = {
                    'gateway_id': gateway.gateway_id,
                    'name': gateway.name,
                    'username': gateway.username,
                    'password': gateway.password,
                    'realm': gateway.realm,
                    'proxy': gateway.proxy,
                    'register': gateway.register,
                    'retry_seconds': gateway.retry_seconds,
                    'caller_id_in_from': gateway.caller_id_in_from,
                    'contact_params': gateway.contact_params,
                    'codecs': gateway.codecs
                }
                
                if await self.create_gateway_config(gateway_data):
                    success_count += 1
            
            logger.info(f"已同步 {success_count}/{len(active_gateways)} 个网关配置到FreeSWITCH")
            return success_count
            
        except Exception as e:
            logger.error(f"同步网关配置失败: {e}")
            return 0
    
    async def get_gateway_status(self, gateway_id: str) -> Optional[Dict]:
        """获取网关状态（通过ESL）"""
        try:
            # 这里需要通过ESL连接到FreeSWITCH获取网关状态
            # 暂时返回配置文件是否存在的状态
            config_path = fs_config_manager.get_gateway_config_path(gateway_id)
            
            return {
                'gateway_id': gateway_id,
                'config_exists': config_path.exists(),
                'config_path': str(config_path)
            }
        except Exception as e:
            logger.error(f"获取网关状态失败: {e}")
            return None


# 全局网关管理器实例
gateway_manager = GatewayManager()

