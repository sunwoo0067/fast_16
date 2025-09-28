"""토큰 저장소 어댑터"""
from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass

from src.core.entities.account import TokenInfo, Account, AccountType
from src.core.ports.repo_port import RepositoryPort
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TokenRefreshPolicy:
    """토큰 갱신 정책"""
    buffer_hours: int = 3  # 만료 3시간 전부터 갱신
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 1.0


class TokenStore:
    """토큰 저장 및 관리"""

    def __init__(
        self,
        repository: RepositoryPort,
        refresh_policy: TokenRefreshPolicy = None
    ):
        self.repository = repository
        self.refresh_policy = refresh_policy or TokenRefreshPolicy()
        self._token_cache: Dict[str, TokenInfo] = {}
        self._cache_lock = asyncio.Lock()

    async def get_token(self, account: Account) -> Optional[TokenInfo]:
        """계정의 유효한 토큰 조회"""
        cache_key = f"{account.account_type.value}:{account.id}"

        # 캐시 확인
        async with self._cache_lock:
            if cache_key in self._token_cache:
                cached_token = self._token_cache[cache_key]
                if not cached_token.is_expired():
                    return cached_token

        # 리포지토리에서 토큰 정보 조회
        if account.token_info and not account.token_info.is_expired():
            async with self._cache_lock:
                self._token_cache[cache_key] = account.token_info
            return account.token_info

        return None

    async def save_token(self, account: Account, token_info: TokenInfo) -> None:
        """토큰 저장"""
        account.update_token(token_info)

        # 리포지토리에 저장
        await self.repository.save_supplier_account(account) if account.account_type == AccountType.SUPPLIER else None

        # 캐시에 저장
        cache_key = f"{account.account_type.value}:{account.id}"
        async with self._cache_lock:
            self._token_cache[cache_key] = token_info

        logger.info(f"토큰 저장 완료: {account.account_name}")

    async def refresh_token_if_needed(
        self,
        account: Account,
        token_refresher
    ) -> Optional[TokenInfo]:
        """토큰 갱신 필요시 자동 갱신"""
        current_token = await self.get_token(account)

        if not current_token or current_token.needs_refresh(self.refresh_policy.buffer_hours):
            try:
                logger.info(f"토큰 갱신 시작: {account.account_name}")
                new_token = await self._refresh_token_with_retry(account, token_refresher)
                if new_token:
                    await self.save_token(account, new_token)
                    return new_token
            except Exception as e:
                logger.error(f"토큰 갱신 실패: {account.account_name} - {e}")

        return current_token

    async def _refresh_token_with_retry(
        self,
        account: Account,
        token_refresher
    ) -> Optional[TokenInfo]:
        """재시도 로직과 함께 토큰 갱신"""
        for attempt in range(self.refresh_policy.max_retry_attempts):
            try:
                return await token_refresher(account)
            except Exception as e:
                if attempt < self.refresh_policy.max_retry_attempts - 1:
                    logger.warning(f"토큰 갱신 재시도 {attempt + 1}: {account.account_name} - {e}")
                    await asyncio.sleep(self.refresh_policy.retry_delay_seconds * (2 ** attempt))
                else:
                    logger.error(f"토큰 갱신 최종 실패: {account.account_name} - {e}")

        return None

    async def invalidate_token(self, account: Account) -> None:
        """토큰 무효화"""
        cache_key = f"{account.account_type.value}:{account.id}"

        async with self._cache_lock:
            self._token_cache.pop(cache_key, None)

        # 만료된 토큰 정보로 업데이트
        expired_token = TokenInfo(
            access_token="",
            expires_at=datetime.now() - timedelta(hours=1)
        )
        await self.save_token(account, expired_token)

        logger.info(f"토큰 무효화 완료: {account.account_name}")

    async def cleanup_expired_tokens(self) -> int:
        """만료된 토큰 정리"""
        cleaned_count = 0

        async with self._cache_lock:
            expired_keys = []
            for cache_key, token_info in self._token_cache.items():
                if token_info.is_expired():
                    expired_keys.append(cache_key)

            for key in expired_keys:
                self._token_cache.pop(key, None)
                cleaned_count += 1

        if cleaned_count > 0:
            logger.info(f"만료된 토큰 정리 완료: {cleaned_count}개")

        return cleaned_count
