#!/usr/bin/env python3
"""
测试脚本 - 验证AI机器人新功能
"""
import asyncio
import aiohttp
import json
import time
from config.settings import config

API_BASE_URL = f"http://localhost:{config.api.port}"

async def test_basic_call_flow():
    """测试基础呼叫流程"""
    print("=== 测试基础呼叫流程 ===")

    async with aiohttp.ClientSession() as session:
        # 开始呼叫
        call_data = {
            "session_id": "test-call-001",
            "caller_id": "1001"
        }

        try:
            async with session.post(f"{API_BASE_URL}/call/start", json=call_data) as resp:
                result = await resp.json()
                print(f"开始呼叫结果: {result}")

            # 查询状态
            async with session.get(f"{API_BASE_URL}/call/status/test-call-001") as resp:
                status = await resp.json()
                print(f"呼叫状态: {status}")

            # 结束呼叫
            async with session.post(f"{API_BASE_URL}/call/end/test-call-001") as resp:
                end_result = await resp.json()
                print(f"结束呼叫结果: {end_result}")

        except Exception as e:
            print(f"基础呼叫测试失败: {e}")

async def test_call_simulation():
    """测试呼叫模拟"""
    print("\n=== 测试呼叫模拟 ===")

    async with aiohttp.ClientSession() as session:
        test_data = {
            "scenario_id": "default",
            "duration": 10,
            "record_audio": False
        }

        try:
            async with session.post(f"{API_BASE_URL}/test/simulate", json=test_data) as resp:
                result = await resp.json()
                print(f"呼叫模拟结果: {result}")

        except Exception as e:
            print(f"呼叫模拟测试失败: {e}")

async def test_scenarios():
    """测试场景管理"""
    print("\n=== 测试场景管理 ===")

    async with aiohttp.ClientSession() as session:
        try:
            # 获取场景列表
            async with session.get(f"{API_BASE_URL}/scenarios") as resp:
                scenarios = await resp.json()
                print(f"场景列表: {scenarios}")

            # 获取默认场景配置
            async with session.get(f"{API_BASE_URL}/scenarios/default") as resp:
                scenario = await resp.json()
                print(f"默认场景配置: {scenario}")

        except Exception as e:
            print(f"场景管理测试失败: {e}")

async def test_health_check():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{API_BASE_URL}/health") as resp:
                health = await resp.json()
                print(f"健康状态: {health}")

        except Exception as e:
            print(f"健康检查失败: {e}")

async def main():
    """主测试函数"""
    print("开始AI机器人功能测试...")

    # 等待服务启动
    print("等待服务启动...")
    await asyncio.sleep(3)

    # 运行各项测试
    await test_health_check()
    await test_scenarios()
    await test_call_simulation()
    await test_basic_call_flow()

    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())