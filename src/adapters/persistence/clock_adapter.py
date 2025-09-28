"""시간 어댑터"""
from datetime import datetime, timedelta
import asyncio

from src.core.ports.clock_port import ClockPort


class ClockAdapter(ClockPort):
    """시간 어댑터 구현체"""

    def now(self) -> datetime:
        """현재 시간 반환"""
        return datetime.now()

    def today(self) -> datetime:
        """오늘 날짜 반환 (시간 00:00:00)"""
        now = datetime.now()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    def add_days(self, days: int) -> datetime:
        """현재 시간에 일자 추가"""
        return datetime.now() + timedelta(days=days)

    def add_hours(self, hours: int) -> datetime:
        """현재 시간에 시간 추가"""
        return datetime.now() + timedelta(hours=hours)

    def is_expired(self, expire_at: datetime, buffer_minutes: int = 0) -> bool:
        """토큰/세션이 만료되었는지 확인"""
        if not expire_at:
            return False
        return datetime.now() + timedelta(minutes=buffer_minutes) >= expire_at

    def sleep(self, seconds: float) -> None:
        """비동기 대기"""
        asyncio.sleep(seconds)
