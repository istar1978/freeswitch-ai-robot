# webui/auth.py
import hashlib
import jwt
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config.settings import config

class AuthManager:
    """认证管理器"""

    def __init__(self):
        self.secret_key = config.auth.jwt_secret
        self.algorithm = "HS256"

    def hash_password(self, password: str) -> str:
        """哈希密码"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        return self.hash_password(password) == hashed

    def create_token(self, username: str) -> str:
        """创建JWT token"""
        payload = {
            "username": username,
            "exp": int(time.time()) + config.auth.jwt_expiration,
            "iat": int(time.time())
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """用户认证"""
        if not config.auth.enabled:
            return self.create_token(username)

        if username == config.auth.admin_username:
            if config.auth.admin_password_hash:
                if self.verify_password(password, config.auth.admin_password_hash):
                    return self.create_token(username)
            else:
                # 如果没有设置密码哈希，允许空密码登录（仅用于初始设置）
                if not password:
                    return self.create_token(username)

        return None

    def get_current_user(self, token: str) -> Optional[str]:
        """获取当前用户"""
        payload = self.verify_token(token)
        if payload:
            return payload.get("username")
        return None