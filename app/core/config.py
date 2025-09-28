from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    """애플리케이션 설정"""

    # API 설정
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    debug: bool = False

    # 데이터베이스 설정
    database_url: str = "postgresql+asyncpg://postgres:12345678@localhost:5433/fast_15"

    # 상품 동기화 설정
    sync_batch_size: int = 50
    sync_max_workers: int = 5
    sync_retry_attempts: int = 3
    sync_timeout_seconds: int = 300

    # 쿠팡 API 설정
    coupang_api_timeout: int = 30
    coupang_rate_limit_per_minute: int = 100

    # 드랍싸핑 설정
    default_margin_rate: float = 0.3  # 30% 마진
    min_margin_rate: float = 0.1      # 최소 10% 마진
    max_shipping_days: int = 14       # 최대 배송일

    # OwnerClan API 설정
    ownerclan_api_url: str = "https://api.ownerclan.com/v1/graphql"
    ownerclan_auth_url: str = "https://auth.ownerclan.com/auth"

    # 로깅 설정
    log_level: str = "INFO"
    log_file_path: str = "logs/product_sync.log"

    # 보안 설정
    secret_key: str = "your-secret-key-change-this-in-production"

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """설정 인스턴스를 반환 (싱글톤)"""
    return Settings()

