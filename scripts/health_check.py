#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.health_checker import HealthChecker

async def main():
    checker = HealthChecker()
    status = checker.get_status()
    print("服务健康状态:")
    print(f"全局状态: {status['global_status']}")
    for service, info in status['services'].items():
        print(f"{service}: {info['status']} (响应时间: {info.get('response_time', 0):.3f}s)")

if __name__ == "__main__":
    asyncio.run(main())
