"""
安全相关功能模块
包括：JWT令牌生成与验证、密码加密、API Key加密等
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
from app.core.config import settings


# ==================== 密码加密 ====================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


# ==================== JWT令牌 ====================
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建JWT访问令牌
    
    Args:
        data: 要编码的数据（通常包含user_id, role等）
        expires_delta: 过期时间增量，如不指定则使用配置的默认值
    
    Returns:
        JWT令牌字符串
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解码JWT令牌
    
    Args:
        token: JWT令牌字符串
    
    Returns:
        解码后的数据字典，如果令牌无效则返回None
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


# ==================== API Key加密 ====================
class APIKeyEncryption:
    """API Key加密工具类，使用AES加密"""
    
    def __init__(self):
        # 将32字节的密钥编码为Fernet所需的格式
        key = settings.AES_ENCRYPTION_KEY.encode()
        # Fernet需要base64编码的32字节密钥
        self.cipher = Fernet(base64.urlsafe_b64encode(key))
    
    def encrypt(self, plain_text: str) -> str:
        """
        加密API Key
        
        Args:
            plain_text: 明文API Key
        
        Returns:
            加密后的字符串
        """
        encrypted = self.cipher.encrypt(plain_text.encode())
        return encrypted.decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        解密API Key
        
        Args:
            encrypted_text: 加密的API Key
        
        Returns:
            明文API Key
        """
        decrypted = self.cipher.decrypt(encrypted_text.encode())
        return decrypted.decode()


# 创建全局加密实例
api_key_crypto = APIKeyEncryption()


def mask_api_key(api_key: str) -> str:
    """
    脱敏显示API Key
    显示格式：前8个字符 + **** + 后4个字符
    
    Args:
        api_key: 完整的API Key
    
    Returns:
        脱敏后的API Key
    """
    if len(api_key) <= 12:
        # 如果Key太短，只显示前缀和星号
        return api_key[:4] + "****"
    
    return api_key[:8] + "****" + api_key[-4:]


# ==================== 密码验证 ====================
def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    验证密码强度
    
    规则：
    - 长度8-32字符
    - 必须包含字母和数字
    
    Args:
        password: 待验证的密码
    
    Returns:
        (是否有效, 错误信息)
    """
    if len(password) < 8:
        return False, "密码长度不能少于8个字符"
    
    if len(password) > 32:
        return False, "密码长度不能超过32个字符"
    
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not has_letter:
        return False, "密码必须包含字母"
    
    if not has_digit:
        return False, "密码必须包含数字"
    
    return True, ""
