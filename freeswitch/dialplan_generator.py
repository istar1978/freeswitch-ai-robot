# freeswitch/dialplan_generator.py
import os
from typing import Dict, Any
from config.settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DialplanGenerator:
    """FreeSWITCH拨号计划生成器"""

    def __init__(self):
        self.dialplan_dir = "/usr/local/freeswitch/conf/dialplan"
        self.context_name = config.freeswitch.dialplan_context

    def generate_dialplan_xml(self) -> str:
        """生成拨号计划XML"""
        template = f'''<?xml version="1.0" encoding="UTF-8"?>
<document type="freeswitch/xml">
  <section name="dialplan" description="AI Robot Dialplan">
    <context name="{self.context_name}">
      <extension name="ai-robot-inbound">
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
        """生成Lua脚本"""
        template = f'''-- ai_robot_handler.lua
local session_id = session:get_uuid()
local caller_id = session:getVariable("caller_id_number") or "unknown"

freeswitch.consoleLog("INFO", "AI Robot call started: " .. session_id .. " from " .. caller_id)

-- 设置音频参数
session:setVariable("record_sample_rate", "{config.freeswitch.audio_sample_rate}")
session:setVariable("playback_sample_rate", "{config.freeswitch.audio_sample_rate}")

-- 启动录音
session:execute("record_session", "/tmp/ai_robot_" .. session_id .. ".wav")

-- 通知AI机器人服务
local http = require("socket.http")
local ltn12 = require("ltn12")

local request_body = "{{\\"session_id\\":\\"" .. session_id .. "\\", \\"caller_id\\":\\"" .. caller_id .. "\\"}}"
local response_body = {{}}

local res, code = http.request{{
    url = "http://localhost:8080/call/start",
    method = "POST",
    headers = {{
        ["Content-Type"] = "application/json",
        ["Content-Length"] = string.len(request_body)
    }},
    source = ltn12.source.string(request_body),
    sink = ltn12.sink.table(response_body)
}}

if code == 200 then
    freeswitch.consoleLog("INFO", "AI Robot service notified successfully")
else
    freeswitch.consoleLog("ERR", "Failed to notify AI Robot service: " .. tostring(code))
    session:hangup()
end

-- 保持通话活跃
while session:ready() do
    -- 检查服务状态
    local status_response = {{}}
    local status_res, status_code = http.request{{
        url = "http://localhost:8080/call/status/" .. session_id,
        method = "GET",
        sink = ltn12.sink.table(status_response)
    }}

    if status_code ~= 200 then
        freeswitch.consoleLog("WARNING", "AI Robot service health check failed")
        -- 播放等待音乐
        session:execute("playback", "local_stream://moh")
    end

    -- 等待一段时间后再次检查
    freeswitch.msleep(5000)
end

freeswitch.consoleLog("INFO", "AI Robot call ended: " .. session_id)'''
        return template

    def save_dialplan_files(self, output_dir: str = None):
        """保存拨号计划文件"""
        if output_dir is None:
            output_dir = self.dialplan_dir

        os.makedirs(output_dir, exist_ok=True)

        # 保存XML拨号计划
        xml_file = os.path.join(output_dir, f"{self.context_name}.xml")
        with open(xml_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_dialplan_xml())

        # 保存Lua脚本
        lua_file = os.path.join(output_dir, "ai_robot_handler.lua")
        with open(lua_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_lua_script())

        logger.info(f"拨号计划文件已保存到: {output_dir}")
        return xml_file, lua_file

    def validate_dialplan(self) -> bool:
        """验证拨号计划配置"""
        try:
            import xml.etree.ElementTree as ET
            xml_content = self.generate_dialplan_xml()
            ET.fromstring(xml_content)
            logger.info("拨号计划XML格式验证通过")
            return True
        except Exception as e:
            logger.error(f"拨号计划XML格式错误: {e}")
            return False