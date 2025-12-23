import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from config.settings import config

def setup_logger(name: str, level: int = None) -> logging.Logger:
    """设置日志记录器"""
    logger = logging.getLogger(name)
    
    if level is None:
        level = config.LOG_LEVEL
        
    logger.setLevel(level)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
        
    formatter = logging.Formatter(config.LOG_FORMAT)
    
    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件handler（轮转）
    try:
        os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
        file_handler = RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"无法创建文件日志: {e}")
    
    # 避免传播到根logger
    logger.propagate = False
    
    return logger
