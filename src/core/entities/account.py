"""계정 도메인 엔티티"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum


class AccountType(Enum):
    """계정 타입"""
    SUPPLIER = "supplier"
    MARKET = "market"


class AccountStatus(Enum):
    """계정 상태"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


@dataclass
class TokenInfo:
    """토큰 정보"""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    token_type: str = "Bearer"

    def is_expired(self, buffer_minutes: int = 5) -> bool:
        """토큰 만료 확인 (버퍼 시간 포함)"""
        if not self.expires_at:
            return False
        return datetime.now() + timedelta(minutes=buffer_minutes) >= self.expires_at

    def needs_refresh(self, buffer_hours: int = 3) -> bool:
        """토큰 갱신 필요 확인"""
        if not self.expires_at:
            return False
        return datetime.now() + timedelta(hours=buffer_hours) >= self.expires_at


@dataclass
class ApiCredentials:
    """API 인증 정보"""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    vendor_id: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None


@dataclass
class Account:
    """계정 도메인 엔티티"""
    id: str
    account_type: AccountType
    account_name: str
    username: str
    password_encrypted: str
    api_credentials: Optional[ApiCredentials] = None
    token_info: Optional[TokenInfo] = None
    status: AccountStatus = AccountStatus.ACTIVE
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # 설정 정보
    default_margin_rate: float = 0.3
    sync_enabled: bool = True
    last_sync_at: Optional[datetime] = None

    # 메타데이터
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def update_usage_stats(self, success: bool) -> None:
        """사용 통계 업데이트"""
        self.usage_count += 1
        self.total_requests += 1
        self.last_used_at = datetime.now()

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

    def get_success_rate(self) -> float:
        """성공률 계산"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    def is_healthy(self, min_success_rate: float = 0.8) -> bool:
        """계정 상태가 양호한지 확인"""
        return (
            self.is_active and
            self.status == AccountStatus.ACTIVE and
            self.get_success_rate() >= min_success_rate and
            (not self.token_info or not self.token_info.is_expired())
        )

    def update_token(self, token_info: TokenInfo) -> None:
        """토큰 정보 업데이트"""
        self.token_info = token_info
        self.updated_at = datetime.now()

    def update_credentials(self, api_credentials: ApiCredentials) -> None:
        """API 인증 정보 업데이트"""
        self.api_credentials = api_credentials
        self.updated_at = datetime.now()

    def mark_inactive(self) -> None:
        """계정 비활성화"""
        self.is_active = False
        self.status = AccountStatus.INACTIVE
        self.updated_at = datetime.now()

    def activate(self) -> None:
        """계정 활성화"""
        self.is_active = True
        self.status = AccountStatus.ACTIVE
        self.updated_at = datetime.now()

    def suspend(self) -> None:
        """계정 정지"""
        self.status = AccountStatus.SUSPENDED
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환 (직렬화용)"""
        return {
            'id': self.id,
            'account_type': self.account_type.value,
            'account_name': self.account_name,
            'username': self.username,
            'status': self.status.value,
            'is_active': self.is_active,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'usage_count': self.usage_count,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': self.get_success_rate(),
            'default_margin_rate': self.default_margin_rate,
            'sync_enabled': self.sync_enabled,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
