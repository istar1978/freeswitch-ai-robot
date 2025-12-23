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

        token = self.auth_manager.authenticate_user(username, password)
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
        scenarios = self.scenario_manager.list_scenarios()
        return web.json_response({
            'success': True,
            'scenarios': scenarios
        })

    async def api_create_scenario(self, request):
        """创建场景"""
        data = await request.json()
        scenario_id = data.get('scenario_id')

        # 这里应该实现场景创建逻辑
        return web.json_response({'success': True, 'message': 'Scenario creation not implemented yet'})

    async def api_update_scenario(self, request):
        """更新场景"""
        scenario_id = request.match_info['scenario_id']
        data = await request.json()

        # 这里应该实现场景更新逻辑
        return web.json_response({'success': True, 'message': 'Scenario update not implemented yet'})

    async def api_delete_scenario(self, request):
        """删除场景"""
        scenario_id = request.match_info['scenario_id']

        # 这里应该实现场景删除逻辑
        return web.json_response({'success': True, 'message': 'Scenario deletion not implemented yet'})

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
        for session_id, manager in self.fs_handler.sessions.items():
            active_calls.append({
                'session_id': session_id,
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
        return web.json_response({
            'success': True,
            'settings': {
                'webui': {
                    'enabled': config.webui.enabled,
                    'host': config.webui.host,
                    'port': config.webui.port
                },
                'auth': {
                    'enabled': config.auth.enabled,
                    'admin_username': config.auth.admin_username
                }
            }
        })

    async def api_update_settings(self, request):
        """更新系统设置"""
        data = await request.json()

        # 这里应该实现设置更新逻辑
        return web.json_response({'success': True, 'message': 'Settings update not implemented yet'})

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