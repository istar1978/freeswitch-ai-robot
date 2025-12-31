# freeswitch/config_manager.py
import os
import platform
from pathlib import Path
from typing import Dict, Optional, List
from utils.logger import setup_logger

logger = setup_logger(__name__)

class FreeSwitchConfigManager:
    """FreeSWITCH配置文件管理器 - 支持Windows和Linux"""
    
    def __init__(self):
        self.os_type = platform.system()
        self.config_base_path = self._detect_freeswitch_path()
        
    def _detect_freeswitch_path(self) -> Optional[Path]:
        """自动检测FreeSWITCH配置文件路径"""
        if self.os_type == "Windows":
            # Windows常见安装路径
            possible_paths = [
                Path("C:/Program Files/FreeSWITCH"),
                Path("C:/FreeSWITCH"),
                Path("D:/FreeSWITCH"),
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "FreeSWITCH"
            ]
        elif self.os_type == "Linux":
            # Linux常见安装路径
            possible_paths = [
                Path("/usr/local/freeswitch"),
                Path("/opt/freeswitch"),
                Path("/etc/freeswitch"),
                Path("/usr/share/freeswitch")
            ]
        else:
            # macOS等其他系统
            possible_paths = [
                Path("/usr/local/freeswitch"),
                Path("/opt/freeswitch")
            ]
        
        # 检测哪个路径存在
        for path in possible_paths:
            if path.exists():
                conf_path = path / "conf"
                if conf_path.exists():
                    logger.info(f"检测到FreeSWITCH配置路径: {conf_path}")
                    return conf_path
        
        # 如果没有找到，使用默认路径
        if self.os_type == "Windows":
            default_path = Path("C:/FreeSWITCH/conf")
        else:
            default_path = Path("/usr/local/freeswitch/conf")
        
        logger.warning(f"未检测到FreeSWITCH安装路径，使用默认路径: {default_path}")
        return default_path
    
    def get_sip_profiles_path(self) -> Path:
        """获取SIP Profiles配置目录"""
        return self.config_base_path / "sip_profiles"
    
    def get_dialplan_path(self) -> Path:
        """获取Dialplan配置目录"""
        return self.config_base_path / "dialplan"
    
    def get_directory_path(self) -> Path:
        """获取Directory配置目录"""
        return self.config_base_path / "directory"
    
    def ensure_directories(self):
        """确保必要的配置目录存在"""
        directories = [
            self.get_sip_profiles_path(),
            self.get_dialplan_path(),
            self.get_directory_path()
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"确保目录存在: {directory}")
    
    def get_gateway_config_path(self, gateway_id: str) -> Path:
        """获取网关配置文件路径"""
        # 网关配置通常放在 sip_profiles/external/ 或 sip_profiles/internal/ 目录下
        return self.get_sip_profiles_path() / "external" / f"{gateway_id}.xml"
    
    def get_dialplan_context_path(self, context_name: str) -> Path:
        """获取Dialplan上下文配置文件路径"""
        return self.get_dialplan_path() / f"{context_name}.xml"
    
    def write_config_file(self, file_path: Path, content: str) -> bool:
        """写入配置文件"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Windows下可能需要处理路径分隔符
            if self.os_type == "Windows":
                # 确保使用正确的路径分隔符
                file_path = Path(str(file_path).replace('/', '\\'))
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"配置文件已写入: {file_path}")
            return True
        except Exception as e:
            logger.error(f"写入配置文件失败 {file_path}: {e}")
            return False
    
    def read_config_file(self, file_path: Path) -> Optional[str]:
        """读取配置文件"""
        try:
            if not file_path.exists():
                logger.warning(f"配置文件不存在: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.debug(f"配置文件已读取: {file_path}")
            return content
        except Exception as e:
            logger.error(f"读取配置文件失败 {file_path}: {e}")
            return None
    
    def delete_config_file(self, file_path: Path) -> bool:
        """删除配置文件"""
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"配置文件已删除: {file_path}")
                return True
            else:
                logger.warning(f"配置文件不存在: {file_path}")
                return False
        except Exception as e:
            logger.error(f"删除配置文件失败 {file_path}: {e}")
            return False
    
    def backup_config_file(self, file_path: Path) -> Optional[Path]:
        """备份配置文件"""
        try:
            if not file_path.exists():
                logger.warning(f"配置文件不存在，无法备份: {file_path}")
                return None
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = file_path.with_suffix(f".{timestamp}.bak")
            
            import shutil
            shutil.copy2(file_path, backup_path)
            
            logger.info(f"配置文件已备份: {file_path} -> {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"备份配置文件失败 {file_path}: {e}")
            return None
    
    def validate_xml(self, content: str) -> bool:
        """验证XML配置文件格式"""
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(content)
            return True
        except Exception as e:
            logger.error(f"XML格式验证失败: {e}")
            return False


# 全局配置管理器实例
fs_config_manager = FreeSwitchConfigManager()

