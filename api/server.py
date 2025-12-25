# api/server.py
import asyncio
import json
from aiohttp import web
from config.settings import config
from utils.logger import setup_logger
from freeswitch.esl_handler import FreeSwitchHandler
from tests.call_tester import CallTester
from outbound.outbound_manager import OutboundManager
from scenarios.scenario_manager import ScenarioManager

logger = setup_logger(__name__)

class APIServer:
    def __init__(self, fs_handler: FreeSwitchHandler, call_tester: CallTester = None,
                 outbound_manager: OutboundManager = None, scenario_manager: ScenarioManager = None):
        self.fs_handler = fs_handler
        self.call_tester = call_tester
        self.outbound_manager = outbound_manager
        self.scenario_manager = scenario_manager
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.setup_routes()

    def setup_routes(self):
        """设置路由"""
        # 基础呼叫路由
        self.app.router.add_post('/call/start', self.handle_call_start)
        self.app.router.add_get('/call/status/{session_id}', self.handle_call_status)
        self.app.router.add_post('/call/end/{session_id}', self.handle_call_end)

        # 测试路由
        if self.call_tester:
            self.app.router.add_post('/test/simulate', self.handle_test_simulate)
            self.app.router.add_post('/test/batch', self.handle_test_batch)
            self.app.router.add_get('/test/metrics', self.handle_test_metrics)

        # 外呼路由
        if self.outbound_manager:
            self.app.router.add_post('/outbound/start', self.handle_outbound_start)
            self.app.router.add_post('/outbound/stop', self.handle_outbound_stop)
            self.app.router.add_get('/outbound/status', self.handle_outbound_status)
            self.app.router.add_post('/outbound/add-contact', self.handle_outbound_add_contact)

        # 场景路由
        if self.scenario_manager:
            self.app.router.add_get('/scenarios', self.handle_scenarios_list)
            self.app.router.add_get('/scenarios/{scenario_id}', self.handle_scenario_get)
            self.app.router.add_post('/scenarios/{scenario_id}/activate', self.handle_scenario_activate)

        # 健康检查
        self.app.router.add_get('/health', self.handle_health_check)

    async def handle_call_start(self, request):
        """处理呼叫开始"""
        try:
            data = await request.json()
            session_id = data.get('session_id')
            caller_id = data.get('caller_id', 'unknown')
            instance_id = data.get('instance_id', 'default')
            scenario_id = data.get('scenario_id', 'default')

            if not session_id:
                return web.json_response({'error': 'Missing session_id'}, status=400)

            # 处理来电
            success = await self.fs_handler.handle_incoming_call(session_id, instance_id, scenario_id, caller_id)

            if success:
                return web.json_response({
                    'status': 'success',
                    'session_id': session_id,
                    'message': 'Call started successfully'
                })
            else:
                return web.json_response({
                    'status': 'error',
                    'session_id': session_id,
                    'message': 'Failed to start call'
                }, status=500)

        except Exception as e:
            logger.error(f"处理呼叫开始失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_call_status(self, request):
        """处理呼叫状态查询"""
        session_id = request.match_info['session_id']

        try:
            # 在所有实例中查找会话
            for instance_id, instance in self.fs_handler.instances.items():
                if session_id in instance.sessions:
                    manager = instance.sessions[session_id]
                    return web.json_response({
                        'session_id': session_id,
                        'instance_id': instance_id,
                        'status': manager.state.value,
                        'active': True
                    })
            
            # 会话不存在
            return web.json_response({
                'session_id': session_id,
                'status': 'not_found',
                'active': False
            }, status=404)

        except Exception as e:
            logger.error(f"查询呼叫状态失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_call_end(self, request):
        """处理呼叫结束"""
        session_id = request.match_info['session_id']

        try:
            # 在所有实例中查找并结束会话
            for instance_id, instance in self.fs_handler.instances.items():
                if session_id in instance.sessions:
                    await instance.sessions[session_id].stop()
                    del instance.sessions[session_id]
                    logger.info(f"呼叫结束: {session_id} (实例: {instance_id})")
                    break

            return web.json_response({
                'status': 'success',
                'session_id': session_id,
                'message': 'Call ended successfully'
            })

        except Exception as e:
            logger.error(f"结束呼叫失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    # 测试相关处理方法
    async def handle_test_simulate(self, request):
        """处理测试模拟"""
        if not self.call_tester:
            return web.json_response({'error': 'Call tester not available'}, status=503)

        try:
            data = await request.json()
            scenario_id = data.get('scenario_id', 'default')
            duration = data.get('duration', 30)
            record_audio = data.get('record_audio', False)

            result = await self.call_tester.simulate_call(scenario_id, duration, record_audio)

            return web.json_response({
                'status': 'success',
                'result': result
            })

        except Exception as e:
            logger.error(f"测试模拟失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_test_batch(self, request):
        """处理批量测试"""
        if not self.call_tester:
            return web.json_response({'error': 'Call tester not available'}, status=503)

        try:
            data = await request.json()
            scenarios = data.get('scenarios', ['default'])
            iterations = data.get('iterations', 5)
            concurrent = data.get('concurrent', True)

            results = await self.call_tester.run_batch_tests(scenarios, iterations, concurrent)

            return web.json_response({
                'status': 'success',
                'results': results
            })

        except Exception as e:
            logger.error(f"批量测试失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_test_metrics(self, request):
        """获取测试指标"""
        if not self.call_tester:
            return web.json_response({'error': 'Call tester not available'}, status=503)

        try:
            metrics = self.call_tester.get_metrics()
            return web.json_response({
                'status': 'success',
                'metrics': metrics
            })

        except Exception as e:
            logger.error(f"获取测试指标失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    # 外呼相关处理方法
    async def handle_outbound_start(self, request):
        """启动外呼活动"""
        if not self.outbound_manager:
            return web.json_response({'error': 'Outbound manager not available'}, status=503)

        try:
            data = await request.json()
            campaign_name = data.get('campaign_name')
            contact_file = data.get('contact_file')
            scenario_id = data.get('scenario_id', 'default')

            if not campaign_name or not contact_file:
                return web.json_response({'error': 'Missing campaign_name or contact_file'}, status=400)

            success = await self.outbound_manager.start_campaign(campaign_name, contact_file, scenario_id)

            if success:
                return web.json_response({
                    'status': 'success',
                    'message': f'Campaign {campaign_name} started'
                })
            else:
                return web.json_response({
                    'status': 'error',
                    'message': 'Failed to start campaign'
                }, status=500)

        except Exception as e:
            logger.error(f"启动外呼活动失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_outbound_stop(self, request):
        """停止外呼活动"""
        if not self.outbound_manager:
            return web.json_response({'error': 'Outbound manager not available'}, status=503)

        try:
            await self.outbound_manager.stop_campaign()
            return web.json_response({
                'status': 'success',
                'message': 'Campaign stopped'
            })

        except Exception as e:
            logger.error(f"停止外呼活动失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_outbound_status(self, request):
        """获取外呼状态"""
        if not self.outbound_manager:
            return web.json_response({'error': 'Outbound manager not available'}, status=503)

        try:
            status = self.outbound_manager.get_status()
            return web.json_response({
                'status': 'success',
                'campaign_status': status
            })

        except Exception as e:
            logger.error(f"获取外呼状态失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_outbound_add_contact(self, request):
        """添加外呼联系人"""
        if not self.outbound_manager:
            return web.json_response({'error': 'Outbound manager not available'}, status=503)

        try:
            data = await request.json()
            contact = data.get('contact')

            if not contact:
                return web.json_response({'error': 'Missing contact data'}, status=400)

            success = await self.outbound_manager.add_contact(contact)

            if success:
                return web.json_response({
                    'status': 'success',
                    'message': 'Contact added successfully'
                })
            else:
                return web.json_response({
                    'status': 'error',
                    'message': 'Failed to add contact'
                }, status=500)

        except Exception as e:
            logger.error(f"添加联系人失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    # 场景相关处理方法
    async def handle_scenarios_list(self, request):
        """获取场景列表"""
        if not self.scenario_manager:
            return web.json_response({'error': 'Scenario manager not available'}, status=503)

        try:
            scenarios = self.scenario_manager.get_all_scenarios()
            scenario_dicts = [s.to_dict() for s in scenarios]
            return web.json_response({
                'status': 'success',
                'scenarios': scenario_dicts
            })

        except Exception as e:
            logger.error(f"获取场景列表失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_scenario_get(self, request):
        """获取特定场景配置"""
        if not self.scenario_manager:
            return web.json_response({'error': 'Scenario manager not available'}, status=503)

        scenario_id = request.match_info['scenario_id']

        try:
            scenario = self.scenario_manager.get_scenario_config(scenario_id)

            if scenario:
                return web.json_response({
                    'status': 'success',
                    'scenario': scenario
                })
            else:
                return web.json_response({
                    'status': 'error',
                    'message': f'Scenario {scenario_id} not found'
                }, status=404)

        except Exception as e:
            logger.error(f"获取场景配置失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_scenario_activate(self, request):
        """激活场景"""
        if not self.scenario_manager:
            return web.json_response({'error': 'Scenario manager not available'}, status=503)

        scenario_id = request.match_info['scenario_id']

        try:
            success = await self.scenario_manager.activate_scenario(scenario_id)

            if success:
                return web.json_response({
                    'status': 'success',
                    'message': f'Scenario {scenario_id} activated'
                })
            else:
                return web.json_response({
                    'status': 'error',
                    'message': f'Failed to activate scenario {scenario_id}'
                }, status=500)

        except Exception as e:
            logger.error(f"激活场景失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_health_check(self, request):
        """健康检查"""
        try:
            # 检查是否有任何FreeSWITCH实例连接
            any_connected = any(instance.connected for instance in self.fs_handler.instances.values())
            total_sessions = sum(len(instance.sessions) for instance in self.fs_handler.instances.values())
            
            return web.json_response({
                'status': 'healthy',
                'freeswitch_connected': any_connected,
                'active_sessions': total_sessions,
                'instances': len(self.fs_handler.instances)
            })
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def start(self, host: str = None, port: int = None):
        """启动服务器"""
        if host is None:
            host = config.api.host
        if port is None:
            port = config.api.port

        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, host, port)
            await self.site.start()
            logger.info(f"API服务器启动在 http://{host}:{port}")
        except Exception as e:
            logger.error(f"启动API服务器失败: {e}")
            raise

    async def stop(self):
        """停止服务器"""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            logger.info("API服务器已停止")
        except Exception as e:
            logger.error(f"停止API服务器失败: {e}")