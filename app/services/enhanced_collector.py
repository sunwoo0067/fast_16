"""
향상된 상품 수집 서비스 - 진행 상황 추적 및 모니터링 포함
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ownerclan_collector import OwnerClanCollector
from app.services.product_service import ProductService
from app.websocket.progress_tracker import (
    update_collection_progress, 
    complete_collection_task, 
    fail_collection_task
)
from app.core.logging import get_logger, log_product_sync

logger = get_logger(__name__)

class EnhancedProductCollector:
    """향상된 상품 수집 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ownerclan_collector = OwnerClanCollector(db)
        self.product_service = ProductService(db)
    
    async def collect_products_with_progress(
        self,
        supplier_id: int,
        supplier_account_id: Optional[int] = None,
        count: int = 50,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """진행 상황 추적이 포함된 상품 수집"""
        
        if not task_id:
            task_id = f"collect_{supplier_id}_{uuid.uuid4().hex[:8]}"
        
        try:
            # 작업 시작 알림
            from app.websocket.progress_tracker import progress_tracker
            progress_tracker.start_task(task_id, count)
            await progress_tracker.broadcast_progress(task_id, progress_tracker.get_progress(task_id))
            
            logger.info(f"상품 수집 시작: task_id={task_id}, supplier_id={supplier_id}, count={count}")
            
            # 진행 상황 업데이트
            await update_collection_progress(
                task_id, 0, count, "OwnerClan API 연결 중..."
            )
            
            # OwnerClan API에서 상품 데이터 수집
            products_data = await self.ownerclan_collector._fetch_products_from_ownerclan(
                supplier_id=supplier_id,
                supplier_account_id=supplier_account_id,
                count=count
            )
            
            if not products_data:
                await update_collection_progress(
                    task_id, 0, count, "수집할 상품이 없습니다."
                )
                result = {
                    "task_id": task_id,
                    "total_products": 0,
                    "new_products": 0,
                    "updated_products": 0,
                    "errors": [],
                    "duration_ms": 0,
                    "status": "completed"
                }
                await complete_collection_task(task_id, result)
                return result
            
            total_products = len(products_data)
            new_products = 0
            updated_products = 0
            errors = []
            
            # 진행 상황 업데이트
            await update_collection_progress(
                task_id, 0, total_products, f"총 {total_products}개 상품 처리 시작"
            )
            
            # 각 상품 처리
            for i, product_data in enumerate(products_data):
                try:
                    # 진행 상황 업데이트
                    await update_collection_progress(
                        task_id, 
                        i + 1, 
                        total_products, 
                        f"상품 처리 중: {product_data.get('name', 'Unknown')}",
                        {
                            "new_products": new_products,
                            "updated_products": updated_products,
                            "errors": len(errors)
                        }
                    )
                    
                    # 상품이 이미 존재하는지 확인
                    existing_product = await self.product_service.get_product_by_item_key(
                        product_data["item_key"], supplier_id
                    )
                    
                    if existing_product:
                        # 기존 상품 업데이트
                        await self.product_service.update_product(
                            existing_product.id,
                            **product_data
                        )
                        updated_products += 1
                        logger.debug(f"상품 업데이트: {product_data['item_key']}")
                    else:
                        # 새 상품 생성
                        await self.product_service.create_product(
                            supplier_id=supplier_id,
                            supplier_account_id=supplier_account_id or 1,
                            **product_data
                        )
                        new_products += 1
                        logger.debug(f"새 상품 생성: {product_data['item_key']}")
                    
                    # 처리 속도 조절 (API 부하 방지)
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    error_msg = f"상품 처리 실패: {product_data.get('item_key', 'Unknown')} - {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 최종 결과
            result = {
                "task_id": task_id,
                "total_products": total_products,
                "new_products": new_products,
                "updated_products": updated_products,
                "errors": errors,
                "duration_ms": 0,  # 실제로는 시작 시간부터 계산
                "status": "completed"
            }
            
            # 완료 알림
            await update_collection_progress(
                task_id, 
                total_products, 
                total_products, 
                f"수집 완료: 새 상품 {new_products}개, 업데이트 {updated_products}개",
                {
                    "new_products": new_products,
                    "updated_products": updated_products,
                    "errors": len(errors)
                }
            )
            
            await complete_collection_task(task_id, result)
            
            # 로그 기록
            log_product_sync(
                product_data={
                    "supplier_id": supplier_id,
                    "total_products": total_products
                },
                action="collect_with_progress",
                success=True,
                sync_stats={
                    "new_products": new_products,
                    "updated_products": updated_products,
                    "errors": len(errors)
                }
            )
            
            logger.info(f"상품 수집 완료: task_id={task_id}, 결과={result}")
            return result
            
        except Exception as e:
            error_msg = f"상품 수집 실패: {str(e)}"
            logger.error(error_msg)
            await fail_collection_task(task_id, error_msg)
            
            result = {
                "task_id": task_id,
                "total_products": 0,
                "new_products": 0,
                "updated_products": 0,
                "errors": [error_msg],
                "duration_ms": 0,
                "status": "failed"
            }
            return result
    
    async def collect_all_suppliers_with_progress(
        self,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """모든 공급사의 상품 수집 (진행 상황 추적 포함)"""
        
        if not task_id:
            task_id = f"collect_all_{uuid.uuid4().hex[:8]}"
        
        try:
            # 활성 공급사 목록 조회
            suppliers = await self.product_service.get_active_suppliers()
            total_suppliers = len(suppliers)
            
            # 작업 시작 알림
            from app.websocket.progress_tracker import progress_tracker
            progress_tracker.start_task(task_id, total_suppliers)
            await progress_tracker.broadcast_progress(task_id, progress_tracker.get_progress(task_id))
            
            logger.info(f"전체 공급사 상품 수집 시작: task_id={task_id}, suppliers={total_suppliers}")
            
            total_new_products = 0
            total_updated_products = 0
            all_errors = []
            supplier_results = []
            
            # 각 공급사별 수집
            for i, supplier in enumerate(suppliers):
                try:
                    await update_collection_progress(
                        task_id,
                        i + 1,
                        total_suppliers,
                        f"공급사 처리 중: {supplier['name']}",
                        {
                            "total_new_products": total_new_products,
                            "total_updated_products": total_updated_products,
                            "total_errors": len(all_errors)
                        }
                    )
                    
                    # 공급사별 상품 수집
                    supplier_result = await self.collect_products_with_progress(
                        supplier_id=supplier["id"],
                        count=50,  # 공급사당 50개씩
                        task_id=f"{task_id}_supplier_{supplier['id']}"
                    )
                    
                    total_new_products += supplier_result.get("new_products", 0)
                    total_updated_products += supplier_result.get("updated_products", 0)
                    all_errors.extend(supplier_result.get("errors", []))
                    
                    supplier_results.append({
                        "supplier_id": supplier["id"],
                        "supplier_name": supplier["name"],
                        "result": supplier_result
                    })
                    
                    # 공급사 간 처리 속도 조절
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    error_msg = f"공급사 {supplier['name']} 처리 실패: {str(e)}"
                    all_errors.append(error_msg)
                    logger.error(error_msg)
            
            # 최종 결과
            result = {
                "task_id": task_id,
                "total_suppliers": total_suppliers,
                "total_new_products": total_new_products,
                "total_updated_products": total_updated_products,
                "total_errors": len(all_errors),
                "supplier_results": supplier_results,
                "errors": all_errors,
                "status": "completed"
            }
            
            # 완료 알림
            await update_collection_progress(
                task_id,
                total_suppliers,
                total_suppliers,
                f"전체 수집 완료: 새 상품 {total_new_products}개, 업데이트 {total_updated_products}개",
                {
                    "total_new_products": total_new_products,
                    "total_updated_products": total_updated_products,
                    "total_errors": len(all_errors)
                }
            )
            
            await complete_collection_task(task_id, result)
            
            logger.info(f"전체 공급사 상품 수집 완료: task_id={task_id}, 결과={result}")
            return result
            
        except Exception as e:
            error_msg = f"전체 공급사 상품 수집 실패: {str(e)}"
            logger.error(error_msg)
            await fail_collection_task(task_id, error_msg)
            
            result = {
                "task_id": task_id,
                "total_suppliers": 0,
                "total_new_products": 0,
                "total_updated_products": 0,
                "total_errors": 1,
                "supplier_results": [],
                "errors": [error_msg],
                "status": "failed"
            }
            return result
