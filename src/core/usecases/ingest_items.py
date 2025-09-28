"""상품 수집 유즈케이스"""
from typing import List, Optional
from datetime import datetime
import asyncio

from src.core.ports.supplier_port import SupplierPort, RawItemData
from src.core.ports.repo_port import RepositoryPort
from src.core.ports.clock_port import ClockPort
from src.core.entities.item import Item, PricePolicy, ItemOption
from src.core.entities.sync_history import (
    SyncHistory, SyncType, SyncStatus, SyncResult
)
from src.shared.result import Result, Success, Failure
from src.shared.logging import get_logger

logger = get_logger(__name__)


class IngestItemsUseCase:
    """상품 수집 유즈케이스"""

    def __init__(
        self,
        supplier_port: SupplierPort,
        repository: RepositoryPort,
        clock: ClockPort
    ):
        self.supplier_port = supplier_port
        self.repository = repository
        self.clock = clock

    async def execute(
        self,
        supplier_id: str,
        account_id: str,
        item_keys: Optional[List[str]] = None,
        max_concurrent: int = 5
    ) -> "Result[List[Item], str]":
        """상품 수집 실행"""
        sync_history = SyncHistory(
            id=f"ingest_{supplier_id}_{self.clock.now().isoformat()}",
            supplier_id=supplier_id,
            sync_type=SyncType.INGEST,
            status=SyncStatus.PENDING
        )

        try:
            # 동기화 이력 저장
            await self.repository.save_sync_history(sync_history)
            sync_history.start()

            # 상품 수집
            raw_items = await self.supplier_port.fetch_items(
                supplier_id, account_id, item_keys
            )

            if not raw_items:
                sync_history.complete(SyncResult())
                await self.repository.save_sync_history(sync_history)
                return Success([])

            # 병렬 처리로 상품 변환
            semaphore = asyncio.Semaphore(max_concurrent)
            tasks = [
                self._convert_raw_item(raw_item, semaphore)
                for raw_item in raw_items
            ]

            items = await asyncio.gather(*tasks, return_exceptions=True)

            # 예외 처리
            valid_items = []
            sync_result = SyncResult()

            for i, item_result in enumerate(items):
                if isinstance(item_result, Exception):
                    sync_result.add_failure(
                        raw_items[i].id,
                        str(item_result)
                    )
                else:
                    valid_items.append(item_result)
                    sync_result.add_success(raw_items[i].id)

            # 성공한 상품들 저장
            for item in valid_items:
                await self.repository.save_item(item)

            # 동기화 완료
            sync_history.complete(sync_result)
            await self.repository.save_sync_history(sync_history)

            if sync_result.failure_count > 0:
                failure_msg = f"일부 상품 수집 실패: {sync_result.failure_count}/{sync_result.total_count}"
                return Failure(failure_msg, valid_items)

            return Success(valid_items)

        except Exception as e:
            error_msg = f"상품 수집 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            sync_history.fail(error_msg)
            await self.repository.save_sync_history(sync_history)
            return Failure(error_msg)

    async def _convert_raw_item(
        self,
        raw_item: RawItemData,
        semaphore: asyncio.Semaphore
    ) -> Item:
        """원본 데이터를 도메인 엔티티로 변환"""
        async with semaphore:
            try:
                # 가격 정책 생성
                price_data = raw_item.price or {}
                price_policy = PricePolicy(
                    original_price=price_data.get("original", 0),
                    sale_price=price_data.get("sale"),
                    margin_rate=price_data.get("margin_rate", 0.3)
                )

                # 옵션 변환
                options = []
                for option_data in raw_item.options or []:
                    options.append(ItemOption(
                        name=option_data.get("name", ""),
                        value=option_data.get("value", ""),
                        price_adjustment=option_data.get("price_adjustment", 0),
                        stock_quantity=option_data.get("stock_quantity", 0)
                    ))

                # 도메인 엔티티 생성
                item = Item(
                    id=raw_item.id,
                    title=raw_item.title,
                    brand=raw_item.brand,
                    price=price_policy,
                    options=options,
                    images=raw_item.images,
                    category_id=raw_item.category,
                    supplier_id=raw_item.supplier_id,
                    description=raw_item.description,
                    normalized_at=self.clock.now()
                )

                return item

            except Exception as e:
                logger.error(f"상품 변환 실패 {raw_item.id}: {e}")
                raise
