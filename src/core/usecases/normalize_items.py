"""상품 정규화 유즈케이스"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

from src.core.ports.repo_port import RepositoryPort
from src.core.ports.clock_port import ClockPort
from src.core.entities.item import Item
from src.core.entities.sync_history import (
    SyncHistory, SyncType, SyncStatus, SyncResult
)
from src.shared.result import Result, Success, Failure
from src.shared.logging import get_logger

logger = get_logger(__name__)


class NormalizationRule:
    """상품 정규화 규칙"""

    @staticmethod
    def normalize_title(title: str) -> str:
        """상품명 정규화"""
        # 불필요한 공백 제거
        title = re.sub(r'\s+', ' ', title.strip())

        # 특수 문자 정리
        title = re.sub(r'[^\w\s가-힣()\[\]\/\-\+\.]', '', title)

        return title

    @staticmethod
    def normalize_brand(brand: str) -> str:
        """브랜드명 정규화"""
        if not brand:
            return "기타"

        # 대소문자 통일 및 공백 정리
        brand = brand.strip().upper()

        # 주요 브랜드명 매핑
        brand_mapping = {
            'SAMSUNG': '삼성전자',
            'LG': 'LG전자',
            'APPLE': '애플',
            'SONY': '소니'
        }

        return brand_mapping.get(brand, brand)

    @staticmethod
    def extract_category_from_title(title: str) -> str:
        """상품명에서 카테고리 추출"""
        # 키워드 기반 카테고리 매핑
        category_keywords = {
            '의류': ['의류', '옷', '셔츠', '바지', '드레스', '상의', '하의'],
            '전자제품': ['전자', '휴대폰', '컴퓨터', '노트북', '태블릿'],
            '가구': ['가구', '소파', '침대', '책상', '의자'],
            '도서': ['도서', '책', '서적', '만화', '잡지']
        }

        title_lower = title.lower()

        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in title_lower:
                    return category

        return "기타"

    @staticmethod
    def calculate_margin_rate(price: int, cost_price: int) -> float:
        """마진율 계산"""
        if cost_price <= 0:
            return 0.3  # 기본 마진율

        return (price - cost_price) / cost_price


class NormalizeItemsUseCase:
    """상품 정규화 유즈케이스"""

    def __init__(
        self,
        repository: RepositoryPort,
        clock: ClockPort
    ):
        self.repository = repository
        self.clock = clock

    async def execute(
        self,
        supplier_id: Optional[str] = None,
        item_ids: Optional[List[str]] = None,
        batch_size: int = 100
    ) -> "Result[List[Item], str]":
        """상품 정규화 실행"""
        sync_history = SyncHistory(
            id=f"normalize_{self.clock.now().isoformat()}",
            supplier_id=supplier_id,
            sync_type=SyncType.NORMALIZE,
            status=SyncStatus.PENDING
        )

        try:
            # 동기화 이력 저장
            await self.repository.save_sync_history(sync_history)
            sync_history.start()

            # 상품 조회
            if item_ids:
                # 특정 상품들만 정규화
                items = []
                for item_id in item_ids:
                    item = await self.repository.get_item_by_id(item_id)
                    if item:
                        items.append(item)
            else:
                # 공급사별 모든 상품 조회
                all_items = []
                offset = 0

                while True:
                    batch = await self.repository.get_items_by_supplier(
                        supplier_id or "",
                        limit=batch_size,
                        offset=offset
                    )
                    if not batch:
                        break
                    all_items.extend(batch)
                    offset += batch_size

                items = all_items

            if not items:
                sync_history.complete(SyncResult())
                await self.repository.save_sync_history(sync_history)
                return Success([])

            # 상품 정규화
            normalized_items = []
            sync_result = SyncResult()

            for item in items:
                try:
                    normalized_item = await self._normalize_item(item)
                    normalized_items.append(normalized_item)
                    sync_result.add_success(item.id)

                    # 변경사항 저장
                    await self.repository.update_item(item.id, {
                        'title': normalized_item.title,
                        'brand': normalized_item.brand,
                        'category_id': normalized_item.category_id,
                        'normalized_at': self.clock.now()
                    })

                except Exception as e:
                    logger.error(f"상품 정규화 실패 {item.id}: {e}")
                    sync_result.add_failure(item.id, str(e))

            # 동기화 완료
            sync_history.complete(sync_result)
            await self.repository.save_sync_history(sync_history)

            if sync_result.failure_count > 0:
                failure_msg = f"일부 상품 정규화 실패: {sync_result.failure_count}/{sync_result.total_count}"
                return Failure(failure_msg, normalized_items)

            return Success(normalized_items)

        except Exception as e:
            error_msg = f"상품 정규화 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            sync_history.fail(error_msg)
            await self.repository.save_sync_history(sync_history)
            return Failure(error_msg)

    async def _normalize_item(self, item: Item) -> Item:
        """개별 상품 정규화"""
        # 제목 정규화
        normalized_title = NormalizationRule.normalize_title(item.title)

        # 브랜드 정규화
        normalized_brand = NormalizationRule.normalize_brand(item.brand)

        # 카테고리 추출/정규화
        if not item.category_id or item.category_id == "기타":
            extracted_category = NormalizationRule.extract_category_from_title(normalized_title)
            normalized_category = extracted_category
        else:
            normalized_category = item.category_id

        # 마진율 재계산 (필요시)
        if item.price.margin_rate < 0.1:  # 마진율이 너무 낮은 경우
            # 공급가 추정 (원가의 70%로 가정)
            estimated_cost = int(item.price.original_price * 0.7)
            new_margin_rate = NormalizationRule.calculate_margin_rate(
                item.price.original_price,
                estimated_cost
            )
            # 새로운 가격 정책 생성
            new_price = item.price
            new_price.margin_rate = new_margin_rate
        else:
            new_price = item.price

        # 정규화된 상품 반환
        return Item(
            id=item.id,
            title=normalized_title,
            brand=normalized_brand,
            price=new_price,
            options=item.options,
            images=item.images,
            category_id=normalized_category,
            supplier_id=item.supplier_id,
            description=item.description,
            manufacturer=item.manufacturer,
            model=item.model,
            estimated_shipping_days=item.estimated_shipping_days,
            stock_quantity=item.stock_quantity,
            max_stock_quantity=item.max_stock_quantity,
            is_active=item.is_active,
            normalized_at=self.clock.now(),
            hash_key=item.hash_key
        )
