# freeswitch/config_sync.py
import asyncio
from typing import Dict, Optional, List
from utils.logger import setup_logger
from freeswitch.gateway_manager import gateway_manager
from freeswitch.dialplan_generator import DialplanGenerator

logger = setup_logger(__name__)


class FreeSwitchConfigSync:
    """FreeSWITCH配置同步器 - 通过ESL命令同步配置"""
    
    def __init__(self, esl_handler=None):
        self.esl_handler = esl_handler
        self.dialplan_generator = DialplanGenerator()
    
    async def reload_xml(self, instance_id: str = 'default') -> bool:
        """重新加载FreeSWITCH XML配置"""
        try:
            if not self.esl_handler:
                logger.warning("ESL处理器未初始化，无法执行reload命令")
                return False
            
            # 通过ESL执行reloadxml命令
            instance = self.esl_handler.instances.get(instance_id)
            if not instance or not instance.connection:
                logger.error(f"FreeSWITCH实例 {instance_id} 未连接")
                return False
            
            result = await instance.connection.api('reloadxml')
            logger.info(f"FreeSWITCH {instance_id} XML配置已重新加载: {result}")
            return True
            
        except Exception as e:
            logger.error(f"重新加载XML配置失败: {e}")
            return False
    
    async def reload_gateway(self, gateway_id: str, profile: str = 'external', 
                           instance_id: str = 'default') -> bool:
        """重新加载指定网关"""
        try:
            if not self.esl_handler:
                logger.warning("ESL处理器未初始化，无法执行reload gateway命令")
                return False
            
            instance = self.esl_handler.instances.get(instance_id)
            if not instance or not instance.connection:
                logger.error(f"FreeSWITCH实例 {instance_id} 未连接")
                return False
            
            # 执行 sofia profile <profile> rescan 命令
            cmd = f'sofia profile {profile} rescan'
            result = await instance.connection.api(cmd)
            logger.info(f"网关 {gateway_id} 已重新加载: {result}")
            return True
            
        except Exception as e:
            logger.error(f"重新加载网关失败: {e}")
            return False
    
    async def get_gateway_status(self, gateway_id: str, profile: str = 'external',
                                instance_id: str = 'default') -> Optional[Dict]:
        """获取网关状态"""
        try:
            if not self.esl_handler:
                logger.warning("ESL处理器未初始化")
                return None
            
            instance = self.esl_handler.instances.get(instance_id)
            if not instance or not instance.connection:
                logger.error(f"FreeSWITCH实例 {instance_id} 未连接")
                return None
            
            # 执行 sofia status gateway <gateway_id>
            cmd = f'sofia status gateway {gateway_id}'
            result = await instance.connection.api(cmd)
            
            # 解析状态结果
            status_info = {
                'gateway_id': gateway_id,
                'profile': profile,
                'raw_status': result
            }
            
            # 简单解析状态（实际可能需要更复杂的解析逻辑）
            if 'REGED' in result:
                status_info['state'] = 'registered'
            elif 'NOREG' in result:
                status_info['state'] = 'not_registered'
            elif 'FAILED' in result:
                status_info['state'] = 'failed'
            else:
                status_info['state'] = 'unknown'
            
            return status_info
            
        except Exception as e:
            logger.error(f"获取网关状态失败: {e}")
            return None
    
    async def sync_gateway_config(self, gateway_id: str, gateway_data: Dict,
                                 instance_id: str = 'default') -> bool:
        """同步网关配置到FreeSWITCH"""
        try:
            # 1. 创建网关配置文件
            success = await gateway_manager.create_gateway_config(gateway_data)
            if not success:
                logger.error(f"创建网关配置失败: {gateway_id}")
                return False
            
            # 2. 重新加载XML配置
            if not await self.reload_xml(instance_id):
                logger.warning(f"重新加载XML配置失败，网关配置可能未生效: {gateway_id}")
            
            # 3. 重新加载网关
            profile = gateway_data.get('profile', 'external')
            if not await self.reload_gateway(gateway_id, profile, instance_id):
                logger.warning(f"重新加载网关失败: {gateway_id}")
            
            logger.info(f"网关配置已同步到FreeSWITCH: {gateway_id}")
            return True
            
        except Exception as e:
            logger.error(f"同步网关配置失败: {e}")
            return False
    
    async def sync_dialplan_config(self, instance_id: str = 'default') -> bool:
        """同步拨号计划配置到FreeSWITCH"""
        try:
            # 1. 从数据库同步拨号计划到配置文件
            success = await self.dialplan_generator.sync_dialplan_from_database()
            if not success:
                logger.error("同步拨号计划到配置文件失败")
                return False
            
            # 2. 重新加载XML配置
            if not await self.reload_xml(instance_id):
                logger.error("重新加载XML配置失败")
                return False
            
            logger.info("拨号计划配置已同步到FreeSWITCH")
            return True
            
        except Exception as e:
            logger.error(f"同步拨号计划配置失败: {e}")
            return False
    
    async def sync_all_configs(self, instance_id: str = 'default') -> Dict[str, bool]:
        """同步所有配置到FreeSWITCH"""
        results = {
            'gateways': False,
            'dialplan': False,
            'reload_xml': False
        }
        
        try:
            # 1. 同步所有网关配置
            gateway_count = await gateway_manager.sync_gateways_from_database()
            results['gateways'] = gateway_count > 0
            
            # 2. 同步拨号计划
            results['dialplan'] = await self.dialplan_generator.sync_dialplan_from_database()
            
            # 3. 重新加载XML配置
            results['reload_xml'] = await self.reload_xml(instance_id)
            
            logger.info(f"配置同步完成: {results}")
            return results
            
        except Exception as e:
            logger.error(f"同步所有配置失败: {e}")
            return results
    
    async def check_freeswitch_status(self, instance_id: str = 'default') -> Optional[Dict]:
        """检查FreeSWITCH服务状态"""
        try:
            if not self.esl_handler:
                return {'status': 'disconnected', 'message': 'ESL处理器未初始化'}
            
            instance = self.esl_handler.instances.get(instance_id)
            if not instance or not instance.connection:
                return {'status': 'disconnected', 'message': f'实例 {instance_id} 未连接'}
            
            # 执行status命令获取FreeSWITCH状态
            result = await instance.connection.api('status')
            
            return {
                'status': 'connected',
                'instance_id': instance_id,
                'raw_status': result
            }
            
        except Exception as e:
            logger.error(f"检查FreeSWITCH状态失败: {e}")
            return {'status': 'error', 'message': str(e)}


# 全局配置同步器实例
config_sync = None

def init_config_sync(esl_handler):
    """初始化配置同步器"""
    global config_sync
    config_sync = FreeSwitchConfigSync(esl_handler)
    return config_sync
