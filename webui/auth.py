# webui/auth.py
import jwt
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config.settings import config
from storage.mysql_client import mysql_client, User
from sqlalchemy import select
from utils.logger import setup_logger

logger = setup_logger(__name__)

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    import hashlib
    HAS_BCRYPT = False

class AuthManager:
    """认证管理器"""

    def __init__(self):
        self.secret_key = config.auth.jwt_secret
        self.algorithm = "HS256"

    async def initialize_admin_user(self):
        """初始化默认管理员用户"""
        if mysql_client.session_maker is None:
            logger.warning("MySQL未连接，跳过管理员用户初始化")
            return
            
        session = await mysql_client.get_session()
        async with session:
            # 检查管理员用户是否已存在
            result = await session.execute(
                select(User).where(User.username == config.auth.admin_username)
            )
            user = result.scalar_one_or_none()

            if not user:
                # 创建默认管理员用户
                hashed_password = self.hash_password(config.auth.admin_password)
                admin_user = User(
                    username=config.auth.admin_username,
                    password_hash=hashed_password,
                    is_admin=True
                )
                session.add(admin_user)
                await session.commit()
                logger.info(f"创建默认管理员用户: {config.auth.admin_username}")
            else:
                logger.info("管理员用户已存在")

    def hash_password(self, password: str) -> str:
        """哈希密码"""
        if HAS_BCRYPT:
            return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        else:
            # 降级到hashlib (仅用于开发)
            import hashlib
            return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        if HAS_BCRYPT:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        else:
            # 降级到hashlib (仅用于开发)
            import hashlib
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

    async def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """用户认证"""
        if not config.auth.enabled:
            return self.create_token(username)

        if mysql_client.session_maker is None:
            logger.warning("MySQL未连接，使用默认认证")
            # 如果MySQL未连接，使用简单的默认认证
            if username == config.auth.admin_username and password == config.auth.admin_password:
                return self.create_token(username)
            return None

        session = await mysql_client.get_session()
        async with session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one_or_none()

            if user and self.verify_password(password, user.password_hash):
                return self.create_token(username)

        return None

    def get_current_user(self, token: str) -> Optional[str]:
        """获取当前用户"""
        payload = self.verify_token(token)
        if payload:
            return payload.get("username")
        return None