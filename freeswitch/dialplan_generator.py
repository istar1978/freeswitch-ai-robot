# freeswitch/dialplan_generator.py
import os
from typing import Dict, Any, List, Optional
from config.settings import config
from utils.logger import setup_logger
from freeswitch.config_manager import fs_config_manager

logger = setup_logger(__name__)

class DialplanGenerator:
    """FreeSWITCH拨号计划生成器"""

    def __init__(self):
        self.dialplan_dir = fs_config_manager.get_dialplan_path()
        self.context_name = config.freeswitch.dialplan_context

    async def generate_dialplan_xml(self) -> str:
        """生成拨号计划XML - 从数据库读取配置"""
        try:
            from storage.mysql_client import mysql_client
            configs = await mysql_client.get_freeswitch_configs()
            scenarios = await mysql_client.get_scenarios()

            # 构建场景映射
            scenario_map = {s.scenario_id: s for s in scenarios}

            # 生成扩展列表
            extensions = []

            for config in configs:
                if not config.is_active:
                    continue

                # 为每个FreeSWITCH实例生成扩展
                extension = self._generate_instance_extension(config, scenario_map)
                extensions.append(extension)

            # 健康检查扩展
            extensions.append(self._generate_health_extension())

            template = f'''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="dialplan" description="AI Robot Dialplan">
    <context name="{self.context_name}">
      {"".join(extensions)}
    </context>
  </section>
</document>'''
            return template

        except Exception as e:
            logger.error(f"生成拨号计划失败: {e}")
            # 返回默认拨号计划
            return self._generate_default_dialplan()

    def _generate_instance_extension(self, config, scenario_map: Dict) -> str:
        """为FreeSWITCH实例生成扩展"""
        conditions = []

        # 为每个场景映射生成条件
        for entry_point, scenario_id in config.scenario_mapping.items():
            if scenario_id in scenario_map and scenario_map[scenario_id].is_active:
                scenario = scenario_map[scenario_id]
                condition = f'''      <condition field="destination_number" expression="^{entry_point}$">
        <action application="set" data="ai_instance_id={config.instance_id}"/>
        <action application="set" data="ai_scenario_id={scenario_id}"/>
        <action application="set" data="hangup_after_bridge=true"/>
        <action application="set" data="continue_on_fail=true"/>
        <action application="set" data="call_timeout={scenario.timeout_seconds}"/>
        <action application="set" data="execute_on_answer=ai_robot_start"/>
        <action application="lua" data="ai_robot_handler.lua"/>
      </condition>'''
                conditions.append(condition)

        if not conditions:
            return ""

        extension_name = f"ai-robot-{config.instance_id}"
        extension = f'''
      <extension name="{extension_name}">
        {"".join(conditions)}
      </extension>'''

        return extension

    def _generate_health_extension(self) -> str:
        """生成健康检查扩展"""
        return '''
      <!-- 健康检查扩展 -->
      <extension name="ai-robot-health">
        <condition field="destination_number" expression="^health$">
          <action application="playback" data="ivr/ivr-welcome_to_freeswitch.wav"/>
          <action application="hangup"/>
        </condition>
      </extension>'''

    def _generate_default_dialplan(self) -> str:
        """生成默认拨号计划（当数据库不可用时）"""
        template = f'''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="dialplan" description="AI Robot Dialplan">
    <context name="{self.context_name}">
      <extension name="ai-robot-default">
        <condition field="destination_number" expression="^{config.freeswitch.dialplan_extension}$">
          <action application="set" data="hangup_after_bridge=true"/>
          <action application="set" data="continue_on_fail=true"/>
          <action application="set" data="call_timeout=300"/>
          <action application="set" data="execute_on_answer=ai_robot_start"/>
          <action application="lua" data="ai_robot_handler.lua"/>
        </condition>
      </extension>

      <!-- 健康检查扩展 -->
      <extension name="ai-robot-health">
        <condition field="destination_number" expression="^health$">
          <action application="playback" data="ivr/ivr-welcome_to_freeswitch.wav"/>
          <action application="hangup"/>
        </condition>
      </extension>
    </context>
  </section>
</document>'''
        return template

    def generate_lua_script(self) -> str:
        """生成Lua脚本 - 支持多实例和场景路由"""
        template = '''-- ai_robot_handler.lua
local session_id = session:get_uuid()
local caller_id = session:getVariable("caller_id_number") or "unknown"
local instance_id = session:getVariable("ai_instance_id") or "default"
local scenario_id = session:getVariable("ai_scenario_id") or "default"

freeswitch.consoleLog("INFO", "AI Robot call started: " .. session_id .. " from " .. caller_id .. " instance: " .. instance_id .. " scenario: " .. scenario_id)

-- 连接到AI机器人API
local api_url = "http://localhost:8080"
local start_url = api_url .. "/call/start"

-- 准备请求数据
local request_data = [[
{
  "session_id": "]] .. session_id .. [[",
  "caller_id": "]] .. caller_id .. [[",
  "instance_id": "]] .. instance_id .. [[",
  "scenario_id": "]] .. scenario_id .. [["
}
]]

-- 发送开始呼叫请求
local curl_cmd = "curl -X POST " .. start_url .. " -H 'Content-Type: application/json' -d '" .. request_data .. "' -s"
local handle = io.popen(curl_cmd)
local result = handle:read("*a")
handle:close()

freeswitch.consoleLog("INFO", "AI Robot start response: " .. result)

-- 设置会话变量
session:setVariable("ai_session_id", session_id)
session:setVariable("ai_instance_id", instance_id)
session:setVariable("ai_scenario_id", scenario_id)

-- 播放欢迎消息
session:answer()
session:sleep(500)

-- 这里应该实现音频流处理
-- 暂时使用简单的等待
session:sleep(1000)

-- 结束呼叫
local end_url = api_url .. "/call/end/" .. session_id
local end_curl = "curl -X POST " .. end_url .. " -s"
local end_handle = io.popen(end_curl)
local end_result = end_handle:read("*a")
end_handle:close()

freeswitch.consoleLog("INFO", "AI Robot call ended: " .. session_id)
'''
        return template

    def save_dialplan(self, xml_content: str, lua_content: str = None):
        """保存拨号计划文件"""
        try:
            # 确保目录存在
            fs_config_manager.ensure_directories()

            # 保存XML文件
            xml_path = self.dialplan_dir / "ai_robot_dialplan.xml"
            fs_config_manager.write_config_file(xml_path, xml_content)

            # 保存Lua脚本
            if lua_content:
                lua_path = self.dialplan_dir / "ai_robot_handler.lua"
                with open(lua_path, 'w', encoding='utf-8') as f:
                    f.write(lua_content)
                logger.info(f"Lua脚本已保存: {lua_path}")

        except Exception as e:
            logger.error(f"保存拨号计划文件失败: {e}")
            raise

    async def save_dialplan_files(self, output_dir: str = None):
        """保存拨号计划文件"""
        from pathlib import Path
        if output_dir is None:
            output_dir = self.dialplan_dir
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存XML拨号计划
        xml_file = output_dir / f"{self.context_name}.xml"
        xml_content = await self.generate_dialplan_xml()
        fs_config_manager.write_config_file(xml_file, xml_content)

        # 保存Lua脚本
        lua_file = output_dir / "ai_robot_handler.lua"
        with open(lua_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_lua_script())

        logger.info(f"拨号计划文件已保存到: {output_dir}")
        return str(xml_file), str(lua_file)

    async def validate_dialplan(self) -> bool:
        """验证拨号计划配置"""
        try:
            xml_content = await self.generate_dialplan_xml()
            return fs_config_manager.validate_xml(xml_content)
        except Exception as e:
            logger.error(f"拨号计划XML格式错误: {e}")
            return False
    
    async def sync_dialplan_from_database(self) -> bool:
        """从数据库同步拨号计划到FreeSWITCH"""
        try:
            # 生成拨号计划XML
            xml_content = await self.generate_dialplan_xml()
            
            # 验证XML格式
            if not fs_config_manager.validate_xml(xml_content):
                logger.error("拨号计划XML格式验证失败")
                return False
            
            # 保存配置文件
            xml_path = self.dialplan_dir / f"{self.context_name}.xml"
            
            # 备份旧配置
            if xml_path.exists():
                fs_config_manager.backup_config_file(xml_path)
            
            # 写入新配置
            success = fs_config_manager.write_config_file(xml_path, xml_content)
            
            if success:
                logger.info(f"拨号计划已同步到FreeSWITCH: {xml_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"同步拨号计划失败: {e}")
            return False
    
    async def generate_entry_point_dialplan(self, entry_point_data: Dict) -> str:
        """为单个入口点生成拨号计划扩展"""
        entry_point_id = entry_point_data.get('entry_point_id', 'entry')
        pattern = entry_point_data.get('dialplan_pattern', '^default$')
        scenario_id = entry_point_data.get('scenario_id', 'default')
        gateway_id = entry_point_data.get('gateway_id', '')
        
        extension = f'''      <extension name="{entry_point_id}">
        <condition field="destination_number" expression="{pattern}">
          <action application="set" data="ai_scenario_id={scenario_id}"/>'''
        
        if gateway_id:
            extension += f'''
          <action application="set" data="ai_gateway_id={gateway_id}"/>'''
        
        extension += '''
          <action application="set" data="hangup_after_bridge=true"/>
          <action application="set" data="continue_on_fail=true"/>
          <action application="set" data="execute_on_answer=ai_robot_start"/>
          <action application="lua" data="ai_robot_handler.lua"/>
        </condition>
      </extension>
'''
        return extension