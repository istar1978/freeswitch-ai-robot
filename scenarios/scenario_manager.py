# scenarios/scenario_manager.py
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from config.settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class ScenarioConfig:
    """场景配置"""
    scenario_id: str
    name: str
    description: str
    entry_points: List[str]  # 入口点标识符
    system_prompt: str
    welcome_message: str
    fallback_responses: List[str] = field(default_factory=list)
    max_turns: int = 10
    timeout_seconds: int = 300
    custom_settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        """转换为字典"""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "entry_points": self.entry_points,
            "system_prompt": self.system_prompt,
            "welcome_message": self.welcome_message,
            "fallback_responses": self.fallback_responses,
            "max_turns": self.max_turns,
            "timeout_seconds": self.timeout_seconds,
            "custom_settings": self.custom_settings
        }

class ScenarioManager:
    """场景管理器"""

    def __init__(self, config_dir: str = "scenarios"):
        self.config_dir = config_dir
        self.scenarios: Dict[str, ScenarioConfig] = {}
        self.entry_point_map: Dict[str, str] = {}  # 入口点 -> 场景ID映射
        self._ensure_config_dir()
        self.load_scenarios()

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        os.makedirs(self.config_dir, exist_ok=True)

    def load_scenarios(self):
        """加载所有场景配置"""
        self.scenarios.clear()
        self.entry_point_map.clear()

        for filename in os.listdir(self.config_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.config_dir, filename)
                try:
                    self._load_scenario_file(filepath)
                except Exception as e:
                    logger.error(f"加载场景文件失败 {filename}: {e}")

        logger.info(f"已加载 {len(self.scenarios)} 个场景配置")

    def _load_scenario_file(self, filepath: str):
        """加载单个场景文件"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 处理旧格式的场景文件（场景ID作为键）
        if isinstance(data, dict) and not any(key in data for key in ['scenario_id', 'name']):
            # 这是旧格式，每个键都是场景ID
            for scenario_id, scenario_data in data.items():
                try:
                    # 转换旧格式到新格式
                    config_data = {
                        'scenario_id': scenario_id,
                        'name': scenario_data.get('name', scenario_id),
                        'description': scenario_data.get('description', ''),
                        'entry_points': scenario_data.get('entry_points', [scenario_id]),
                        'system_prompt': scenario_data.get('prompt', ''),
                        'welcome_message': scenario_data.get('welcome_message', '您好！'),
                        'fallback_responses': scenario_data.get('fallback_responses', []),
                        'max_turns': scenario_data.get('max_turns', 10),
                        'timeout_seconds': scenario_data.get('max_duration', 300),
                        'custom_settings': {
                            'voice': scenario_data.get('voice', 'female'),
                            'language': scenario_data.get('language', 'zh-CN'),
                            'interrupt_enabled': scenario_data.get('interrupt_enabled', True)
                        }
                    }

                    scenario = ScenarioConfig(**config_data)
                    self.scenarios[scenario.scenario_id] = scenario

                    # 建立入口点映射
                    for entry_point in scenario.entry_points:
                        if entry_point in self.entry_point_map:
                            logger.warning(f"入口点 {entry_point} 被多个场景使用")
                        self.entry_point_map[entry_point] = scenario.scenario_id

                except Exception as e:
                    logger.error(f"加载场景 {scenario_id} 失败: {e}")
        else:
            # 新格式的单个场景文件
            scenario = ScenarioConfig(**data)
            self.scenarios[scenario.scenario_id] = scenario

            # 建立入口点映射
            for entry_point in scenario.entry_points:
                if entry_point in self.entry_point_map:
                    logger.warning(f"入口点 {entry_point} 被多个场景使用")
                self.entry_point_map[entry_point] = scenario.scenario_id

    def save_scenario(self, scenario: ScenarioConfig):
        """保存场景配置"""
        filename = f"{scenario.scenario_id}.json"
        filepath = os.path.join(self.config_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(scenario.to_dict(), f, indent=2, ensure_ascii=False)

        # 重新加载以确保一致性
        self.load_scenarios()
        logger.info(f"场景已保存: {scenario.scenario_id}")

    def get_scenario_by_entry_point(self, entry_point: str) -> Optional[ScenarioConfig]:
        """根据入口点获取场景"""
        scenario_id = self.entry_point_map.get(entry_point)
        return self.scenarios.get(scenario_id) if scenario_id else None

    def get_scenario(self, scenario_id: str) -> Optional[ScenarioConfig]:
        """获取场景配置"""
        return self.scenarios.get(scenario_id)

    def get_all_scenarios(self) -> List[ScenarioConfig]:
        """获取所有场景"""
        return list(self.scenarios.values())

    def create_default_scenarios(self):
        """创建默认场景"""
        # 客服场景
        customer_service = ScenarioConfig(
            scenario_id="customer_service",
            name="客服机器人",
            description="处理客户咨询和投诉",
            entry_points=["customer", "support", "help"],
            system_prompt="""你是专业的客服机器人，负责解答客户问题。
请始终保持礼貌、专业和耐心。
如果无法解决复杂问题，请建议客户联系人工客服。""",
            welcome_message="您好，我是客服机器人，请问有什么可以帮您？",
            fallback_responses=[
                "抱歉，我暂时无法处理这个问题，请稍后再试。",
                "这个问题需要人工客服处理，请您留下联系方式。",
                "感谢您的耐心等待，我们会尽快为您处理。"
            ],
            max_turns=15,
            timeout_seconds=600
        )

        # 销售场景
        sales = ScenarioConfig(
            scenario_id="sales",
            name="销售机器人",
            description="产品介绍和销售咨询",
            entry_points=["sales", "product", "buy"],
            system_prompt="""你是专业的销售机器人，负责介绍产品和服务。
请积极主动，突出产品优势，引导客户购买。
始终保持热情和专业的态度。""",
            welcome_message="您好！我是销售助手，很高兴为您介绍我们的产品和服务。",
            fallback_responses=[
                "关于这个产品详情，建议您访问我们的官方网站。",
                "我来为您转接专业销售顾问。",
                "感谢您的关注，我们的产品一定会让您满意。"
            ],
            max_turns=20,
            timeout_seconds=900
        )

        # 技术支持场景
        tech_support = ScenarioConfig(
            scenario_id="tech_support",
            name="技术支持机器人",
            description="技术问题解答和故障排除",
            entry_points=["tech", "technical", "issue"],
            system_prompt="""你是技术支持机器人，专门解决技术问题。
请提供详细、准确的技术指导。
如果问题复杂，建议升级到高级技术支持。""",
            welcome_message="您好，我是技术支持助手，请描述您遇到的问题。",
            fallback_responses=[
                "这个问题需要进一步诊断，请提供更多详细信息。",
                "建议您重启设备后再次尝试。",
                "这个问题需要专业技术人员处理，请稍候。"
            ],
            max_turns=25,
            timeout_seconds=1200
        )

        # 保存默认场景
        for scenario in [customer_service, sales, tech_support]:
            self.save_scenario(scenario)

        logger.info("默认场景已创建")

    def add_scenario(self, scenario_id: str, name: str, description: str,
                    entry_points: List[str], system_prompt: str,
                    welcome_message: str, **kwargs) -> ScenarioConfig:
        """添加新场景"""
        scenario = ScenarioConfig(
            scenario_id=scenario_id,
            name=name,
            description=description,
            entry_points=entry_points,
            system_prompt=system_prompt,
            welcome_message=welcome_message,
            **kwargs
        )
        self.save_scenario(scenario)
        return scenario

    def update_scenario(self, scenario_id: str, **updates):
        """更新场景配置"""
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            raise ValueError(f"场景不存在: {scenario_id}")

        for key, value in updates.items():
            if hasattr(scenario, key):
                setattr(scenario, key, value)

        self.save_scenario(scenario)
        logger.info(f"场景已更新: {scenario_id}")

    def delete_scenario(self, scenario_id: str):
        """删除场景"""
        if scenario_id not in self.scenarios:
            raise ValueError(f"场景不存在: {scenario_id}")

        # 删除文件
        filename = f"{scenario_id}.json"
        filepath = os.path.join(self.config_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        # 清理映射
        scenario = self.scenarios[scenario_id]
        for entry_point in scenario.entry_points:
            if self.entry_point_map.get(entry_point) == scenario_id:
                del self.entry_point_map[entry_point]

        del self.scenarios[scenario_id]
        logger.info(f"场景已删除: {scenario_id}")

    def get_scenario_stats(self) -> Dict:
        """获取场景统计"""
        return {
            "total_scenarios": len(self.scenarios),
            "total_entry_points": len(self.entry_point_map),
            "scenarios": [
                {
                    "id": s.scenario_id,
                    "name": s.name,
                    "entry_points": len(s.entry_points)
                }
                for s in self.scenarios.values()
            ]
        }