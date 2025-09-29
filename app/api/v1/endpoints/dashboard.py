#!/usr/bin/env python3
"""Dashboard API endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Dict, Any
from datetime import datetime, timedelta

from app.models.database import get_db, Product, Supplier, SupplierAccount, Order
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("/stats", response_model=Dict[str, Any])
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """대시보드 통계 정보 조회"""
    try:
        logger.info("대시보드 통계 조회 요청")
        
        # 총 상품 수
        total_products_result = await db.execute(
            select(func.count(Product.id))
        )
        total_products = total_products_result.scalar() or 0
        
        # 활성 상품 수
        active_products_result = await db.execute(
            select(func.count(Product.id)).where(Product.is_active == True)
        )
        active_products = active_products_result.scalar() or 0
        
        # 총 공급사 수
        total_suppliers_result = await db.execute(
            select(func.count(Supplier.id))
        )
        total_suppliers = total_suppliers_result.scalar() or 0
        
        # 활성 공급사 수
        active_suppliers_result = await db.execute(
            select(func.count(Supplier.id)).where(Supplier.is_active == True)
        )
        active_suppliers = active_suppliers_result.scalar() or 0
        
        # 총 주문 수
        total_orders_result = await db.execute(
            select(func.count(Order.id))
        )
        total_orders = total_orders_result.scalar() or 0
        
        # 오늘 생성된 상품 수
        today = datetime.now().date()
        today_products_result = await db.execute(
            select(func.count(Product.id)).where(
                func.date(Product.created_at) == today
            )
        )
        today_products = today_products_result.scalar() or 0
        
        # 이번 주 생성된 상품 수
        week_start = today - timedelta(days=today.weekday())
        week_products_result = await db.execute(
            select(func.count(Product.id)).where(
                func.date(Product.created_at) >= week_start
            )
        )
        week_products = week_products_result.scalar() or 0
        
        # 이번 달 생성된 상품 수
        month_start = today.replace(day=1)
        month_products_result = await db.execute(
            select(func.count(Product.id)).where(
                func.date(Product.created_at) >= month_start
            )
        )
        month_products = month_products_result.scalar() or 0
        
        stats = {
            "products": {
                "total": total_products,
                "active": active_products,
                "inactive": total_products - active_products,
                "today": today_products,
                "this_week": week_products,
                "this_month": month_products
            },
            "suppliers": {
                "total": total_suppliers,
                "active": active_suppliers,
                "inactive": total_suppliers - active_suppliers
            },
            "orders": {
                "total": total_orders
            },
            "system": {
                "uptime": "실시간",
                "status": "정상",
                "last_updated": datetime.now().isoformat()
            }
        }
        
        logger.info(f"대시보드 통계 조회 완료: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"대시보드 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")

@router.get("/sync-history", response_model=Dict[str, Any])
async def get_sync_history(
    limit: int = 10,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """동기화 히스토리 조회"""
    try:
        logger.info(f"동기화 히스토리 조회 요청: limit={limit}, offset={offset}")
        
        # 최근 상품 동기화 기록 (상품 업데이트 시간 기준)
        recent_products_result = await db.execute(
            select(Product)
            .where(Product.last_synced_at.isnot(None))
            .order_by(Product.last_synced_at.desc())
            .limit(limit)
            .offset(offset)
        )
        recent_products = recent_products_result.scalars().all()
        
        sync_history = []
        for product in recent_products:
            sync_history.append({
                "id": product.id,
                "product_name": product.title,
                "supplier_name": product.supplier_name,
                "sync_status": product.sync_status,
                "last_synced_at": product.last_synced_at.isoformat() if product.last_synced_at else None,
                "sync_error_message": product.sync_error_message,
                "item_key": product.item_key
            })
        
        # 총 동기화 기록 수
        total_count_result = await db.execute(
            select(func.count(Product.id)).where(
                Product.last_synced_at.isnot(None)
            )
        )
        total_count = total_count_result.scalar() or 0
        
        result = {
            "sync_history": sync_history,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }
        
        logger.info(f"동기화 히스토리 조회 완료: {len(sync_history)}개 기록")
        return result
        
    except Exception as e:
        logger.error(f"동기화 히스토리 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"동기화 히스토리 조회 실패: {str(e)}")
