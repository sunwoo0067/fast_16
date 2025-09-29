"""
진행 상황 추적이 포함된 상품 수집 서비스
"""
import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert

from app.core.logging import get_logger, LoggerMixin
from app.core.exceptions import ProductSyncError
from app.models.database import Product, ProductSyncHistory, Supplier, SupplierAccount
from app.services.ownerclan_collector import OwnerClanCollector

logger = get_logger(__name__)

class ProgressCollector(LoggerMixin):
    """
    진행 상황을 추적하는 상품 수집 서비스
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ownerclan_collector = OwnerClanCollector(db)
        self.batch_size = 10  # 한 번에 처리할 상품 수
    
    async def _update_progress(self, task_id: str, current: int, total: int, status: str, message: str, **kwargs):
        """진행 상황을 API를 통해 업데이트"""
        import httpx
        
        progress_data = {
            "current": current,
            "total": total,
            "progress_percent": (current / total * 100) if total > 0 else 0,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"http://localhost:8000/api/v1/progress/progress/{task_id}",
                    json=progress_data,
                    timeout=5.0
                )
        except Exception as e:
            logger.error(f"진행 상황 업데이트 실패: {e}")
    
    async def collect_products_with_progress(
        self,
        supplier_id: int,
        supplier_account_id: Optional[int] = None,
        count: int = 50,
        task_id: str = "default_task"
    ) -> Dict[str, Any]:
        """
        OwnerClan API에서 상품을 수집하고 진행 상황을 추적합니다.
        """
        start_time = datetime.now()
        collected_count = 0
        saved_count = 0
        errors = []
        
        await self._update_progress(task_id, 0, count, "started", "상품 수집 시작...")
        
        try:
            # OwnerClanCollector를 사용하여 상품 수집
            # supplier_account_id가 없으면 기본값 1 사용
            if supplier_account_id is None:
                supplier_account_id = 1
            
            collection_result = await self.ownerclan_collector.collect_products(
                supplier_account_id=supplier_account_id,
                limit=count
            )
            
            # 수집된 상품 데이터 처리
            # OwnerClanCollector는 collected_products 필드를 반환하지 않음
            collected_count = collection_result.get("collected", 0)
            saved_count = collection_result.get("saved", 0)
            
            if collection_result.get("success", False):
                await self._update_progress(
                    task_id, 
                    count, 
                    count, 
                    "completed", 
                    f"상품 수집 완료: {collected_count}개 수집, {saved_count}개 저장",
                    collected_count=collected_count,
                    saved_count=saved_count
                )
                
                return {
                    "success": True,
                    "collected": collected_count,
                    "saved": saved_count,
                    "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
                }
            else:
                raise ProductSyncError(collection_result.get("error", "상품 수집 실패"))
            
        except Exception as e:
            error_msg = f"상품 수집 중 치명적인 오류 발생: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            await self._update_progress(
                task_id, 
                0, 
                count, 
                "failed", 
                error_msg,
                errors=errors,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
            
            return {
                "success": False,
                "collected": 0,
                "saved": 0,
                "errors": errors,
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
            }
    
    async def collect_all_suppliers_with_progress(
        self,
        count: int = 50,
        task_id: str = "default_task"
    ) -> Dict[str, Any]:
        """
        모든 공급사에서 상품을 수집하고 진행 상황을 추적합니다.
        """
        start_time = datetime.now()
        total_collected = 0
        total_saved = 0
        errors = []
        
        await self._update_progress(task_id, 0, count, "started", "모든 공급사 상품 수집 시작...")
        
        try:
            # 활성 공급사 목록 조회
            suppliers_result = await self.db.execute(
                select(Supplier).where(Supplier.is_active == True)
            )
            active_suppliers = suppliers_result.scalars().all()
            
            if not active_suppliers:
                raise ProductSyncError("활성 공급사가 없습니다")
            
            total_suppliers = len(active_suppliers)
            await self._update_progress(
                task_id, 
                0, 
                total_suppliers, 
                "in_progress", 
                f"{total_suppliers}개 공급사에서 상품 수집 중..."
            )
            
            for i, supplier in enumerate(active_suppliers):
                try:
                    # 각 공급사별로 상품 수집
                    supplier_task_id = f"{task_id}_supplier_{supplier.id}"
                    supplier_result = await self.collect_products_with_progress(
                        supplier_id=supplier.id,
                        supplier_account_id=1,  # 기본 계정 사용
                        count=count // total_suppliers,  # 공급사별 수집 수량 분배
                        task_id=supplier_task_id
                    )
                    
                    if supplier_result.get("success", False):
                        total_collected += supplier_result.get("collected", 0)
                        total_saved += supplier_result.get("saved", 0)
                    
                    # 전체 진행 상황 업데이트
                    await self._update_progress(
                        task_id,
                        i + 1,
                        total_suppliers,
                        "in_progress",
                        f"공급사 {supplier.name} 완료 ({i + 1}/{total_suppliers})",
                        collected_count=total_collected,
                        saved_count=total_saved
                    )
                    
                except Exception as e:
                    error_msg = f"공급사 {supplier.name} 상품 수집 실패: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # 최종 결과
            await self._update_progress(
                task_id,
                total_suppliers,
                total_suppliers,
                "completed",
                f"모든 공급사 상품 수집 완료: {total_collected}개 수집, {total_saved}개 저장",
                collected_count=total_collected,
                saved_count=total_saved,
                errors=errors
            )
            
            return {
                "success": True,
                "collected": total_collected,
                "saved": total_saved,
                "suppliers_processed": total_suppliers,
                "errors": errors,
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
            }
            
        except Exception as e:
            error_msg = f"모든 공급사 상품 수집 중 치명적인 오류 발생: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            await self._update_progress(
                task_id,
                0,
                count,
                "failed",
                error_msg,
                errors=errors,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
            
            return {
                "success": False,
                "collected": 0,
                "saved": 0,
                "errors": errors,
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
            }