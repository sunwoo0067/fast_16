"""
재고 관리 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.database import get_async_session_factory
from app.services.inventory_service import InventoryService
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ===== Pydantic 모델 =====

class InventoryResponse(BaseModel):
    id: str
    product_id: str
    supplier_id: Optional[str]
    available_quantity: int
    reserved_quantity: int
    total_quantity: int
    low_stock_threshold: int
    out_of_stock_threshold: int
    stock_status: str
    last_synced_at: Optional[datetime]
    enable_low_stock_alert: bool
    last_alerted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InventoryCreate(BaseModel):
    product_id: str
    supplier_id: str
    available_quantity: int = Field(ge=0)
    low_stock_threshold: int = Field(default=10, ge=0)


class InventoryAdjust(BaseModel):
    quantity_change: int
    reason: str = "manual"
    reference_id: Optional[str] = None
    notes: Optional[str] = None


class InventoryReserve(BaseModel):
    quantity: int = Field(gt=0)
    reference_id: str


class InventoryHistoryResponse(BaseModel):
    id: str
    inventory_id: str
    product_id: str
    change_type: str
    quantity_before: int
    quantity_after: int
    quantity_changed: int
    reason: str
    reference_id: Optional[str]
    notes: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class InventoryAlertResponse(BaseModel):
    id: str
    inventory_id: str
    product_id: str
    supplier_id: Optional[str]
    alert_type: str
    alert_level: str
    current_quantity: int
    threshold_quantity: int
    title: str
    message: str
    is_read: bool
    is_resolved: bool
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InventorySyncHistoryResponse(BaseModel):
    id: str
    supplier_id: str
    sync_type: str
    sync_status: str
    total_products: int
    synced_products: int
    failed_products: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class InventoryStatsResponse(BaseModel):
    total_inventories: int
    in_stock_count: int
    low_stock_count: int
    out_of_stock_count: int
    total_quantity: int
    available_quantity: int
    reserved_quantity: int
    unresolved_alerts: int


# ===== API 엔드포인트 =====

async def get_db() -> AsyncSession:
    """데이터베이스 세션 의존성"""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        yield session


@router.get("/", response_model=List[InventoryResponse])
async def get_inventories(
    supplier_id: Optional[str] = Query(None),
    stock_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    재고 목록 조회
    
    - **supplier_id**: 공급사 ID 필터 (선택)
    - **stock_status**: 재고 상태 필터 (in_stock, low_stock, out_of_stock)
    - **limit**: 페이지 크기
    - **offset**: 페이지 오프셋
    """
    try:
        service = InventoryService(db)
        inventories = await service.get_inventories(
            supplier_id=supplier_id,
            stock_status=stock_status,
            limit=limit,
            offset=offset
        )
        return inventories
    except Exception as e:
        logger.error(f"재고 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}", response_model=InventoryResponse)
async def get_inventory(
    product_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 상품의 재고 조회
    """
    try:
        service = InventoryService(db)
        inventory = await service.get_inventory_by_product_id(product_id)
        
        if not inventory:
            raise HTTPException(status_code=404, detail=f"재고를 찾을 수 없습니다: {product_id}")
        
        return inventory
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"재고 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=InventoryResponse)
async def create_inventory(
    inventory: InventoryCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    재고 생성 또는 업데이트
    """
    try:
        logger.info(f"재고 생성 요청: {inventory.product_id}")
        service = InventoryService(db)
        created_inventory = await service.create_or_update_inventory(
            product_id=inventory.product_id,
            supplier_id=inventory.supplier_id,
            available_quantity=inventory.available_quantity,
            low_stock_threshold=inventory.low_stock_threshold
        )
        logger.info(f"재고 생성 완료: ID={created_inventory.id}")
        return created_inventory
    except Exception as e:
        logger.error(f"재고 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{product_id}/adjust", response_model=InventoryResponse)
async def adjust_inventory(
    product_id: str,
    adjust: InventoryAdjust,
    db: AsyncSession = Depends(get_db)
):
    """
    재고 조정 (증가/감소)
    
    - **quantity_change**: 변동량 (양수: 증가, 음수: 감소)
    - **reason**: 변동 사유
    - **reference_id**: 참조 ID (선택)
    - **notes**: 비고 (선택)
    """
    try:
        logger.info(f"재고 조정 요청: {product_id}, 변동량: {adjust.quantity_change}")
        service = InventoryService(db)
        inventory = await service.adjust_inventory(
            product_id=product_id,
            quantity_change=adjust.quantity_change,
            reason=adjust.reason,
            reference_id=adjust.reference_id,
            notes=adjust.notes
        )
        logger.info(f"재고 조정 완료: {product_id}")
        return inventory
    except ValueError as e:
        logger.error(f"재고 조정 실패: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"재고 조정 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{product_id}/reserve", response_model=InventoryResponse)
async def reserve_inventory(
    product_id: str,
    reserve: InventoryReserve,
    db: AsyncSession = Depends(get_db)
):
    """
    재고 예약 (주문 시)
    """
    try:
        logger.info(f"재고 예약 요청: {product_id}, 수량: {reserve.quantity}")
        service = InventoryService(db)
        inventory = await service.reserve_inventory(
            product_id=product_id,
            quantity=reserve.quantity,
            reference_id=reserve.reference_id
        )
        logger.info(f"재고 예약 완료: {product_id}")
        return inventory
    except ValueError as e:
        logger.error(f"재고 예약 실패: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"재고 예약 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{product_id}/release", response_model=InventoryResponse)
async def release_reservation(
    product_id: str,
    reserve: InventoryReserve,
    db: AsyncSession = Depends(get_db)
):
    """
    재고 예약 해제 (주문 취소 시)
    """
    try:
        logger.info(f"재고 예약 해제 요청: {product_id}, 수량: {reserve.quantity}")
        service = InventoryService(db)
        inventory = await service.release_reservation(
            product_id=product_id,
            quantity=reserve.quantity,
            reference_id=reserve.reference_id
        )
        logger.info(f"재고 예약 해제 완료: {product_id}")
        return inventory
    except ValueError as e:
        logger.error(f"재고 예약 해제 실패: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"재고 예약 해제 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 재고 이력 API =====

@router.get("/history/", response_model=List[InventoryHistoryResponse])
async def get_inventory_history(
    product_id: Optional[str] = Query(None),
    inventory_id: Optional[str] = Query(None),
    change_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    재고 변동 이력 조회
    """
    try:
        service = InventoryService(db)
        history = await service.get_inventory_history(
            product_id=product_id,
            inventory_id=inventory_id,
            change_type=change_type,
            limit=limit,
            offset=offset
        )
        return history
    except Exception as e:
        logger.error(f"재고 이력 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 재고 알림 API =====

@router.get("/alerts/", response_model=List[InventoryAlertResponse])
async def get_inventory_alerts(
    supplier_id: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
    is_resolved: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    재고 알림 목록 조회
    """
    try:
        service = InventoryService(db)
        alerts = await service.get_inventory_alerts(
            supplier_id=supplier_id,
            alert_type=alert_type,
            is_read=is_read,
            is_resolved=is_resolved,
            limit=limit,
            offset=offset
        )
        return alerts
    except Exception as e:
        logger.error(f"재고 알림 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/alerts/{alert_id}/read", response_model=InventoryAlertResponse)
async def mark_alert_as_read(
    alert_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    재고 알림 읽음 처리
    """
    try:
        service = InventoryService(db)
        alert = await service.mark_alert_as_read(alert_id)
        return alert
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"알림 읽음 처리 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/alerts/{alert_id}/resolve", response_model=InventoryAlertResponse)
async def resolve_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    재고 알림 해결 처리
    """
    try:
        service = InventoryService(db)
        alert = await service.resolve_alert(alert_id)
        return alert
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"알림 해결 처리 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 재고 동기화 API =====

@router.get("/sync-history/", response_model=List[InventorySyncHistoryResponse])
async def get_sync_history(
    supplier_id: Optional[str] = Query(None),
    sync_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    재고 동기화 이력 조회
    """
    try:
        service = InventoryService(db)
        history = await service.get_sync_history(
            supplier_id=supplier_id,
            sync_status=sync_status,
            limit=limit,
            offset=offset
        )
        return history
    except Exception as e:
        logger.error(f"동기화 이력 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 재고 통계 API =====

@router.get("/stats/{supplier_id}", response_model=InventoryStatsResponse)
async def get_inventory_stats(
    supplier_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    재고 통계 조회
    """
    try:
        service = InventoryService(db)
        stats = await service.get_inventory_stats(supplier_id=supplier_id)
        return stats
    except Exception as e:
        logger.error(f"재고 통계 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
