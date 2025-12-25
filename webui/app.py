# webui/app.py
import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from aiohttp import web, WSMsgType
from aiohttp.web_fileresponse import FileResponse
from config.settings import config
from utils.logger import setup_logger
from webui.auth import AuthManager
from scenarios.scenario_manager import ScenarioManager
from outbound.outbound_manager import OutboundManager
from freeswitch.esl_handler import FreeSwitchHandler
from storage.mysql_client import mysql_client, SystemConfig
from sqlalchemy import select

logger = setup_logger(__name__)

class WebUIApp:
    """WebUI应用"""

    def __init__(self, fs_handler: FreeSwitchHandler, scenario_manager: ScenarioManager,
                 outbound_manager: OutboundManager):
        self.fs_handler = fs_handler
        self.scenario_manager = scenario_manager
        self.outbound_manager = outbound_manager
        self.auth_manager = AuthManager()
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.websocket_clients = set()  # WebSocket客户端集合

        # 设置静态文件目录
        static_path = Path(__file__).parent / "static"
        static_path.mkdir(exist_ok=True)
        self.app.router.add_static('/static/', static_path)

        # 设置模板目录
        self.template_path = Path(__file__).parent / "templates"
        self.template_path.mkdir(exist_ok=True)

        self.setup_routes()
        self.setup_auth_middleware()

    def setup_auth_middleware(self):
        """设置认证中间件"""
        @web.middleware
        async def auth_middleware(request, handler):
            # 公开路由
            public_routes = ['/login', '/static/', '/api/auth/login']

            if any(request.path.startswith(route) for route in public_routes):
                return await handler(request)

            # 检查认证
            token = request.cookies.get('auth_token')
            if not token or not self.auth_manager.get_current_user(token):
                return web.Response(status=302, headers={'Location': '/login'})

            return await handler(request)

        self.app.middlewares.append(auth_middleware)

    def setup_routes(self):
        """设置路由"""
        # 页面路由
        self.app.router.add_get('/', self.index_page)
        self.app.router.add_get('/login', self.login_page)
        self.app.router.add_get('/dashboard', self.dashboard_page)
        self.app.router.add_get('/freeswitch', self.freeswitch_page)
        self.app.router.add_get('/scenarios', self.scenarios_page)
        self.app.router.add_get('/outbound', self.outbound_page)
        self.app.router.add_get('/monitoring', self.monitoring_page)
        self.app.router.add_get('/settings', self.settings_page)

        # API路由
        self.app.router.add_post('/api/auth/login', self.api_login)
        self.app.router.add_post('/api/auth/logout', self.api_logout)

        # FreeSWITCH管理API
        self.app.router.add_get('/api/freeswitch/instances', self.api_get_fs_instances)
        self.app.router.add_post('/api/freeswitch/instances', self.api_create_fs_instance)
        self.app.router.add_put('/api/freeswitch/instances/{instance_id}', self.api_update_fs_instance)
        self.app.router.add_delete('/api/freeswitch/instances/{instance_id}', self.api_delete_fs_instance)

        # 场景管理API
        self.app.router.add_get('/api/scenarios', self.api_get_scenarios)
        self.app.router.add_post('/api/scenarios', self.api_create_scenario)
        self.app.router.add_put('/api/scenarios/{scenario_id}', self.api_update_scenario)
        self.app.router.add_delete('/api/scenarios/{scenario_id}', self.api_delete_scenario)

        # FreeSWITCH配置管理API
        self.app.router.add_get('/api/freeswitch/configs', self.api_get_freeswitch_configs)
        self.app.router.add_post('/api/freeswitch/configs', self.api_create_freeswitch_config)
        self.app.router.add_put('/api/freeswitch/configs/{instance_id}', self.api_update_freeswitch_config)
        self.app.router.add_delete('/api/freeswitch/configs/{instance_id}', self.api_delete_freeswitch_config)

        # 外呼管理API
        self.app.router.add_get('/api/outbound/campaigns', self.api_get_campaigns)
        self.app.router.add_post('/api/outbound/campaigns', self.api_create_campaign)
        self.app.router.add_put('/api/outbound/campaigns/{campaign_id}', self.api_update_campaign)
        self.app.router.add_delete('/api/outbound/campaigns/{campaign_id}', self.api_delete_campaign)
        self.app.router.add_post('/api/outbound/campaigns/{campaign_id}/start', self.api_start_campaign)
        self.app.router.add_post('/api/outbound/campaigns/{campaign_id}/stop', self.api_stop_campaign)
        self.app.router.add_post('/api/outbound/import', self.api_import_contacts)
        self.app.router.add_get('/api/outbound/export/{campaign_id}', self.api_export_results)

        # 监控API
        self.app.router.add_get('/api/monitoring/active-calls', self.api_get_active_calls)
        self.app.router.add_get('/api/monitoring/ws', self.websocket_handler)

        # 系统设置API
        self.app.router.add_get('/api/settings', self.api_get_settings)
        self.app.router.add_put('/api/settings', self.api_update_settings)
        self.app.router.add_post('/api/settings/test-service', self.api_test_service)

        # 通话记录API
        self.app.router.add_get('/api/call-records', self.api_get_call_records)
        self.app.router.add_get('/api/call-records/{record_id}', self.api_get_call_record_detail)

    # 页面处理方法
    async def login_page(self, request):
        """登录页面"""
        return self.render_template('login.html')

    async def index_page(self, request):
        """首页"""
        return web.Response(status=302, headers={'Location': '/dashboard'})

    async def dashboard_page(self, request):
        """仪表板页面"""
        return self.render_template('dashboard.html')

    async def freeswitch_page(self, request):
        """FreeSWITCH管理页面"""
        return self.render_template('freeswitch.html')

    async def scenarios_page(self, request):
        """场景管理页面"""
        return self.render_template('scenarios.html')

    async def outbound_page(self, request):
        """外呼管理页面"""
        return self.render_template('outbound.html')

    async def monitoring_page(self, request):
        """监控页面"""
        return self.render_template('monitoring.html')

    async def settings_page(self, request):
        """设置页面"""
        return self.render_template('settings.html')

    def render_template(self, template_name: str, **kwargs) -> web.Response:
        """渲染模板"""
        template_file = self.template_path / template_name
        if template_file.exists():
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            return web.Response(text=content, content_type='text/html')
        else:
            return web.Response(text=f"Template {template_name} not found", status=404)

    # API处理方法
    async def api_login(self, request):
        """登录API"""
        data = await request.json()
        username = data.get('username')
        password = data.get('password')

        token = await self.auth_manager.authenticate_user(username, password)
        if token:
            response = web.json_response({'success': True, 'token': token})
            response.set_cookie('auth_token', token, max_age=config.auth.jwt_expiration)
            return response
        else:
            return web.json_response({'success': False, 'message': 'Invalid credentials'}, status=401)

    async def api_logout(self, request):
        """登出API"""
        response = web.json_response({'success': True})
        response.del_cookie('auth_token')
        return response

    # FreeSWITCH管理API
    async def api_get_fs_instances(self, request):
        """获取FreeSWITCH实例列表"""
        return web.json_response({
            'success': True,
            'instances': config.multi_fs.instances
        })

    async def api_create_fs_instance(self, request):
        """创建FreeSWITCH实例"""
        data = await request.json()
        instance_id = data.get('instance_id')

        if instance_id in config.multi_fs.instances:
            return web.json_response({'success': False, 'message': 'Instance already exists'}, status=400)

        config.multi_fs.instances[instance_id] = {
            'host': data.get('host'),
            'port': data.get('port', 8021),
            'password': data.get('password'),
            'enabled_scenarios': data.get('enabled_scenarios', []),
            'description': data.get('description', '')
        }

        return web.json_response({'success': True})

    async def api_update_fs_instance(self, request):
        """更新FreeSWITCH实例"""
        instance_id = request.match_info['instance_id']
        data = await request.json()

        if instance_id not in config.multi_fs.instances:
            return web.json_response({'success': False, 'message': 'Instance not found'}, status=404)

        config.multi_fs.instances[instance_id].update(data)
        return web.json_response({'success': True})

    async def api_delete_fs_instance(self, request):
        """删除FreeSWITCH实例"""
        instance_id = request.match_info['instance_id']

        if instance_id not in config.multi_fs.instances:
            return web.json_response({'success': False, 'message': 'Instance not found'}, status=404)

        del config.multi_fs.instances[instance_id]
        return web.json_response({'success': True})

    # 场景管理API
    async def api_get_scenarios(self, request):
        """获取场景列表"""
        try:
            from storage.mysql_client import mysql_client
            scenarios = await mysql_client.get_scenarios()
            scenario_dicts = []
            for s in scenarios:
                scenario_dicts.append({
                    'id': s.id,
                    'scenario_id': s.scenario_id,
                    'name': s.name,
                    'description': s.description,
                    'entry_points': s.entry_points,
                    'system_prompt': s.system_prompt,
                    'welcome_message': s.welcome_message,
                    'fallback_responses': s.fallback_responses,
                    'max_turns': s.max_turns,
                    'timeout_seconds': s.timeout_seconds,
                    'custom_settings': s.custom_settings,
                    'is_active': s.is_active,
                    'created_at': s.created_at.isoformat() if s.created_at else None,
                    'updated_at': s.updated_at.isoformat() if s.updated_at else None
                })
            return web.json_response({
                'success': True,
                'scenarios': scenario_dicts
            })
        except Exception as e:
            logger.error(f"获取场景列表失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def api_create_scenario(self, request):
        """创建场景"""
        try:
            from storage.mysql_client import mysql_client
            data = await request.json()
            
            scenario_data = {
                'scenario_id': data['scenario_id'],
                'name': data['name'],
                'description': data.get('description', ''),
                'entry_points': data.get('entry_points', []),
                'system_prompt': data['system_prompt'],
                'welcome_message': data['welcome_message'],
                'fallback_responses': data.get('fallback_responses', []),
                'max_turns': data.get('max_turns', 10),
                'timeout_seconds': data.get('timeout_seconds', 300),
                'custom_settings': data.get('custom_settings', {}),
                'is_active': data.get('is_active', True)
            }
            
            scenario = await mysql_client.create_scenario(scenario_data)
            return web.json_response({
                'success': True, 
                'scenario': {
                    'id': scenario.id,
                    'scenario_id': scenario.scenario_id,
                    'name': scenario.name
                }
            })
        except Exception as e:
            logger.error(f"创建场景失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def api_update_scenario(self, request):
        """更新场景"""
        try:
            from storage.mysql_client import mysql_client
            scenario_id = request.match_info['scenario_id']
            data = await request.json()
            
            update_data = {}
            for field in ['name', 'description', 'entry_points', 'system_prompt', 
                         'welcome_message', 'fallback_responses', 'max_turns', 
                         'timeout_seconds', 'custom_settings', 'is_active']:
                if field in data:
                    update_data[field] = data[field]
            
            scenario = await mysql_client.update_scenario(scenario_id, update_data)
            if scenario:
                return web.json_response({'success': True})
            else:
                return web.json_response({'success': False, 'error': '场景不存在'}, status=404)
        except Exception as e:
            logger.error(f"更新场景失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def api_delete_scenario(self, request):
        """删除场景"""
        try:
            from storage.mysql_client import mysql_client
            scenario_id = request.match_info['scenario_id']
            
            success = await mysql_client.delete_scenario(scenario_id)
            if success:
                return web.json_response({'success': True})
            else:
                return web.json_response({'success': False, 'error': '场景不存在'}, status=404)
        except Exception as e:
            logger.error(f"删除场景失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    # FreeSWITCH配置管理API
    async def api_get_freeswitch_configs(self, request):
        """获取FreeSWITCH配置列表"""
        try:
            from storage.mysql_client import mysql_client
            configs = await mysql_client.get_freeswitch_configs()
            config_dicts = []
            for c in configs:
                config_dicts.append({
                    'id': c.id,
                    'instance_id': c.instance_id,
                    'name': c.name,
                    'host': c.host,
                    'port': c.port,
                    'scenario_mapping': c.scenario_mapping,
                    'is_active': c.is_active,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None
                })
            return web.json_response({
                'success': True,
                'configs': config_dicts
            })
        except Exception as e:
            logger.error(f"获取FreeSWITCH配置列表失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def api_create_freeswitch_config(self, request):
        """创建FreeSWITCH配置"""
        try:
            from storage.mysql_client import mysql_client
            data = await request.json()
            
            config_data = {
                'instance_id': data['instance_id'],
                'name': data['name'],
                'host': data['host'],
                'port': data.get('port', 8021),
                'password': data['password'],
                'scenario_mapping': data.get('scenario_mapping', {}),
                'is_active': data.get('is_active', True)
            }
            
            config = await mysql_client.create_freeswitch_config(config_data)
            return web.json_response({
                'success': True, 
                'config': {
                    'id': config.id,
                    'instance_id': config.instance_id,
                    'name': config.name
                }
            })
        except Exception as e:
            logger.error(f"创建FreeSWITCH配置失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def api_update_freeswitch_config(self, request):
        """更新FreeSWITCH配置"""
        try:
            from storage.mysql_client import mysql_client
            instance_id = request.match_info['instance_id']
            data = await request.json()
            
            update_data = {}
            for field in ['name', 'host', 'port', 'password', 'scenario_mapping', 'is_active']:
                if field in data:
                    update_data[field] = data[field]
            
            config = await mysql_client.update_freeswitch_config(instance_id, update_data)
            if config:
                return web.json_response({'success': True})
            else:
                return web.json_response({'success': False, 'error': 'FreeSWITCH配置不存在'}, status=404)
        except Exception as e:
            logger.error(f"更新FreeSWITCH配置失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def api_delete_freeswitch_config(self, request):
        """删除FreeSWITCH配置"""
        try:
            from storage.mysql_client import mysql_client
            instance_id = request.match_info['instance_id']
            
            success = await mysql_client.delete_freeswitch_config(instance_id)
            if success:
                return web.json_response({'success': True})
            else:
                return web.json_response({'success': False, 'error': 'FreeSWITCH配置不存在'}, status=404)
        except Exception as e:
            logger.error(f"删除FreeSWITCH配置失败: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    # 外呼管理API
    async def api_get_campaigns(self, request):
        """获取外呼活动列表"""
        # 这里应该实现获取活动列表逻辑
        return web.json_response({
            'success': True,
            'campaigns': []
        })

    async def api_create_campaign(self, request):
        """创建外呼活动"""
        data = await request.json()

        # 这里应该实现活动创建逻辑
        return web.json_response({'success': True, 'message': 'Campaign creation not implemented yet'})

    async def api_update_campaign(self, request):
        """更新外呼活动"""
        campaign_id = request.match_info['campaign_id']
        data = await request.json()

        # 这里应该实现活动更新逻辑
        return web.json_response({'success': True, 'message': 'Campaign update not implemented yet'})

    async def api_delete_campaign(self, request):
        """删除外呼活动"""
        campaign_id = request.match_info['campaign_id']

        # 这里应该实现活动删除逻辑
        return web.json_response({'success': True, 'message': 'Campaign deletion not implemented yet'})

    async def api_start_campaign(self, request):
        """启动外呼活动"""
        campaign_id = request.match_info['campaign_id']

        # 这里应该实现活动启动逻辑
        return web.json_response({'success': True, 'message': 'Campaign start not implemented yet'})

    async def api_stop_campaign(self, request):
        """停止外呼活动"""
        campaign_id = request.match_info['campaign_id']

        # 这里应该实现活动停止逻辑
        return web.json_response({'success': True, 'message': 'Campaign stop not implemented yet'})

    async def api_import_contacts(self, request):
        """导入联系人"""
        data = await request.post()

        # 这里应该实现联系人导入逻辑
        return web.json_response({'success': True, 'message': 'Contact import not implemented yet'})

    async def api_export_results(self, request):
        """导出结果"""
        campaign_id = request.match_info['campaign_id']

        # 这里应该实现结果导出逻辑
        return web.json_response({'success': True, 'message': 'Result export not implemented yet'})

    # 监控API
    async def api_get_active_calls(self, request):
        """获取活跃通话"""
        active_calls = []
        for instance_id, instance in self.fs_handler.instances.items():
            for session_id, manager in instance.sessions.items():
                active_calls.append({
                    'session_id': session_id,
                    'instance_id': instance_id,
                    'state': manager.state.value,
                    'start_time': getattr(manager, 'start_time', None),
                    'caller_id': getattr(manager, 'caller_id', None)
                })

        return web.json_response({
            'success': True,
            'active_calls': active_calls
        })

    async def websocket_handler(self, request):
        """WebSocket处理器"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.websocket_clients.add(ws)

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # 处理客户端消息
                    pass
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
        finally:
            self.websocket_clients.remove(ws)

        return ws

    # 系统设置API
    async def api_get_settings(self, request):
        """获取系统设置"""
        try:
            session = await mysql_client.get_session()
            async with session:
                result = await session.execute(select(SystemConfig))
                configs = {config.key: config.value for config in result.scalars()}

            return web.json_response({
                'success': True,
                'settings': {
                    'webui': configs.get('webui', {
                        'enabled': config.webui.enabled,
                        'host': config.webui.host,
                        'port': config.webui.port
                    }),
                    'auth': configs.get('auth', {
                        'enabled': config.auth.enabled,
                        'admin_username': config.auth.admin_username
                    }),
                    'freeswitch': configs.get('freeswitch', {
                        'host': config.freeswitch.host,
                        'port': config.freeswitch.port,
                        'password': config.freeswitch.password,
                        'audio_sample_rate': config.freeswitch.audio_sample_rate
                    }),
                    'mysql': configs.get('mysql', {
                        'host': config.mysql.host,
                        'port': config.mysql.port,
                        'user': config.mysql.user,
                        'database': config.mysql.database
                    }),
                    'redis': configs.get('redis', {
                        'host': config.redis.host,
                        'port': config.redis.port,
                        'db': config.redis.db
                    }),
                    'llm': configs.get('llm', {
                        'api_url': config.llm.api_url,
                        'model': config.llm.model,
                        'timeout': config.llm.timeout,
                        'max_tokens': config.llm.max_tokens,
                        'temperature': config.llm.temperature
                    }),
                    'asr': configs.get('asr', {
                        'ws_url': config.asr.ws_url,
                        'sample_rate': config.asr.sample_rate,
                        'vad_threshold': config.asr.vad_threshold
                    }),
                    'tts': configs.get('tts', {
                        'api_url': config.tts.api_url,
                        'voice': config.tts.voice,
                        'sample_rate': config.tts.sample_rate
                    })
                }
            })
        except Exception as e:
            logger.error(f"获取设置失败: {e}")
            return web.json_response({'success': False, 'message': str(e)}, status=500)

    async def api_update_settings(self, request):
        """更新系统设置"""
        data = await request.json()
        settings = data.get('settings', {})

        try:
            session = await mysql_client.get_session()
            async with session:
                # 更新或插入配置
                for key, value in settings.items():
                    # 检查配置是否已存在
                    result = await session.execute(
                        select(SystemConfig).where(SystemConfig.key == key)
                    )
                    existing_config = result.scalar_one_or_none()

                    if existing_config:
                        existing_config.value = value
                    else:
                        new_config = SystemConfig(key=key, value=value)
                        session.add(new_config)

                await session.commit()

            return web.json_response({'success': True, 'message': '设置已更新'})

        except Exception as e:
            logger.error(f"更新设置失败: {e}")
            return web.json_response({'success': False, 'message': f'更新设置失败: {str(e)}'}, status=500)

    async def _save_config_to_file(self):
        """保存配置到文件"""
        try:
            config_file = Path(__file__).parent.parent / '.env'
            config_content = f"""# AI机器人系统配置
# 生成时间: {asyncio.get_event_loop().time()}

# WebUI配置
WEBUI_ENABLED={config.webui.enabled}
WEBUI_HOST={config.webui.host}
WEBUI_PORT={config.webui.port}

# 认证配置
AUTH_ENABLED={config.auth.enabled}
AUTH_ADMIN_USERNAME={config.auth.admin_username}
AUTH_ADMIN_PASSWORD_HASH={config.auth.admin_password_hash}

# FreeSWITCH配置
FREESWITCH_ENABLED={config.freeswitch.enabled}
FREESWITCH_HOST={config.freeswitch.host}
FREESWITCH_PORT={config.freeswitch.port}
FREESWITCH_PASSWORD={config.freeswitch.password}
FREESWITCH_AUDIO_SAMPLE_RATE={config.freeswitch.audio_sample_rate}

# Redis配置
REDIS_ENABLED={config.redis.enabled}
REDIS_HOST={config.redis.host}
REDIS_PORT={config.redis.port}
REDIS_DB={config.redis.db}
REDIS_PASSWORD={config.redis.password}

# LLM配置
LLM_ENABLED={config.llm.enabled}
LLM_PROVIDER={config.llm.provider}
LLM_API_KEY={config.llm.api_key}
LLM_BASE_URL={config.llm.base_url}
LLM_MODEL={config.llm.model}
LLM_TEMPERATURE={config.llm.temperature}

# ASR配置
ASR_ENABLED={config.asr.enabled}
ASR_PROVIDER={config.asr.provider}
ASR_API_KEY={config.asr.api_key}
ASR_BASE_URL={config.asr.base_url}
ASR_MODEL={config.asr.model}
ASR_SAMPLE_RATE={config.asr.sample_rate}

# TTS配置
TTS_ENABLED={config.tts.enabled}
TTS_PROVIDER={config.tts.provider}
TTS_API_KEY={config.tts.api_key}
TTS_BASE_URL={config.tts.base_url}
TTS_MODEL={config.tts.model}
TTS_VOICE={config.tts.voice}
"""
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(config_content)
            logger.info("配置已保存到文件")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    # 服务测试API
    async def api_test_service(self, request):
        """测试服务可用性"""
        data = await request.json()
        service_type = data.get('service_type')
        service_config = data.get('config', {})

        try:
            if service_type == 'redis':
                result = await self._test_redis_connection(service_config)
            elif service_type == 'freeswitch':
                result = await self._test_freeswitch_connection(service_config)
            elif service_type == 'llm':
                result = await self._test_llm_connection(service_config)
            elif service_type == 'asr':
                result = await self._test_asr_connection(service_config)
            elif service_type == 'tts':
                result = await self._test_tts_connection(service_config)
            else:
                return web.json_response({'success': False, 'message': f'未知的服务类型: {service_type}'}, status=400)

            return web.json_response({'success': True, 'result': result})

        except Exception as e:
            logger.error(f"测试服务失败: {e}")
            return web.json_response({'success': False, 'message': f'测试失败: {str(e)}'}, status=500)

    async def _test_redis_connection(self, config_data):
        """测试Redis连接"""
        import redis.asyncio as redis

        try:
            client = redis.Redis(
                host=config_data.get('host', 'localhost'),
                port=config_data.get('port', 6379),
                db=config_data.get('db', 0),
                password=config_data.get('password'),
                socket_timeout=5
            )
            await client.ping()
            return {'status': 'success', 'message': 'Redis连接成功'}
        except Exception as e:
            return {'status': 'error', 'message': f'Redis连接失败: {str(e)}'}

    async def _test_freeswitch_connection(self, config_data):
        """测试FreeSWITCH连接"""
        import socket
        import asyncio

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((config_data.get('host', 'localhost'), config_data.get('port', 8021)))
            sock.close()

            if result == 0:
                return {'status': 'success', 'message': 'FreeSWITCH连接成功'}
            else:
                return {'status': 'error', 'message': 'FreeSWITCH连接失败: 端口无响应'}
        except Exception as e:
            return {'status': 'error', 'message': f'FreeSWITCH连接失败: {str(e)}'}

    async def _test_llm_connection(self, config_data):
        """测试LLM连接"""
        try:
            # 这里应该根据不同的provider实现不同的测试逻辑
            # 暂时返回模拟结果
            return {'status': 'success', 'message': 'LLM服务测试成功（模拟）'}
        except Exception as e:
            return {'status': 'error', 'message': f'LLM连接失败: {str(e)}'}

    async def _test_asr_connection(self, config_data):
        """测试ASR连接"""
        try:
            # 这里应该实现ASR服务的测试逻辑
            return {'status': 'success', 'message': 'ASR服务测试成功（模拟）'}
        except Exception as e:
            return {'status': 'error', 'message': f'ASR连接失败: {str(e)}'}

    async def _test_tts_connection(self, config_data):
        """测试TTS连接"""
        try:
            # 这里应该实现TTS服务的测试逻辑
            return {'status': 'success', 'message': 'TTS服务测试成功（模拟）'}
        except Exception as e:
            return {'status': 'error', 'message': f'TTS连接失败: {str(e)}'}

    async def broadcast_to_clients(self, message: Dict[str, Any]):
        """向所有WebSocket客户端广播消息"""
        if self.websocket_clients:
            message_json = json.dumps(message)
            await asyncio.gather(
                *[client.send_str(message_json) for client in self.websocket_clients],
                return_exceptions=True
            )

    async def start(self):
        """启动WebUI服务器"""
        if not config.webui.enabled:
            logger.info("WebUI is disabled")
            return

        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, config.webui.host, config.webui.port)
            await self.site.start()
            logger.info(f"WebUI服务器启动在 http://{config.webui.host}:{config.webui.port}")
        except Exception as e:
            logger.error(f"启动WebUI服务器失败: {e}")
            raise

    async def stop(self):
        """停止WebUI服务器"""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            logger.info("WebUI服务器已停止")
        except Exception as e:
            logger.error(f"停止WebUI服务器失败: {e}")

    # 通话记录API
    async def api_get_call_records(self, request):
        """获取通话记录列表"""
        try:
            page = int(request.query.get('page', 1))
            per_page = int(request.query.get('per_page', 20))
            offset = (page - 1) * per_page

            session = await mysql_client.get_session()
            async with session:
                from storage.mysql_client import CallRecord
                from sqlalchemy import desc

                # 获取总数
                total_result = await session.execute(
                    select(CallRecord).with_only_columns([CallRecord.id])
                )
                total = len(total_result.all())

                # 获取分页数据
                result = await session.execute(
                    select(CallRecord).order_by(desc(CallRecord.start_time)).offset(offset).limit(per_page)
                )
                records = result.scalars().all()

                records_data = []
                for record in records:
                    records_data.append({
                        'id': record.id,
                        'session_id': record.session_id,
                        'caller_number': record.caller_number,
                        'start_time': record.start_time.isoformat() if record.start_time else None,
                        'end_time': record.end_time.isoformat() if record.end_time else None,
                        'duration': record.duration,
                        'status': record.status
                    })

            return web.json_response({
                'success': True,
                'records': records_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })

        except Exception as e:
            logger.error(f"获取通话记录失败: {e}")
            return web.json_response({'success': False, 'message': str(e)}, status=500)

    async def api_get_call_record_detail(self, request):
        """获取通话记录详情"""
        try:
            record_id = int(request.match_info['record_id'])

            session = await mysql_client.get_session()
            async with session:
                from storage.mysql_client import CallRecord

                result = await session.execute(
                    select(CallRecord).where(CallRecord.id == record_id)
                )
                record = result.scalar_one_or_none()

                if not record:
                    return web.json_response({'success': False, 'message': '记录不存在'}, status=404)

                import json
                conversation_log = json.loads(record.conversation_log) if record.conversation_log else []

                return web.json_response({
                    'success': True,
                    'record': {
                        'id': record.id,
                        'session_id': record.session_id,
                        'caller_number': record.caller_number,
                        'start_time': record.start_time.isoformat() if record.start_time else None,
                        'end_time': record.end_time.isoformat() if record.end_time else None,
                        'duration': record.duration,
                        'status': record.status,
                        'conversation_log': conversation_log
                    }
                })

        except Exception as e:
            logger.error(f"获取通话记录详情失败: {e}")
            return web.json_response({'success': False, 'message': str(e)}, status=500)