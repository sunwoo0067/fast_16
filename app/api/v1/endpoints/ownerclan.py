from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import json

from app.models.database import get_db
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

class ProductCollectionRequest(BaseModel):
    supplier_account_id: int = Field(..., description="공급사 계정 ID")
    limit: int = Field(10, description="수집할 상품 수", ge=1, le=100)

class CollectionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

@router.post("/collect-products", response_model=CollectionResponse)
async def collect_ownerclan_products(
    request: ProductCollectionRequest,
    db: AsyncSession = Depends(get_db)
):
    """OwnerClan에서 상품 데이터 수집 (더미 데이터)"""
    try:
        # 더미 상품 데이터 생성
        categories = ["전자제품", "의류", "도서", "스포츠", "뷰티", "식품"]
        dummy_products = []

        for i in range(min(request.limit, 10)):
            category = categories[i % len(categories)]
            base_price = (i + 1) * 1000

            dummy_product = {
                "item_key": f"OC_API_{i+1}",
                "name": f"{category} API상품 {i+1}",
                "price": base_price,
                "sale_price": int(base_price * 1.2),
                "stock_quantity": 50 + i * 5,
                "category_id": f"CAT_{i%5 + 1}",
                "category_name": category,
                "description": f"API를 통한 더미 상품 {i+1}입니다. {category} 카테고리의 테스트 상품입니다.",
                "images": json.dumps([f"https://dummyimage.com/300x300/000/fff&text=상품{i+1}"]),
                "options": json.dumps({"색상": ["블랙", "화이트"], "사이즈": ["S", "M", "L"]}),
                "is_active": True,
                "supplier_product_id": f"API_{i+1}",
                "supplier_name": "OwnerClan",
                "supplier_url": f"https://ownerclan.com/product/api_{i+1}",
                "supplier_image_url": f"https://dummyimage.com/300x300/000/fff&text=상품{i+1}",
                "estimated_shipping_days": 3,
                "manufacturer": "OwnerClan",
                "margin_rate": 0.3,
                "sync_status": "synced"
            }
            dummy_products.append(dummy_product)

        # 더미 데이터를 데이터베이스에 저장
        saved_count = 0
        for product_data in dummy_products:
            try:
                from app.models.database import Product
                new_product = Product(
                    supplier_id=request.supplier_account_id,
                    **product_data
                )
                db.add(new_product)
                saved_count += 1
            except Exception as e:
                logger.error(f"상품 저장 실패: {product_data.get('name', 'Unknown')} - {e}")

        await db.commit()

        return CollectionResponse(
            success=True,
            message=f"상품 수집 완료: {len(dummy_products)}개 수집, {saved_count}개 저장",
            data={
                "collected": len(dummy_products),
                "saved": saved_count,
                "supplier_account_id": request.supplier_account_id
            }
        )

    except Exception as e:
        logger.error(f"상품 수집 API 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"상품 수집 실패: {str(e)}"
        )

@router.get("/collection-stats/{supplier_account_id}", response_model=CollectionResponse)
async def get_collection_stats(
    supplier_account_id: int,
    db: AsyncSession = Depends(get_db)
):
    """OwnerClan 상품 수집 통계 조회"""
    try:
        from sqlalchemy import select
        from app.models.database import Product

        # 통계 조회
        result = await db.execute(
            select(Product).where(Product.supplier_id == supplier_account_id)
        )
        products = result.scalars().all()

        stats = {
            "total_products": len(products),
            "active_products": len([p for p in products if p.is_active]),
            "synced_products": len([p for p in products if p.sync_status == "synced"]),
            "last_sync": None
        }

        if products:
            last_updated = max((p.updated_at for p in products if p.updated_at), default=None)
            if last_updated:
                stats["last_sync"] = last_updated.isoformat()

        return CollectionResponse(
            success=True,
            message="통계 조회 완료",
            data=stats
        )

    except Exception as e:
        logger.error(f"통계 조회 API 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"통계 조회 실패: {str(e)}"
        )
