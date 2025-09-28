"""상품 관련 라우트"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from src.app.di import get_ingest_items_usecase, get_normalize_items_usecase
from src.core.usecases.ingest_items import IngestItemsUseCase
from src.core.usecases.normalize_items import NormalizeItemsUseCase
from src.shared.result import Result, Success, Failure
from src.shared.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/ingest/{supplier_id}")
async def ingest_items(
    supplier_id: str,
    account_id: str,
    item_keys: Optional[List[str]] = None,
    usecase: IngestItemsUseCase = Depends(get_ingest_items_usecase)
):
    """상품 수집"""
    try:
        result = await usecase.execute(supplier_id, account_id, item_keys)

        if result.is_success():
            return {
                "success": True,
                "message": f"상품 수집 완료: {len(result.get_value())}개",
                "items": result.get_value()
            }
        else:
            return {
                "success": False,
                "message": result.get_error(),
                "items": result.get_value() or []
            }

    except Exception as e:
        logger.error(f"상품 수집 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/normalize")
async def normalize_items(
    supplier_id: Optional[str] = None,
    item_ids: Optional[List[str]] = None,
    usecase: NormalizeItemsUseCase = Depends(get_normalize_items_usecase)
):
    """상품 정규화"""
    try:
        result = await usecase.execute(supplier_id, item_ids)

        if result.is_success():
            return {
                "success": True,
                "message": f"상품 정규화 완료: {len(result.get_value())}개",
                "items": result.get_value()
            }
        else:
            return {
                "success": False,
                "message": result.get_error(),
                "items": result.get_value() or []
            }

    except Exception as e:
        logger.error(f"상품 정규화 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/items")
async def get_items(
    supplier_id: Optional[str] = None,
    category_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """상품 목록 조회"""
    # 실제 구현에서는 리포지토리에서 조회
    return {
        "items": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    }


@router.get("/items/{item_id}")
async def get_item(item_id: str):
    """상품 상세 조회"""
    # 실제 구현에서는 리포지토리에서 조회
    return {"item": None}
