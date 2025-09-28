"""상품 서비스 파사드"""
from typing import List, Optional
from datetime import datetime

from src.core.usecases.ingest_items import IngestItemsUseCase
from src.core.usecases.normalize_items import NormalizeItemsUseCase
from src.core.usecases.publish_to_market import PublishToMarketUseCase
from src.core.ports.repo_port import RepositoryPort
from src.core.ports.market_port import MarketType
from src.core.entities.item import Item
from src.presentation.schemas.items import (
    ProductListResponse,
    ProductResponse,
    ProductSyncResponse
)
from src.shared.result import Result, Success, Failure
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ItemService:
    """상품 서비스 파사드"""

    def __init__(
        self,
        ingest_usecase: IngestItemsUseCase,
        normalize_usecase: NormalizeItemsUseCase,
        publish_usecase: PublishToMarketUseCase,
        repository: RepositoryPort
    ):
        self.ingest_usecase = ingest_usecase
        self.normalize_usecase = normalize_usecase
        self.publish_usecase = publish_usecase
        self.repository = repository

    async def ingest_and_normalize(
        self,
        supplier_id: str,
        account_id: str,
        item_keys: Optional[List[str]] = None
    ) -> "Result[List[Item], str]":
        """상품 수집 후 즉시 정규화 (트랜잭션 경계)"""
        try:
            # 1. 상품 수집
            ingest_result = await self.ingest_usecase.execute(
                supplier_id=supplier_id,
                account_id=account_id,
                item_keys=item_keys
            )

            if ingest_result.is_failure():
                return Failure(f"상품 수집 실패: {ingest_result.get_error()}")

            collected_items = ingest_result.get_value()

            if not collected_items:
                return Success([])

            # 2. 수집된 상품 정규화
            item_ids = [item.id for item in collected_items]
            normalize_result = await self.normalize_usecase.execute(
                supplier_id=supplier_id,
                item_ids=item_ids
            )

            if normalize_result.is_failure():
                logger.warning(f"상품 정규화 실패: {normalize_result.get_error()}")
                # 수집은 성공했으므로 수집된 상품 반환
                return Success(collected_items)

            return Success(collected_items)

        except Exception as e:
            logger.error(f"상품 수집 및 정규화 중 오류: {e}")
            return Failure(f"처리 중 오류 발생: {str(e)}")

    async def get_products(
        self,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        sync_status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> ProductListResponse:
        """상품 목록 조회"""
        try:
            # TODO: 실제 리포지토리 구현 후 연결
            # 현재는 임시 구현
            items = await self.repository.get_items_by_supplier(
                supplier_id or "",
                limit=limit,
                offset=offset
            )

            # 필터링 (실제로는 리포지토리에서 처리)
            filtered_items = []
            for item in items:
                if category_id and item.category_id != category_id:
                    continue
                if is_active is not None and item.is_active != is_active:
                    continue
                if search and search.lower() not in item.title.lower():
                    continue
                filtered_items.append(item)

            total = len(filtered_items)
            paginated_items = filtered_items[offset:offset + limit]

            return ProductListResponse(
                items=[self._map_item_to_response(item) for item in paginated_items],
                total=total,
                page=offset // limit + 1,
                page_size=limit,
                has_next=offset + limit < total,
                has_prev=offset > 0
            )

        except Exception as e:
            logger.error(f"상품 목록 조회 중 오류: {e}")
            # 오류 시 빈 결과 반환
            return ProductListResponse(
                items=[],
                total=0,
                page=1,
                page_size=limit,
                has_next=False,
                has_prev=False
            )

    async def get_product(self, item_id: str) -> Optional[ProductResponse]:
        """상품 상세 조회"""
        try:
            item = await self.repository.get_item_by_id(item_id)
            if not item:
                return None

            return self._map_item_to_response(item)

        except Exception as e:
            logger.error(f"상품 조회 중 오류: {e}")
            return None

    async def sync_product_to_market(
        self,
        item_id: str,
        market_type: MarketType,
        account_name: str,
        dry_run: bool = False
    ) -> ProductSyncResponse:
        """단일 상품을 마켓에 동기화"""
        try:
            result = await self.publish_usecase.execute(
                market_type=market_type,
                item_ids=[item_id],
                account_name=account_name,
                dry_run=dry_run
            )

            if result.is_success():
                upload_results = result.get_value()
                success_count = sum(1 for r in upload_results if r.get('success', False))
                failure_count = len(upload_results) - success_count

                return ProductSyncResponse(
                    success=failure_count == 0,
                    message=f"동기화 완료: 성공 {success_count}, 실패 {failure_count}",
                    processed_count=len(upload_results),
                    success_count=success_count,
                    failure_count=failure_count,
                    errors=[r for r in upload_results if not r.get('success', False)]
                )
            else:
                return ProductSyncResponse(
                    success=False,
                    message=result.get_error(),
                    processed_count=0,
                    success_count=0,
                    failure_count=0
                )

        except Exception as e:
            logger.error(f"상품 마켓 동기화 중 오류: {e}")
            return ProductSyncResponse(
                success=False,
                message=f"동기화 중 오류 발생: {str(e)}",
                processed_count=0,
                success_count=0,
                failure_count=0
            )

    def _map_item_to_response(self, item: Item) -> ProductResponse:
        """도메인 엔티티를 응답 DTO로 매핑"""
        return ProductResponse(
            id=item.id,
            supplier_id=item.supplier_id,
            supplier_account_id="",  # TODO: 실제 구현 시 매핑
            item_key=item.id,
            name=item.title,
            price=item.price.get_final_price(),
            sale_price=item.price.sale_price,
            margin_rate=item.price.margin_rate,
            stock_quantity=item.stock_quantity,
            max_stock_quantity=item.max_stock_quantity,
            supplier_product_id=None,  # TODO: 실제 구현 시 매핑
            supplier_name="",  # TODO: 실제 구현 시 매핑
            supplier_url=None,
            supplier_image_url=None,
            estimated_shipping_days=item.estimated_shipping_days,
            is_active=item.is_active,
            sync_status="synced",  # TODO: 실제 구현 시 매핑
            last_synced_at=datetime.now(),  # TODO: 실제 구현 시 매핑
            sync_error_message=None,
            category_id=item.category_id,
            category_name=None,  # TODO: 실제 구현 시 매핑
            created_at=datetime.now(),  # TODO: 실제 구현 시 매핑
            updated_at=datetime.now()   # TODO: 실제 구현 시 매핑
        )
