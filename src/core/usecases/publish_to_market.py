"""마켓 업로드 유즈케이스"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.core.ports.market_port import MarketPort, MarketCredentials, MarketProduct, MarketType
from src.core.ports.repo_port import RepositoryPort
from src.core.ports.clock_port import ClockPort
from src.core.entities.item import Item
from src.core.entities.sync_history import (
    SyncHistory, SyncType, SyncStatus, SyncResult
)
from src.core.entities.account import Account, AccountType
from src.shared.result import Result, Success, Failure
from src.shared.logging import get_logger

logger = get_logger(__name__)


class PublishToMarketUseCase:
    """마켓 업로드 유즈케이스"""

    def __init__(
        self,
        market_port: MarketPort,
        repository: RepositoryPort,
        clock: ClockPort
    ):
        self.market_port = market_port
        self.repository = repository
        self.clock = clock

    async def execute(
        self,
        market_type: MarketType,
        item_ids: List[str],
        account_name: str,
        dry_run: bool = False
    ) -> "Result[List[Dict[str, Any]], str]":
        """마켓 업로드 실행"""
        sync_history = SyncHistory(
            id=f"upload_{market_type.value}_{self.clock.now().isoformat()}",
            market_type=market_type.value,
            sync_type=SyncType.UPLOAD,
            status=SyncStatus.PENDING
        )

        try:
            # 동기화 이력 저장
            await self.repository.save_sync_history(sync_history)
            sync_history.start()

            # 마켓 계정 조회
            account = await self.repository.get_market_account(
                market_type.value,
                account_name
            )

            if not account:
                error_msg = f"마켓 계정을 찾을 수 없습니다: {market_type.value}/{account_name}"
                sync_history.fail(error_msg)
                await self.repository.save_sync_history(sync_history)
                return Failure(error_msg)

            if not account.is_healthy():
                error_msg = f"마켓 계정 상태가 양호하지 않습니다: {account.account_name}"
                sync_history.fail(error_msg)
                await self.repository.save_sync_history(sync_history)
                return Failure(error_msg)

            # 상품 조회 및 마켓 상품으로 변환
            market_products = []
            for item_id in item_ids:
                item = await self.repository.get_item_by_id(item_id)
                if not item:
                    continue

                market_product = self._convert_to_market_product(item)
                if market_product:
                    market_products.append((item, market_product))

            if not market_products:
                sync_history.complete(SyncResult())
                await self.repository.save_sync_history(sync_history)
                return Success([])

            # 마켓 업로드
            upload_results = []
            sync_result = SyncResult()

            for item, market_product in market_products:
                try:
                    if dry_run:
                        # 드라이런 모드
                        upload_results.append({
                            'item_id': item.id,
                            'success': True,
                            'dry_run': True,
                            'message': '드라이런 모드'
                        })
                        sync_result.add_success(item.id)
                    else:
                        # 실제 업로드
                        result = await self.market_port.upload_product(
                            self._build_credentials(account),
                            market_product
                        )

                        if result.success:
                            # 업로드 성공 - 동기화 상태 업데이트
                            await self.repository.update_item(item.id, {
                                'last_synced_at': self.clock.now()
                            })

                            upload_results.append({
                                'item_id': item.id,
                                'success': True,
                                'product_id': result.product_id,
                                'channel_product_no': result.channel_product_no
                            })
                            sync_result.add_success(item.id)
                        else:
                            upload_results.append({
                                'item_id': item.id,
                                'success': False,
                                'error_message': result.error_message
                            })
                            sync_result.add_failure(item.id, result.error_message or "업로드 실패")

                except Exception as e:
                    logger.error(f"상품 업로드 실패 {item.id}: {e}")
                    upload_results.append({
                        'item_id': item.id,
                        'success': False,
                        'error_message': str(e)
                    })
                    sync_result.add_failure(item.id, str(e))

            # 동기화 완료
            sync_history.complete(sync_result)
            await self.repository.save_sync_history(sync_history)

            # 계정 사용 통계 업데이트
            account.update_usage_stats(sync_result.is_successful())
            await self.repository.save_market_account(account)

            if sync_result.failure_count > 0:
                failure_msg = f"일부 상품 업로드 실패: {sync_result.failure_count}/{sync_result.total_count}"
                return Failure(failure_msg, upload_results)

            return Success(upload_results)

        except Exception as e:
            error_msg = f"마켓 업로드 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            sync_history.fail(error_msg)
            await self.repository.save_sync_history(sync_history)
            return Failure(error_msg)

    def _convert_to_market_product(self, item: Item) -> Optional[MarketProduct]:
        """도메인 상품을 마켓 상품으로 변환"""
        try:
            # 마켓별 요구사항에 맞는 상품 변환
            # 여기서는 일반적인 변환 로직

            # 필수 필드 검증
            if not item.title or not item.images:
                logger.warning(f"상품 필수 필드 누락: {item.id}")
                return None

            # 마켓별 속성 매핑
            attributes = {
                'brand': item.brand,
                'model': item.model or '',
                'manufacturer': item.manufacturer or '',
            }

            return MarketProduct(
                id=item.id,
                title=item.title,
                price=int(item.price.get_final_price()),
                stock=item.stock_quantity,
                images=item.images,
                category_id=item.category_id,
                attributes=attributes,
                description=item.description
            )

        except Exception as e:
            logger.error(f"마켓 상품 변환 실패 {item.id}: {e}")
            return None

    def _build_credentials(self, account: Account) -> MarketCredentials:
        """계정 정보를 마켓 인증 정보로 변환"""
        return MarketCredentials(
            market=MarketType(account.account_name),  # 실제로는 계정에서 마켓 타입 정보가 있어야 함
            account_id=account.id,
            api_key=account.api_credentials.api_key if account.api_credentials else "",
            api_secret=account.api_credentials.api_secret if account.api_credentials else "",
            vendor_id=account.api_credentials.vendor_id if account.api_credentials else None
        )
