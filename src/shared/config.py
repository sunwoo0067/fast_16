"""애플리케이션 설정"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # 데이터베이스
    database_url: str = Field(default="sqlite:///./dropshipping.db")

    # 로깅
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # API 설정
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=False)

    # 공급사 설정
    ownerclan_api_url: str = Field(default="https://api.ownerclan.com/graphql")
    ownerclan_auth_url: str = Field(default="https://api.ownerclan.com/auth")

    # 마켓 설정
    coupang_api_url: str = Field(default="https://api-gateway.coupang.com")

    # 동기화 설정
    max_concurrent_requests: int = Field(default=5)
    request_timeout: int = Field(default=30)
    max_retries: int = Field(default=3)

    # 토큰 갱신 설정
    token_refresh_buffer_hours: int = Field(default=3)
    token_cleanup_interval_hours: int = Field(default=24)

    # 비즈니스 규칙
    default_margin_rate: float = Field(default=0.3)
    min_margin_rate: float = Field(default=0.1)
    max_stock_quantity: int = Field(default=999)

    # Alembic에서 사용할 때는 .env 파일을 읽지 않도록 설정
    class Config:
        # .env 파일이 있는 경우에만 읽기
        env_file = ".env" if os.path.exists(".env") else None
        case_sensitive = False


# 전역 설정 인스턴스
settings = Settings()


def get_settings() -> Settings:
    """설정 인스턴스 반환"""
    return settings
