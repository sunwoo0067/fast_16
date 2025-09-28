"""시간 및 스케줄 포트 (인터페이스)"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional


class ClockPort(ABC):
    """시간 및 스케줄 인터페이스"""

    @abstractmethod
    def now(self) -> datetime:
        """현재 시간 반환"""
        pass

    @abstractmethod
    def today(self) -> datetime:
        """오늘 날짜 반환 (시간 00:00:00)"""
        pass

    @abstractmethod
    def add_days(self, days: int) -> datetime:
        """현재 시간에 일자 추가"""
        pass

    @abstractmethod
    def add_hours(self, hours: int) -> datetime:
        """현재 시간에 시간 추가"""
        pass

    @abstractmethod
    def is_expired(self, expire_at: datetime, buffer_minutes: int = 0) -> bool:
        """토큰/세션이 만료되었는지 확인"""
        pass

    @abstractmethod
    def sleep(self, seconds: float) -> None:
        """비동기 대기"""
        pass
