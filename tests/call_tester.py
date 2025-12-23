# tests/call_tester.py
import asyncio
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import aiohttp
from config.settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float = 0.0
    status: str = "running"  # running, completed, failed
    steps: List[Dict] = None
    error_message: Optional[str] = None
    audio_received: bool = False
    response_quality: float = 0.0  # 0-1, 响应质量评分

    def __post_init__(self):
        if self.steps is None:
            self.steps = []

    def add_step(self, step_name: str, status: str, details: Dict = None):
        """添加测试步骤"""
        step = {
            "timestamp": datetime.now().isoformat(),
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        self.steps.append(step)
        logger.info(f"测试步骤: {step_name} - {status}")

    def complete(self, success: bool = True, error: str = None):
        """完成测试"""
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.status = "completed" if success else "failed"
        if error:
            self.error_message = error

    def to_dict(self):
        """转换为字典"""
        data = asdict(self)
        data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        return data

class CallTester:
    """呼叫测试器"""

    def __init__(self, api_base_url: str = "http://localhost:8080"):
        self.api_base_url = api_base_url
        self.session = aiohttp.ClientSession()
        self.test_results: Dict[str, TestResult] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def simulate_call(self, test_id: str, caller_id: str = "test-1001",
                          expected_responses: List[str] = None) -> TestResult:
        """模拟一次完整呼叫"""
        session_id = f"test-{test_id}-{int(time.time())}"
        result = TestResult(
            test_id=test_id,
            session_id=session_id,
            start_time=datetime.now()
        )
        self.test_results[test_id] = result

        try:
            # 步骤1: 开始呼叫
            result.add_step("call_start", "starting")
            start_success = await self._start_call(session_id, caller_id)
            if not start_success:
                result.add_step("call_start", "failed", {"error": "Failed to start call"})
                result.complete(False, "Call start failed")
                return result

            result.add_step("call_start", "completed")

            # 步骤2: 等待机器人响应
            result.add_step("wait_response", "waiting")
            await asyncio.sleep(2)  # 等待机器人初始化

            # 步骤3: 检查呼叫状态
            status = await self._check_call_status(session_id)
            if status.get("active"):
                result.add_step("status_check", "passed", status)
            else:
                result.add_step("status_check", "failed", status)

            # 步骤4: 模拟用户输入（如果有预期响应）
            if expected_responses:
                for i, response in enumerate(expected_responses):
                    result.add_step(f"user_input_{i+1}", "sending", {"text": response})
                    # 这里可以扩展为实际发送音频或文本
                    await asyncio.sleep(1)

            # 步骤5: 等待处理完成
            await asyncio.sleep(3)

            # 步骤6: 检查最终状态
            final_status = await self._check_call_status(session_id)
            result.add_step("final_check", "completed", final_status)

            # 步骤7: 结束呼叫
            result.add_step("call_end", "ending")
            end_success = await self._end_call(session_id)
            result.add_step("call_end", "completed" if end_success else "failed")

            result.complete(True)

        except Exception as e:
            logger.error(f"测试异常: {e}")
            result.add_step("error", "exception", {"error": str(e)})
            result.complete(False, str(e))

        return result

    async def _start_call(self, session_id: str, caller_id: str) -> bool:
        """开始呼叫"""
        try:
            url = f"{self.api_base_url}/call/start"
            data = {
                "session_id": session_id,
                "caller_id": caller_id
            }

            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("status") == "success"
                else:
                    logger.error(f"开始呼叫失败: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"开始呼叫异常: {e}")
            return False

    async def _check_call_status(self, session_id: str) -> Dict:
        """检查呼叫状态"""
        try:
            url = f"{self.api_base_url}/call/status/{session_id}"

            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Status check failed: {response.status}"}

        except Exception as e:
            logger.error(f"检查状态异常: {e}")
            return {"error": str(e)}

    async def _end_call(self, session_id: str) -> bool:
        """结束呼叫"""
        try:
            url = f"{self.api_base_url}/call/end/{session_id}"

            async with self.session.post(url) as response:
                return response.status == 200

        except Exception as e:
            logger.error(f"结束呼叫异常: {e}")
            return False

    def save_results(self, filename: str = None):
        """保存测试结果"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_results_{timestamp}.json"

        results = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.test_results),
            "results": [result.to_dict() for result in self.test_results.values()]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"测试结果已保存到: {filename}")
        return filename

    def get_summary(self) -> Dict:
        """获取测试摘要"""
        total = len(self.test_results)
        completed = sum(1 for r in self.test_results.values() if r.status == "completed")
        failed = sum(1 for r in self.test_results.values() if r.status == "failed")
        avg_duration = sum(r.duration for r in self.test_results.values()) / total if total > 0 else 0

        return {
            "total_tests": total,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total if total > 0 else 0,
            "average_duration": avg_duration
        }

async def run_batch_tests(test_count: int = 5, api_url: str = "http://localhost:8080"):
    """运行批量测试"""
    logger.info(f"开始批量测试: {test_count} 个测试")

    async with CallTester(api_url) as tester:
        tasks = []
        for i in range(test_count):
            test_id = f"batch_test_{i+1}"
            task = asyncio.create_task(
                tester.simulate_call(
                    test_id=test_id,
                    caller_id=f"test-{1000+i}",
                    expected_responses=["你好", "测试一下功能"]
                )
            )
            tasks.append(task)

        # 等待所有测试完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 保存结果
        filename = tester.save_results()

        # 显示摘要
        summary = tester.get_summary()
        logger.info("测试摘要:")
        logger.info(f"  总测试数: {summary['total_tests']}")
        logger.info(f"  成功: {summary['completed']}")
        logger.info(f"  失败: {summary['failed']}")
        logger.info(".2%")
        logger.info(".2f")

        return summary, filename

if __name__ == "__main__":
    # 运行示例测试
    asyncio.run(run_batch_tests(3))