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
    """OwnerClan에서 실제 상품 데이터 수집"""
    try:
        from app.services.ownerclan_collector import OwnerClanCollector
        
        # OwnerClanCollector를 사용하여 실제 API 호출
        collector = OwnerClanCollector(db)
        result = await collector.collect_products(
            supplier_account_id=request.supplier_account_id,
            limit=request.limit
        )

        if result.get("success", False):
            return CollectionResponse(
                success=True,
                message=f"상품 수집 완료: {result.get('collected', 0)}개 수집, {result.get('saved', 0)}개 저장",
                data={
                    "collected": result.get("collected", 0),
                    "saved": result.get("saved", 0),
                    "supplier_account_id": request.supplier_account_id
                }
            )
        else:
            return CollectionResponse(
                success=False,
                message=f"상품 수집 실패: {result.get('error', '알 수 없는 오류')}",
                data={
                    "collected": 0,
                    "saved": 0,
                    "supplier_account_id": request.supplier_account_id,
                    "error": result.get("error", "알 수 없는 오류")
                }
            )

    except Exception as e:
        logger.error(f"상품 수집 API 실패: {e}")
        return CollectionResponse(
            success=False,
            message=f"상품 수집 실패: {str(e)}",
            data={
                "collected": 0,
                "saved": 0,
                "supplier_account_id": request.supplier_account_id,
                "error": str(e)
            }
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
