from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json

from app.models.database import Product, ProductSyncHistory
from app.core.logging import get_logger, LoggerMixin, log_product_sync
from app.core.exceptions import ProductSyncError, ValidationError

logger = get_logger(__name__)

class ProductService(LoggerMixin):
    """상품 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_products(
        self,
        supplier_id: Optional[int] = None,
        category_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        sync_status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Product]:
        """상품 목록 조회"""
        query = select(Product)

        # 필터링 조건들
        if supplier_id is not None:
            query = query.where(Product.supplier_id == supplier_id)
        if category_id is not None:
            query = query.where(Product.category_id == category_id)
        if is_active is not None:
            query = query.where(Product.is_active == is_active)
        if sync_status is not None:
            query = query.where(Product.sync_status == sync_status)
        if search:
            # 상품명 검색
            query = query.where(Product.name.contains(search))

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_product_by_id(self, product_id: int) -> Optional[Product]:
        """ID로 상품 조회"""
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_product_by_item_key(self, item_key: str, supplier_id: int) -> Optional[Product]:
        """상품 키와 공급사 ID로 상품 조회"""
        result = await self.db.execute(
            select(Product).where(
                and_(
                    Product.item_key == item_key,
                    Product.supplier_id == supplier_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_product(
        self,
        supplier_id: int,
        supplier_account_id: int,
        item_key: str,
        name: str,
        price: int,
        **kwargs
    ) -> Product:
        """상품 생성"""
        # 상품 데이터 구성
        product_data = {
            "supplier_id": supplier_id,
            "supplier_account_id": supplier_account_id,
            "item_key": item_key,
            "name": name,
            "price": price,
            **kwargs
        }

        # 데이터 검증
        from app.utils.validation import ProductValidator, ValidationUtils
        validated_data = ProductValidator.validate_product_data(product_data)

        # 마진율 정규화
        if "margin_rate" in validated_data:
            validated_data["margin_rate"] = ValidationUtils.normalize_margin_rate(
                validated_data["margin_rate"]
            )

        # 중복 체크
        existing = await self.get_product_by_item_key(item_key, supplier_id)
        if existing:
            raise ValidationError(f"이미 존재하는 상품입니다: {item_key}")

        # 검증된 데이터에서 값 추출
        sale_price = validated_data.get('sale_price', price)
        margin_rate = validated_data.get('margin_rate', 0.3)
        stock_quantity = validated_data.get('stock_quantity', 0)
        max_stock_quantity = validated_data.get('max_stock_quantity', None)

        # 드랍싸핑 특화 필드들
        supplier_product_id = validated_data.get('supplier_product_id')
        supplier_name = validated_data.get('supplier_name')
        supplier_url = validated_data.get('supplier_url')
        supplier_image_url = validated_data.get('supplier_image_url')
        estimated_shipping_days = validated_data.get('estimated_shipping_days', 7)

        # 카테고리 정보
        category_id = validated_data.get('category_id')
        category_name = validated_data.get('category_name')

        # 상품 설명 및 이미지
        description = validated_data.get('description')
        images = validated_data.get('images', [])
        options = validated_data.get('options', {})

        # 쿠팡 상품 정보
        coupang_product_id = validated_data.get('coupang_product_id')
        coupang_status = validated_data.get('coupang_status')
        coupang_category_id = validated_data.get('coupang_category_id')
        manufacturer = validated_data.get('manufacturer')

        new_product = Product(
            supplier_id=supplier_id,
            supplier_account_id=supplier_account_id,
            item_key=item_key,
            name=name,
            price=price,
            sale_price=sale_price,
            margin_rate=margin_rate,
            stock_quantity=stock_quantity,
            max_stock_quantity=max_stock_quantity,
            supplier_product_id=supplier_product_id,
            supplier_name=supplier_name,
            supplier_url=supplier_url,
            supplier_image_url=supplier_image_url,
            estimated_shipping_days=estimated_shipping_days,
            category_id=category_id,
            category_name=category_name,
            description=description,
            images=json.dumps(images) if images else None,
            options=json.dumps(options) if options else None,
            coupang_product_id=coupang_product_id,
            coupang_status=coupang_status,
            coupang_category_id=coupang_category_id,
            manufacturer=manufacturer,
            is_active=True,
            sync_status="pending"
        )

        self.db.add(new_product)
        await self.db.commit()
        await self.db.refresh(new_product)

        # 동기화 이력 기록
        await self._record_sync_history(
            supplier_id=supplier_id,
            product_id=new_product.id,
            sync_type="create",
            status="success"
        )

        log_product_sync(
            product_data={
                "item_key": item_key,
                "name": name,
                "supplier_id": supplier_id
            },
            action="create",
            success=True
        )

        self.logger.info(f"상품 생성 완료: {name} ({item_key})")
        return new_product

    async def update_product(
        self,
        product_id: int,
        **kwargs
    ) -> Optional[Product]:
        """상품 정보 수정"""
        product = await self.get_product_by_id(product_id)
        if not product:
            return None

        # 이전 데이터 백업
        old_data = {
            "name": product.name,
            "price": product.price,
            "sale_price": product.sale_price,
            "stock_quantity": product.stock_quantity
        }

        # 업데이트할 필드들
        update_data = {}
        for field, value in kwargs.items():
            if value is not None and hasattr(product, field):
                update_data[field] = value

        update_data['updated_at'] = datetime.now()

        # 업데이트 실행
        await self.db.execute(
            update(Product).where(Product.id == product_id).values(**update_data)
        )
        await self.db.commit()

        # 업데이트된 상품 조회
        await self.db.refresh(product)

        # 동기화 이력 기록
        await self._record_sync_history(
            supplier_id=product.supplier_id,
            product_id=product_id,
            sync_type="update",
            status="success",
            old_data=old_data
        )

        log_product_sync(
            product_data={
                "item_key": product.item_key,
                "name": product.name,
                "supplier_id": product.supplier_id
            },
            action="update",
            success=True
        )

        self.logger.info(f"상품 수정 완료: {product.name} ({product.item_key})")
        return product

    async def get_product_stats(self, supplier_id: int) -> Dict[str, Any]:
        """공급사의 상품 통계 조회"""
        # 총 상품 수
        total_result = await self.db.execute(
            select(func.count(Product.id)).where(Product.supplier_id == supplier_id)
        )
        total_products = total_result.scalar()

        # 활성 상품 수
        active_result = await self.db.execute(
            select(func.count(Product.id)).where(
                and_(
                    Product.supplier_id == supplier_id,
                    Product.is_active == True
                )
            )
        )
        active_products = active_result.scalar()

        # 동기화 상태별 개수
        sync_status_counts = {}
        for status in ['pending', 'synced', 'failed']:
            result = await self.db.execute(
                select(func.count(Product.id)).where(
                    and_(
                        Product.supplier_id == supplier_id,
                        Product.sync_status == status
                    )
                )
            )
            sync_status_counts[status] = result.scalar()

        # 카테고리별 개수 (상위 10개)
        category_stats = []
        category_result = await self.db.execute(
            select(
                Product.category_name,
                func.count(Product.id).label('count')
            ).where(
                and_(
                    Product.supplier_id == supplier_id,
                    Product.category_name.isnot(None)
                )
            ).group_by(Product.category_name).order_by(func.count(Product.id).desc()).limit(10)
        )
        for category_name, count in category_result:
            category_stats.append({
                "category_name": category_name,
                "count": count
            })

        return {
            "supplier_id": supplier_id,
            "total_products": total_products,
            "active_products": active_products,
            "sync_status": sync_status_counts,
            "top_categories": category_stats
        }

    async def get_sync_history(
        self,
        supplier_id: int,
        product_id: Optional[int] = None,
        sync_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """동기화 이력 조회"""
        query = select(ProductSyncHistory).where(
            ProductSyncHistory.supplier_id == supplier_id
        )

        if product_id is not None:
            query = query.where(ProductSyncHistory.product_id == product_id)
        if sync_type is not None:
            query = query.where(ProductSyncHistory.sync_type == sync_type)
        if status is not None:
            query = query.where(ProductSyncHistory.status == status)

        query = query.order_by(ProductSyncHistory.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        history_records = result.scalars().all()

        return {
            "supplier_id": supplier_id,
            "history": [
                {
                    "id": record.id,
                    "product_id": record.product_id,
                    "sync_type": record.sync_type,
                    "status": record.status,
                    "error_message": record.error_message,
                    "sync_duration_ms": record.sync_duration_ms,
                    "created_at": record.created_at.isoformat()
                }
                for record in history_records
            ]
        }

    async def _record_sync_history(
        self,
        supplier_id: int,
        product_id: int,
        sync_type: str,
        status: str,
        old_data: Optional[Dict] = None,
        new_data: Optional[Dict] = None,
        error_message: Optional[str] = None,
        sync_duration_ms: Optional[int] = None
    ):
        """동기화 이력 기록"""
        history_record = ProductSyncHistory(
            supplier_id=supplier_id,
            product_id=product_id,
            sync_type=sync_type,
            status=status,
            old_data=json.dumps(old_data) if old_data else None,
            new_data=json.dumps(new_data) if new_data else None,
            error_message=error_message,
            sync_duration_ms=sync_duration_ms
        )

        self.db.add(history_record)
        await self.db.commit()

class ProductSyncService(LoggerMixin):
    """상품 동기화 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.batch_size = 50

    async def bulk_create_products(self, products_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """대량 상품 등록"""
        results = {
            "success": 0,
            "failed": 0,
            "errors": []
        }

        # 배치로 나누어 처리
        batches = [products_data[i:i + self.batch_size]
                  for i in range(0, len(products_data), self.batch_size)]

        product_service = ProductService(self.db)

        for batch in batches:
            try:
                # 각 상품 검증 및 생성
                for product_data in batch:
                    try:
                        await product_service.create_product(**product_data)
                        results["success"] += 1
                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append({
                            "product": product_data.get("name", "Unknown"),
                            "error": str(e)
                        })

            except Exception as e:
                results["failed"] += len(batch)
                results["errors"].append({
                    "batch": "all",
                    "error": str(e)
                })

        return results

    async def get_active_suppliers(self) -> List[Dict[str, Any]]:
        """활성 공급사 목록 조회"""
        from app.models.database import Supplier
        
        query = select(Supplier).where(Supplier.is_active == True)
        result = await self.db.execute(query)
        suppliers = result.scalars().all()
        
        return [
            {
                "id": supplier.id,
                "name": supplier.name,
                "description": supplier.description,
                "api_key": supplier.api_key,
                "base_url": supplier.base_url
            }
            for supplier in suppliers
        ]

    async def collect_products(
        self,
        supplier_id: int,
        supplier_account_id: Optional[int] = None,
        item_keys: Optional[List[str]] = None,
        force_sync: bool = False
    ) -> Dict[str, Any]:
        """상품 수집 (OwnerClan API 연동)"""
        try:
            # OwnerClanCollector를 사용하여 상품 수집
            from app.services.ownerclan_collector import OwnerClanCollector
            
            collector = OwnerClanCollector(self.db)
            result = await collector.collect_products(
                supplier_id=supplier_id,
                supplier_account_id=supplier_account_id,
                count=50  # 기본 수집 개수
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"상품 수집 실패: {e}")
            return {
                "total_products": 0,
                "new_products": 0,
                "updated_products": 0,
                "errors": [str(e)],
                "duration_ms": 0
            }


