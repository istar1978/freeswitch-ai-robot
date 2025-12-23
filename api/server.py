# api/server.py
import asyncio
import json
from aiohttp import web
from config.settings import config
from utils.logger import setup_logger
from freeswitch.esl_handler import FreeSwitchHandler

logger = setup_logger(__name__)

class APIServer:
    def __init__(self, fs_handler: FreeSwitchHandler):
        self.fs_handler = fs_handler
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.setup_routes()

    def setup_routes(self):
        """设置路由"""
        self.app.router.add_post('/call/start', self.handle_call_start)
        self.app.router.add_get('/call/status/{session_id}', self.handle_call_status)
        self.app.router.add_post('/call/end/{session_id}', self.handle_call_end)
        self.app.router.add_get('/health', self.handle_health_check)

    async def handle_call_start(self, request):
        """处理呼叫开始"""
        try:
            data = await request.json()
            session_id = data.get('session_id')
            caller_id = data.get('caller_id', 'unknown')

            if not session_id:
                return web.json_response({'error': 'Missing session_id'}, status=400)

            # 处理来电
            success = await self.fs_handler.handle_incoming_call(session_id, caller_id)

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
            # 检查会话是否存在
            if session_id in self.fs_handler.sessions:
                manager = self.fs_handler.sessions[session_id]
                return web.json_response({
                    'session_id': session_id,
                    'status': manager.state.value,
                    'active': True
                })
            else:
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
            if session_id in self.fs_handler.sessions:
                await self.fs_handler.sessions[session_id].stop()
                del self.fs_handler.sessions[session_id]
                logger.info(f"呼叫结束: {session_id}")

            return web.json_response({
                'status': 'success',
                'session_id': session_id,
                'message': 'Call ended successfully'
            })

        except Exception as e:
            logger.error(f"结束呼叫失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_health_check(self, request):
        """健康检查"""
        try:
            return web.json_response({
                'status': 'healthy',
                'freeswitch_connected': self.fs_handler.connected,
                'active_sessions': len(self.fs_handler.sessions)
            })
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def start(self, host: str = '0.0.0.0', port: int = 8080):
        """启动服务器"""
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